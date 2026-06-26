"""
No-coverage waitlist conversion.

When a customer tries to book in an area with no available hauler, the booking
funnel captures them as an AbandonedBooking(lead_source="no_coverage_waitlist")
and tells them we'll reach out. This module makes that promise real:

  1. send_holding_email() — an immediate branded "you're on the list" email so a
     guest who closes the tab is still captured (not just an inline API message).
  2. notify_waitlist_for_coverage() — when a hauler comes online near those
     customers, email them "we're live in your area, book now" exactly once.

Both are best-effort and never raise into the request path.
"""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BOOK_URL = os.environ.get("CUSTOMER_BOOK_URL", "https://app.goumuve.com/book")
_RED = "#C52222"


def _now():
    return datetime.now(timezone.utc)


def _shell(title, body_html, cta_label=None, cta_url=None):
    cta = ""
    if cta_label and cta_url:
        cta = (
            '<a href="{url}" style="display:inline-block;background:{red};color:#fff;'
            'text-decoration:none;font-weight:700;padding:13px 26px;border-radius:10px;'
            'font-size:15px;margin-top:6px">{label}</a>'
        ).format(url=cta_url, red=_RED, label=cta_label)
    return (
        '<div style="background:#FAF8F5;padding:32px 0;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:16px;'
        'overflow:hidden;border:1px solid #ece8e1">'
        '<div style="background:{red};padding:18px 28px"><span style="color:#fff;'
        'font-size:20px;font-weight:800;letter-spacing:-.02em">Umuve</span></div>'
        '<div style="padding:28px">'
        '<h1 style="font-size:21px;color:#1a1a1a;margin:0 0 12px;letter-spacing:-.01em">{title}</h1>'
        '<div style="font-size:15px;color:#444;line-height:1.55">{body}</div>'
        '<div style="margin-top:22px">{cta}</div>'
        '</div>'
        '<div style="padding:16px 28px;border-top:1px solid #f0ece5;color:#9a948b;'
        'font-size:12px">Umuve — junk removal with the price up front.</div>'
        '</div></div>'
    ).format(red=_RED, title=title, body=body_html, cta=cta)


def send_holding_email(email, name, address=None):
    """Immediate confirmation that a no-coverage customer is on the waitlist."""
    if not email:
        return False
    first = (name or "").split(" ")[0] if name else "there"
    where = " at <b>{}</b>".format(address) if address else " in your area"
    body = (
        "Hi {first}, thanks for choosing Umuve. We don't have a hauler free{where} "
        "<b>right this second</b>, but you're in our service zone — so we've saved "
        "your request and put you at the front of the line.<br><br>"
        "<b>You haven't been charged.</b> The moment a truck is available near you, "
        "we'll email you to lock in a time. Most areas open up within a couple of hours."
    ).format(first=first, where=where)
    try:
        from notifications import send_email
        send_email(email, "You're on the Umuve waitlist — we'll be in touch soon", _shell(
            "You're on the list 🚛", body))
        return True
    except Exception:
        logger.warning("waitlist: holding email failed for %s", email)
        return False


def notify_waitlist_for_coverage(app, lat, lng, radius_miles=30.0, limit=200):
    """Email no-coverage waitlist customers within ``radius_miles`` of (lat,lng)
    that we're now live in their area. Idempotent via waitlist_notified_at.

    Returns {"notified": n, "emails": [...]}. Runs in its own app context.
    """
    if lat is None or lng is None:
        return {"notified": 0, "emails": []}
    try:
        lat = float(lat); lng = float(lng)
    except (TypeError, ValueError):
        return {"notified": 0, "emails": []}

    with app.app_context():
        from models import db, AbandonedBooking
        from dispatcher import haversine

        candidates = (
            db.session.query(AbandonedBooking)
            .filter(
                AbandonedBooking.lead_source == "no_coverage_waitlist",
                AbandonedBooking.converted.is_(False),
                AbandonedBooking.waitlist_notified_at.is_(None),
                AbandonedBooking.waitlist_lat.isnot(None),
                AbandonedBooking.waitlist_lng.isnot(None),
            )
            .limit(1000)
            .all()
        )

        notified, emails = 0, []
        for lead in candidates:
            try:
                if haversine(lat, lng, float(lead.waitlist_lat), float(lead.waitlist_lng)) > radius_miles:
                    continue
            except Exception:
                continue
            if _send_live_email(lead):
                lead.waitlist_notified_at = _now()
                notified += 1
                emails.append(lead.email)
            if notified >= limit:
                break
        db.session.commit()
        if notified:
            logger.info("waitlist: notified %d customers near (%.4f, %.4f)", notified, lat, lng)
        return {"notified": notified, "emails": emails}


def _send_live_email(lead):
    if not lead.email:
        return False
    first = (lead.name or "").split(" ")[0] if lead.name else "there"
    price = ""
    if lead.estimated_price:
        try:
            price = " Your estimate was <b>${:.0f}</b>, locked in.".format(float(lead.estimated_price))
        except (TypeError, ValueError):
            price = ""
    body = (
        "Good news, {first} — we've got a hauler available in your area now! 🎉<br><br>"
        "You asked us about junk removal{addr} and we couldn't reach you a truck at "
        "the time. That's changed.{price}<br><br>"
        "Tap below to pick a time — same transparent, up-front price, no surprises."
    ).format(
        first=first,
        addr=(" at {}".format(lead.address) if lead.address else ""),
        price=price,
    )
    try:
        from notifications import send_email
        send_email(lead.email, "We're now serving your area — book your Umuve haul", _shell(
            "We're live in your area 🚛", body, cta_label="Book my haul", cta_url=BOOK_URL))
        return True
    except Exception:
        logger.warning("waitlist: live email failed for %s", lead.email)
        return False
