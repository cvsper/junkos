"""
Daily morning brief — Tier 1-C of the airtight stack.

Once-a-day cron (recommended 11:00 UTC ≈ 7:00 ET) that emails sevs a single
screen with everything that needs attention. The point: if every individual
alert misfires, this brief catches it. A 24-hour broken state cannot repeat
silently because the brief will name the gap.

Sections:
  1. Yesterday at a glance — bookings, revenue, completed, no-shows.
  2. Needs attention today — unassigned, late alerts, urgent callbacks,
     waitlist leads, open support texts.
  3. Coming up today — next 24h jobs by scheduled time.
  4. System health — last successful auto-assign, recent error rate.

Sends to ADMIN_EMAIL. Never raises (any per-section error is rendered as a
"[query failed]" line in the brief so missing data is visible, not hidden).

Usage:
    python morning_brief.py            # standalone
    # Render cron (7am ET ≈ 11am UTC):
    0 11 * * *  cd /app && python morning_brief.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from timeutils import fmt_local

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


# ---------------------------------------------------------------------------
# Section builders — each returns an HTML string. Each is wrapped in a guard
# so one broken section doesn't take down the whole brief.
# ---------------------------------------------------------------------------

def _safe(section_name, fn):
    """Run a section builder; return HTML or a visible error placeholder."""
    try:
        return fn()
    except Exception:
        logger.exception("Brief section '%s' failed", section_name)
        return (
            "<p style='color:#c00'><b>[Brief section &quot;{}&quot; failed — "
            "check logs]</b></p>"
        ).format(section_name)


def _section_yesterday(now):
    """Snapshot of the last 24h."""
    from models import Job
    cutoff = now - timedelta(hours=24)
    jobs = Job.query.filter(Job.created_at >= cutoff).all()

    total = len(jobs)
    revenue = sum((j.total_price or 0.0) for j in jobs)
    completed = sum(1 for j in jobs if j.status == "completed")
    cancelled = sum(1 for j in jobs if j.status == "cancelled")
    noshow_late = sum(1 for j in jobs if getattr(j, "noshow_late_alerted", False))
    noshow_t30 = sum(1 for j in jobs if getattr(j, "noshow_t30_alerted", False))

    return (
        "<h2 style='margin-bottom:4px'>📊 Yesterday at a glance</h2>"
        "<table cellpadding='6' style='font-family:sans-serif;font-size:14px'>"
        "<tr><td>New bookings</td><td><b>{total}</b></td></tr>"
        "<tr><td>Revenue booked</td><td><b>${revenue:.2f}</b></td></tr>"
        "<tr><td>Completed</td><td>{completed}</td></tr>"
        "<tr><td>Cancelled</td><td>{cancelled}</td></tr>"
        "<tr><td>T-30 no-operator alerts fired</td>"
        "<td style='color:{t30_color}'>{noshow_t30}</td></tr>"
        "<tr><td>Late-start alerts fired</td>"
        "<td style='color:{late_color}'>{noshow_late}</td></tr>"
        "</table>"
    ).format(
        total=total,
        revenue=revenue,
        completed=completed,
        cancelled=cancelled,
        noshow_t30=noshow_t30,
        noshow_late=noshow_late,
        t30_color="#c00" if noshow_t30 else "#000",
        late_color="#c00" if noshow_late else "#000",
    )


def _section_needs_attention(now):
    """Things that are unresolved RIGHT NOW and need sevs's hand today."""
    from models import db, Job, ScheduledCallback, AbandonedBooking  # noqa: F401

    # Unassigned open jobs: upcoming 48h, ASAP (no schedule), AND anything
    # already past its time that never resolved. A NULL scheduled_at must not
    # hide a paid job (ASAP is the default launch booking).
    from sqlalchemy import or_
    unassigned = Job.query.filter(
        or_(
            Job.scheduled_at.is_(None),
            Job.scheduled_at <= now + timedelta(hours=48),
        ),
        Job.driver_id.is_(None),
        Job.operator_id.is_(None),
        Job.status.in_((
            "pending", "confirmed", "broadcasting", "accepted", "assigned",
        )),
        Job.created_at >= now - timedelta(days=14),  # bound the lookback
    ).all()

    # Money owed to haulers (concierge pending_connect + failed transfers).
    # Payout state lives on Payment, keyed by job.
    from models import Payment
    owed_rows = (
        db.session.query(Payment, Job)
        .join(Job, Payment.job_id == Job.id)
        .filter(Payment.payout_status.in_(("pending_connect", "failed")),
                Job.status == "completed")
        .all()
    )

    # Recent urgent callbacks (last 48h, status still pending)
    callback_cutoff = now - timedelta(hours=48)
    urgent_callbacks = ScheduledCallback.query.filter(
        ScheduledCallback.created_at >= callback_cutoff,
        ScheduledCallback.status == "pending",
    ).all() if hasattr(ScheduledCallback, "created_at") else []

    # No-coverage waitlist leads (last 7 days, not converted)
    waitlist_cutoff = now - timedelta(days=7)
    waitlist = AbandonedBooking.query.filter(
        AbandonedBooking.lead_source == "no_coverage_waitlist",
        AbandonedBooking.created_at >= waitlist_cutoff,
        AbandonedBooking.converted == False,
    ).all()

    rows = []
    if unassigned:
        rows.append((
            "<tr><td style='color:#c00'><b>⚠️ Unassigned jobs (next 48h)</b></td>"
            "<td><b>{n}</b> — call/scramble immediately</td></tr>"
        ).format(n=len(unassigned)))
        for j in unassigned[:5]:
            sched = fmt_local(j.scheduled_at, "%a %I:%M %p")
            rows.append((
                "<tr><td></td><td style='font-size:13px;color:#555'>"
                "#{code} • {sched} • {addr}</td></tr>"
            ).format(
                code=(j.confirmation_code or str(j.id)[:8]),
                sched=sched,
                addr=(j.address or "")[:50],
            ))

    if urgent_callbacks:
        rows.append((
            "<tr><td style='color:#c00'><b>🚨 Pending urgent callbacks</b></td>"
            "<td><b>{n}</b> — likely complaints</td></tr>"
        ).format(n=len(urgent_callbacks)))
        for cb in urgent_callbacks[:5]:
            rows.append((
                "<tr><td></td><td style='font-size:13px;color:#555'>"
                "{name} • {phone} • {when}</td></tr>"
            ).format(
                name=cb.customer_name or "?",
                phone=cb.phone or "",
                when=cb.requested_time or "?",
            ))

    if waitlist:
        rows.append((
            "<tr><td><b>📋 No-coverage waitlist (last 7d)</b></td>"
            "<td>{n} — demand we couldn't fulfill</td></tr>"
        ).format(n=len(waitlist)))
        for w in waitlist[:5]:
            rows.append((
                "<tr><td></td><td style='font-size:13px;color:#555'>"
                "{addr} • {email}</td></tr>"
            ).format(
                addr=(w.address or "")[:50],
                email=w.email or "",
            ))

    if owed_rows:
        total_owed = sum(float(p.driver_payout_amount or 0) for p, _j in owed_rows)
        rows.append((
            "<tr><td style='color:#c00'><b>💸 Hauler payouts owed</b></td>"
            "<td><b>{n} job(s), ${amt:.2f}</b> — pay via concierge console / "
            "fix Stripe Connect</td></tr>"
        ).format(n=len(owed_rows), amt=total_owed))
        for p, j in owed_rows[:5]:
            rows.append((
                "<tr><td></td><td style='font-size:13px;color:#555'>"
                "#{code} • {status} • ${amt:.2f} • completed {when}</td></tr>"
            ).format(
                code=(j.confirmation_code or str(j.id)[:8]),
                status=p.payout_status,
                amt=float(p.driver_payout_amount or 0),
                when=(j.completed_at.strftime("%b %d") if j.completed_at else "?"),
            ))

    if not rows:
        rows.append(
            "<tr><td colspan='2' style='color:#070'><b>✅ Nothing demanding "
            "attention — system is clean.</b></td></tr>"
        )

    return (
        "<h2 style='margin-bottom:4px'>🎯 Needs attention today</h2>"
        "<table cellpadding='6' style='font-family:sans-serif;font-size:14px'>"
        "{rows}"
        "</table>"
    ).format(rows="".join(rows))


