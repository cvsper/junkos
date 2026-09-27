"""Monday scorecard: paid jobs first, then where the week's leads went.

One email, every Monday at 8am Florida time, whether or not anyone asks.
The point is the first number. Everything under it explains it.
"""
from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from models import db, Job, CallLog, DeskActivity, B2BLead

logger = logging.getLogger(__name__)

WEEKLY_TARGET = 5   # 20 paid jobs in 30 days, the 30-day test


def _now():
    return datetime.now(timezone.utc)


def _section(name, fn):
    try:
        return fn()
    except Exception:
        logger.exception("scorecard section %s failed", name)
        return {"error": "unavailable"}


def build(days=7):
    since = _now() - timedelta(days=days)
    since_naive = since.replace(tzinfo=None)
    r = {"days": days, "since": since.isoformat(timespec="minutes"), "target_paid_jobs": WEEKLY_TARGET * days / 7}

    def jobs():
        done = Job.query.filter(Job.status == "completed", Job.completed_at >= since_naive).all()
        booked = Job.query.filter(Job.created_at >= since_naive,
                                  Job.status.notin_(("cancelled", "canceled"))).all()
        cancelled = Job.query.filter(Job.created_at >= since_naive,
                                     Job.status.in_(("cancelled", "canceled"))).count()
        src = Counter((j.lead_source or "unknown") for j in booked)
        return {"paid": len(done), "revenue": round(sum(float(j.total_price or 0) for j in done), 2),
                "booked": len(booked), "booked_value": round(sum(float(j.total_price or 0) for j in booked), 2),
                "cancelled": cancelled, "booked_by_source": dict(src.most_common())}
    r["jobs"] = _section("jobs", jobs)

    def calls():
        import missed_booking
        rows = CallLog.query.filter(CallLog.created_at >= since_naive).all()
        priced = [c for c in rows if missed_booking.was_priced(c.transcript, c.summary)]
        booked = [c for c in rows if c.booking_created]
        captured = DeskActivity.query.filter(DeskActivity.kind == "callback",
                                             DeskActivity.body.like("%" + missed_booking.MARKER + "%"),
                                             DeskActivity.created_at >= since_naive).count()
        return {"calls": len(rows), "priced": len(priced), "booked_on_call": len(booked),
                "priced_not_booked": len([c for c in priced if not c.booking_created]),
                "callback_tasks_made": captured}
    r["maya"] = _section("maya", calls)

    def leads():
        from leads import collect
        rows, broken = collect(days=days)
        by = {}
        for l in rows:
            s = by.setdefault(l.get("source") or "unknown", {"leads": 0, "untouched": 0})
            s["leads"] += 1
            if not l.get("touched_at"):
                s["untouched"] += 1
        return {"total": len(rows), "untouched": sum(v["untouched"] for v in by.values()),
                "by_source": by, "sources_failed": broken}
    r["leads"] = _section("leads", leads)

    def followups():
        from models_leads import QuoteFollowup
        sent = QuoteFollowup.query.filter(QuoteFollowup.last_sent_at >= since_naive).count()
        booked = QuoteFollowup.query.filter(QuoteFollowup.stopped_at >= since_naive,
                                            QuoteFollowup.stop_reason == "booked").count()
        return {"texts_sent": sent, "booked_after_text": booked}
    r["quote_followups"] = _section("followups", followups)

    def funnel():
        import booking_funnel
        rep = booking_funnel.report(days=days) or {}
        return {k: rep.get(k) for k in ("started", "saw_a_price", "booked", "left_and_reachable") if k in rep}
    r["web_funnel"] = _section("funnel", funnel)

    def b2b():
        emailed = B2BLead.query.filter(B2BLead.last_contacted_at >= since_naive).count()
        new = B2BLead.query.filter(B2BLead.created_at >= since_naive).count()
        with_email = B2BLead.query.filter(B2BLead.email.isnot(None)).count()
        replies = DeskActivity.query.filter(DeskActivity.kind == "sms", DeskActivity.direction == "in",
                                            DeskActivity.prospect_id.isnot(None),
                                            DeskActivity.created_at >= since_naive).count()
        return {"emails_sent": emailed, "new_leads": new, "leads_with_email": with_email,
                "prospect_texts_in": replies}
    r["b2b"] = _section("b2b", b2b)

    def haulers():
        from models_sameday import HaulerConfirmation
        rows = HaulerConfirmation.query.filter(HaulerConfirmation.asked_at >= since_naive).all()
        return dict(Counter(x.status for x in rows)) | {"asked": len(rows)}
    r["hauler_confirmations"] = _section("haulers", haulers)
    return r


def _kv(d):
    if not isinstance(d, dict):
        return "<i>{}</i>".format(d)
    return "".join("<tr><td style='padding:3px 12px 3px 0;color:#555'>{}</td><td style='padding:3px 0;font-weight:600'>{}</td></tr>"
                   .format(k.replace("_", " "), v if not isinstance(v, dict) else
                           ", ".join("{} {}".format(kk, vv) for kk, vv in v.items()) or "none")
                   for k, v in d.items())


def html(r):
    jobs = r.get("jobs") or {}
    paid = jobs.get("paid", 0)
    target = r.get("target_paid_jobs", WEEKLY_TARGET)
    verdict = ("On pace." if paid >= target else
               "Below the {} a week the 30-day test needs.".format(int(target)))
    blocks = [("Maya (phone)", r.get("maya")), ("Leads", r.get("leads")), ("Quote follow-up texts", r.get("quote_followups")),
              ("Website funnel", r.get("web_funnel")), ("B2B outreach", r.get("b2b")),
              ("Hauler confirmations", r.get("hauler_confirmations"))]
    body = "".join("<h3 style='margin:18px 0 4px;font-size:15px'>{}</h3><table style='font-size:14px;border-collapse:collapse'>{}</table>"
                   .format(t, _kv(d)) for t, d in blocks)
    return """<div style="font-family:Arial,sans-serif;color:#1a1a1a;max-width:560px">
<p style="font-size:13px;color:#777;margin:0">Umuve · last {days} days</p>
<p style="font-size:44px;font-weight:700;margin:4px 0 0;line-height:1">{paid}</p>
<p style="margin:2px 0 0;font-size:15px">paid jobs · ${rev:,.0f} revenue · {verdict}</p>
<table style="font-size:14px;border-collapse:collapse;margin-top:12px">{jobs}</table>
{body}
<p style="font-size:12px;color:#777;margin-top:22px">The number that matters is the first one. Everything else explains it.</p>
</div>""".format(days=r.get("days"), paid=paid, rev=jobs.get("revenue", 0) or 0, verdict=verdict,
                 jobs=_kv({k: v for k, v in jobs.items() if k not in ("paid", "revenue")}), body=body)


def send_weekly(app):
    with app.app_context():
        to = os.environ.get("SCORECARD_TO") or os.environ.get("ADMIN_EMAIL", "")
        if not to:
            logger.warning("scorecard: no ADMIN_EMAIL, nothing sent")
            return
        try:
            from notifications import send_email
            r = build(7)
            paid = (r.get("jobs") or {}).get("paid", 0)
            send_email(to, "Umuve week: {} paid job{}".format(paid, "" if paid == 1 else "s"), html(r))
            logger.info("weekly scorecard sent to %s", to)
        except Exception:
            logger.exception("weekly scorecard failed")
