"""Desk dependency health — checked on a schedule, alerts on state change.

Checks (each → ok/warn/fail + a plain reason):
  twilio_account    account reachable and active (read-only fetch)
  twilio_balance    balance above DESK_MIN_BALANCE (default $5)
  desk_number       the desk line exists and its SMS/voice webhooks point at us
  browser_calling   API key + TwiML app + desk number env present
  inbound_recent    a Twilio webhook reached us in the last DESK_INBOUND_STALE_HOURS (warn only)
  transcription     no transcription-error events in the last 24h (warn only)
  sentry            SENTRY_DSN configured (warn only)

Alerts go to ADMIN_EMAIL, SLACK_ALERT_WEBHOOK (if set) and an in-app admin
Notification, only when the overall state changes (ok→degraded, degraded→ok),
so a broken line pings once, not every 30 minutes. Public summary at
/api/health/desk carries no secrets.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

MIN_BALANCE = float(os.environ.get("DESK_MIN_BALANCE", "5") or 5)
INBOUND_STALE_HOURS = int(os.environ.get("DESK_INBOUND_STALE_HOURS", "72") or 72)


def _env(k):
    return (os.environ.get(k) or "").strip()


def _base_url():
    return (_env("BACKEND_URL") or "https://junkos-backend.onrender.com").rstrip("/")


def check_desk_health(alert=False):
    from models import db, DeskActivity, DeskSetting
    checks = {}

    def put(name, state, reason, **extra):
        checks[name] = dict({"state": state, "reason": reason}, **extra)

    sid, tok = _env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN")
    desk = _env("DESK_TWILIO_NUMBER")
    client = None
    if sid and tok:
        try:
            from twilio.rest import Client
            client = Client(sid, tok)
            acct = client.api.accounts(sid).fetch()
            put("twilio_account", "ok" if acct.status == "active" else "fail",
                "account " + acct.status)
        except Exception as e:
            put("twilio_account", "fail", "Twilio unreachable: " + type(e).__name__)
            client = None
    else:
        put("twilio_account", "fail", "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set")

    if client:
        try:
            bal = client.balance.fetch()
            amount = float(bal.balance)
            put("twilio_balance", "ok" if amount >= MIN_BALANCE else "fail",
                "${:.2f}".format(amount) + ("" if amount >= MIN_BALANCE else " — below ${:.0f}, top up or enable auto-recharge".format(MIN_BALANCE)),
                balance=round(amount, 2))
        except Exception as e:
            put("twilio_balance", "warn", "balance unavailable: " + type(e).__name__)
        if desk:
            try:
                nums = client.incoming_phone_numbers.list(phone_number=desk, limit=1)
                if not nums:
                    put("desk_number", "fail", desk + " is not on this Twilio account")
                else:
                    n = nums[0]
                    want_sms = _base_url() + "/api/desk/twilio/sms"
                    want_voice = _base_url() + "/api/desk/twilio/voice/inbound"
                    bad = []
                    if (n.sms_url or "") != want_sms:
                        bad.append("sms webhook → " + (n.sms_url or "unset"))
                    if (n.voice_url or "") != want_voice:
                        bad.append("voice webhook → " + (n.voice_url or "unset"))
                    put("desk_number", "ok" if not bad else "fail",
                        "webhooks wired" if not bad else "; ".join(bad))
            except Exception as e:
                put("desk_number", "warn", "couldn't read the number: " + type(e).__name__)
        else:
            put("desk_number", "fail", "DESK_TWILIO_NUMBER not set — texts fall back to the main number")

    missing = [k for k in ("TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET", "TWILIO_TWIML_APP_SID", "DESK_TWILIO_NUMBER") if not _env(k)]
    put("browser_calling", "ok" if not missing else "fail",
        "configured" if not missing else "missing " + ", ".join(missing))

    try:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=INBOUND_STALE_HOURS)
        recent = DeskActivity.query.filter(DeskActivity.direction == "in", DeskActivity.created_at >= since).count()
        last = (DeskActivity.query.filter(DeskActivity.direction == "in")
                .order_by(DeskActivity.created_at.desc()).first())
        put("inbound_recent", "ok" if recent else "warn",
            "{} inbound in {}h".format(recent, INBOUND_STALE_HOURS) if recent else
            "no inbound text or call in {}h (last: {})".format(INBOUND_STALE_HOURS, last.created_at.isoformat() if last else "never"))
    except Exception as e:
        put("inbound_recent", "warn", "db check failed: " + type(e).__name__)

    try:
        errs = DeskSetting.get("health:transcription_errors_24h")
        put("transcription", "ok" if not errs or int(errs) == 0 else "warn",
            "no errors" if not errs or int(errs) == 0 else "{} transcription errors in 24h".format(errs))
    except Exception:
        put("transcription", "ok", "no errors")

    try:
        from sameday_pay import balance_check
        b = balance_check()
        put("stripe_balance", b["state"], b["reason"], available=b.get("available"),
            pending=b.get("pending"), expected=b.get("expected"),
            due_count=b.get("due_count"), due_jobs=b.get("due_jobs"))
    except Exception as e:
        put("stripe_balance", "warn", "balance check failed: " + type(e).__name__)

    try:
        from ops_sentinel import stranded_summary
        st = stranded_summary()
        n, recent = st["total"], st["recent_total"]
        # Only the recent slice is actionable; months-old rows are seed residue.
        state = "ok" if recent == 0 else ("fail" if st["recent_with_driver"] else "warn")
        reason = ("no live jobs stranded ({} old/seed rows ignored)".format(n) if recent == 0 else
                  "{} live job(s) stranded, {} with a hauler assigned — customers waiting or haulers "
                  "unpaid ({} old/seed rows ignored)".format(recent, st["recent_with_driver"], n - recent))
        put("stranded_jobs", state, reason, total=n, recent_total=recent,
            recent_with_driver=st["recent_with_driver"], buckets=st["buckets"],
            by_status=st["by_status"], recent=st["recent"])
    except Exception as e:
        put("stranded_jobs", "warn", "stranded check failed: " + type(e).__name__)

    # Who a live inbound call actually reaches. DESK_FORWARD_NUMBER rings
    # alongside the browser, so if it is the owner's private mobile then every
    # customer call rings his cell — the thing he asked to stop. Only the last
    # four digits are reported; this endpoint is unauthenticated.
    try:
        from ops_contacts import alert_phone
        fwd = (_env("DESK_FORWARD_NUMBER") or "").strip()
        private = (alert_phone() or "").strip()
        tail = fwd[-4:] if fwd else ""
        if not fwd:
            put("inbound_forward", "ok", "browser only — inbound rings the desk, no cell in the loop")
        elif private and fwd[-10:] == private[-10:]:
            put("inbound_forward", "fail",
                "every inbound call also rings the private alert number (…{}) — "
                "point DESK_FORWARD_NUMBER at the VA's cell or clear it".format(tail))
        else:
            put("inbound_forward", "ok", "inbound also rings …{}".format(tail))
    except Exception as e:
        put("inbound_forward", "warn", "forward check failed: " + type(e).__name__)

    # Paid-lead numbers: a number whose webhooks point at us but has no source
    # mapping tags every call "desk" — the ads are on and nothing is measurable.
    try:
        from leads import source_numbers
        mapped = source_numbers()
        google = _env("GOOGLE_LSA_NUMBER"); meta = _env("META_ADS_NUMBER")
        detail = {"google": ("…" + google[-4:]) if google else None, "meta": ("…" + meta[-4:]) if meta else None,
                  "mapped": len(mapped)}
        if google and meta:
            put("inbound_sources", "ok", "Google …{} and Meta …{} tag their calls".format(google[-4:], meta[-4:]), **detail)
        elif mapped:
            put("inbound_sources", "warn", "only {} paid number(s) mapped — set GOOGLE_LSA_NUMBER and META_ADS_NUMBER".format(len(mapped)), **detail)
        else:
            put("inbound_sources", "warn", "no paid numbers mapped — every call tags as desk; set GOOGLE_LSA_NUMBER / META_ADS_NUMBER on Render", **detail)
    except Exception as e:
        put("inbound_sources", "warn", "source check failed: " + type(e).__name__)

    put("sentry", "ok" if _env("SENTRY_DSN") else "warn",
        "configured" if _env("SENTRY_DSN") else "SENTRY_DSN not set — backend errors go unreported")

    fails = [k for k, v in checks.items() if v["state"] == "fail"]
    warns = [k for k, v in checks.items() if v["state"] == "warn"]
    state = "down" if fails else ("degraded" if warns else "ok")
    report = {"ok": not fails, "state": state, "fails": fails, "warns": warns, "checks": checks,
              "checked_at": datetime.now(timezone.utc).isoformat()}
    if alert:
        _alert_on_change(report)
    return report


def _alert_on_change(report):
    from models import DeskSetting
    key = "health:last_state"
    prev = DeskSetting.get(key) or "unknown"
    cur = report["state"]
    DeskSetting.put(key, cur)
    DeskSetting.put("health:last_report", json.dumps({"state": cur, "fails": report["fails"],
                                                       "warns": report["warns"], "at": report["checked_at"]}))
    if prev == cur:
        return
    if cur == "ok" and prev == "unknown":
        return
    lines = ["Call Desk line: {} → {}".format(prev, cur)]
    for name in report["fails"] + report["warns"]:
        c = report["checks"][name]
        lines.append("  {} {}: {}".format("✗" if c["state"] == "fail" else "△", name, c["reason"]))
    body = "\n".join(lines)
    logger.warning("desk health changed: %s", body)
    _send_alert("Umuve desk line {}".format(cur.upper()), body)


def _send_alert(subject, body):
    admin_email = _env("ADMIN_EMAIL")
    if admin_email:
        try:
            from notifications import _send_email_sync
            _send_email_sync(admin_email, subject, "<pre style='font:13px/1.5 monospace'>{}</pre>".format(body))
        except Exception:
            logger.exception("desk health email failed")
    hook = _env("SLACK_ALERT_WEBHOOK")
    if hook:
        try:
            import requests
            requests.post(hook, json={"text": "*{}*\n```{}```".format(subject, body)}, timeout=10)
        except Exception:
            logger.exception("desk health slack failed")
    try:
        from models import db, User, Notification, generate_uuid
        for admin in User.query.filter(User.role.in_(("admin", "manager"))).all():
            db.session.add(Notification(id=generate_uuid(), user_id=admin.id, type="desk_health",
                                        title=subject, body=body[:900], data={}))
        db.session.commit()
    except Exception:
        logger.exception("desk health notification failed")


def run_desk_health(app):
    with app.app_context():
        try:
            check_desk_health(alert=True)
        except Exception:
            logger.exception("desk health check crashed")