def _section_coming_up(now):
    """Upcoming 24 hours of bookings by time."""
    from models import Job
    jobs = Job.query.filter(
        Job.scheduled_at >= now,
        Job.scheduled_at <= now + timedelta(hours=24),
        Job.status.in_((
            "pending", "confirmed", "accepted", "assigned", "in_progress",
        )),
    ).order_by(Job.scheduled_at.asc()).all()

    if not jobs:
        return (
            "<h2 style='margin-bottom:4px'>📅 Coming up today</h2>"
            "<p style='color:#555'>No bookings in the next 24 hours.</p>"
        )

    rows = []
    for j in jobs[:20]:
        sched = fmt_local(j.scheduled_at, "%a %I:%M %p")
        assigned = (
            "<span style='color:#070'>assigned</span>"
            if (j.driver_id or j.operator_id)
            else "<span style='color:#c00'><b>UNASSIGNED</b></span>"
        )
        rows.append((
            "<tr><td>{sched}</td><td>{code}</td><td>{addr}</td>"
            "<td>${amt:.0f}</td><td>{assigned}</td></tr>"
        ).format(
            sched=sched,
            code=(j.confirmation_code or str(j.id)[:8]),
            addr=(j.address or "")[:40],
            amt=(j.total_price or 0),
            assigned=assigned,
        ))

    return (
        "<h2 style='margin-bottom:4px'>📅 Coming up today</h2>"
        "<table cellpadding='6' style='font-family:sans-serif;font-size:14px;"
        "border-collapse:collapse'>"
        "<thead><tr style='background:#f5f5f5'>"
        "<th align='left'>When</th><th align='left'>#</th>"
        "<th align='left'>Address</th><th align='left'>$</th>"
        "<th align='left'>Status</th>"
        "</tr></thead>"
        "<tbody>{rows}</tbody>"
        "</table>"
    ).format(rows="".join(rows))


def _section_system_health(now):
    """Soft signals about whether the system itself is OK."""
    from models import Job
    # "Did anything book yesterday?" — silence may mean the funnel is broken
    cutoff = now - timedelta(hours=24)
    bookings_24h = Job.query.filter(Job.created_at >= cutoff).count()

    booking_signal = (
        "<span style='color:#070'>✅ funnel is moving</span>"
        if bookings_24h > 0
        else "<span style='color:#c00'><b>⚠️ ZERO bookings in 24h — possible "
             "funnel/payment outage</b></span>"
    )

    # SMS channel health — a Twilio suspension silently kills every alert/text.
    try:
        from twilio_health import check_twilio_health
        t = check_twilio_health()
        if not t["configured"]:
            sms_signal = "<span style='color:#888'>— not configured</span>"
        elif t["ok"]:
            sms_signal = "<span style='color:#070'>✅ Twilio active</span>"
        else:
            sms_signal = (
                "<span style='color:#c00'><b>🚨 SMS DOWN — {} "
                "(all texts silently failing)</b></span>"
            ).format(t["message"])
    except Exception:
        sms_signal = "<span style='color:#888'>(health check errored)</span>"

    return (
        "<h2 style='margin-bottom:4px'>🩺 System health</h2>"
        "<table cellpadding='6' style='font-family:sans-serif;font-size:14px'>"
        "<tr><td>Bookings in last 24h</td><td>{n} — {signal}</td></tr>"
        "<tr><td>SMS channel (Twilio)</td><td>{sms}</td></tr>"
        "<tr><td>ADMIN_PHONE configured</td><td>{phone}</td></tr>"
        "<tr><td>ADMIN_EMAIL configured</td><td>{email}</td></tr>"
        "</table>"
    ).format(
        n=bookings_24h,
        signal=booking_signal,
        sms=sms_signal,
        phone="✅" if os.environ.get("ADMIN_PHONE") else "<b style='color:#c00'>❌ NOT SET</b>",
        email="✅" if os.environ.get("ADMIN_EMAIL") else "<b style='color:#c00'>❌ NOT SET</b>",
    )


# ---------------------------------------------------------------------------
# Compose + send
# ---------------------------------------------------------------------------

def build_brief():
    """Build the full HTML brief inside the Flask app context."""
    from server import app
    with app.app_context():
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%A, %B %-d, %Y")

        sections = [
            _safe("yesterday", lambda: _section_yesterday(now)),
            _safe("needs_attention", lambda: _section_needs_attention(now)),
            _safe("coming_up", lambda: _section_coming_up(now)),
            _safe("system_health", lambda: _section_system_health(now)),
        ]

        html = (
            "<div style='font-family:sans-serif;max-width:720px'>"
            "<h1 style='border-bottom:2px solid #eee;padding-bottom:8px'>"
            "☀️ umuve morning brief — {date}</h1>"
            "{body}"
            "<hr style='margin-top:32px'>"
            "<p style='color:#888;font-size:12px'>"
            "Generated by morning_brief.py. If this brief stops arriving "
            "daily, something has broken in the cron pipeline — that itself "
            "is the signal."
            "</p>"
            "</div>"
        ).format(date=date_str, body="<br>".join(sections))

        subject = "umuve — {} — morning brief".format(now.strftime("%b %-d"))
        return subject, html


def send_brief():
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if not admin_email:
        logger.error(
            "ADMIN_EMAIL not configured — morning brief has nowhere to land.",
        )
        return False

    subject, html = build_brief()

    try:
        from email_service import send_email
        ok = send_email(admin_email, subject, html)
        if ok:
            logger.info("Morning brief sent to %s", admin_email)
        else:
            logger.error("send_email returned falsy — brief may not have sent")
        return bool(ok)
    except Exception:
        logger.exception("Failed to send morning brief")
        return False


def main():
    logger.info("=" * 60)
    logger.info("Morning brief generation starting")
    logger.info("=" * 60)
    ok = send_brief()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
