"""The booking page's drop-off, and the people in it worth calling.

`record()` takes one beacon from the page and keeps a single row per attempt.
`report()` is where the leak becomes visible: how many reached each step, and
how many saw a price and left. `open_leads()` hands the reachable ones to the
desk.

Nothing here messages a customer. It records, reports, and puts rows in front
of a person.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from models import db
from models_funnel import BookingFunnel, STEP_LABELS, LAST_STEP

logger = logging.getLogger(__name__)

# How long an attempt stays "in progress" before we call it abandoned. Someone
# mid-booking should not be phoned while they are still typing.
ABANDON_AFTER_MINUTES = 30
MAX_ITEMS = 60


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digits_of(v):
    d = re.sub(r"\D", "", str(v or ""))
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def _clean_step(v, default=1):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, LAST_STEP))


def _money(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 2) if 0 < f < 1_000_000 else None


def _text(v, limit):
    if v is None:
        return None
    s = str(v).strip()
    return s[:limit] or None


def _items(v):
    if not isinstance(v, list):
        return None
    out = []
    for i in v[:MAX_ITEMS]:
        if isinstance(i, dict):
            out.append({k: i.get(k) for k in ("category", "name", "quantity", "size")
                        if i.get(k) is not None})
        elif isinstance(i, str):
            out.append({"name": i[:80]})
    return out or None


def record(data, referrer=None, user_agent=None):
    """One beacon from the booking page. Returns the row, or None if unusable.

    Only ever moves `max_step` forward, so a visitor stepping back does not
    make the funnel look worse than it was.
    """
    session_id = _text(data.get("session_id") or data.get("sessionId"), 64)
    if not session_id:
        return None

    row = BookingFunnel.query.filter_by(session_id=session_id).first()
    created = row is None
    if created:
        row = BookingFunnel(session_id=session_id)
        db.session.add(row)

    step = _clean_step(data.get("step"), row.step if not created else 1)
    row.step = step
    row.max_step = max(step, row.max_step or 1)

    price = _money(data.get("quoted_price") or data.get("estimatedPrice"))
    if price is not None:
        row.quoted_price = price
    if data.get("quote_accepted") is not None:
        row.quote_accepted = bool(data.get("quote_accepted"))

    for field, key, limit in (("zip_code", "zip", 12), ("zip_code", "zip_code", 12),
                              ("address", "address", 2000), ("scheduled_for", "scheduled_for", 40),
                              ("name", "name", 160), ("phone", "phone", 40),
                              ("email", "email", 254), ("lead_source", "lead_source", 100),
                              ("lead_source", "leadSource", 100)):
        val = _text(data.get(key), limit)
        if val:
            setattr(row, field, val)

    items = _items(data.get("items"))
    if items:
        row.items = items
    if row.phone:
        row.phone_digits = digits_of(row.phone) or row.phone_digits
    if row.email:
        row.email = row.email.lower()

    if created:
        row.referrer = _text(referrer, 300)
        row.user_agent = _text(user_agent, 300)

    row.updated_at = _now()
    db.session.commit()
    return row


def mark_converted(session_id=None, job=None, phone=None, email=None):
    """This attempt became work. Never raises."""
    try:
        row = None
        if session_id:
            row = BookingFunnel.query.filter_by(session_id=str(session_id)[:64]).first()
        if row is None and (phone or email):
            q = BookingFunnel.query.filter(BookingFunnel.converted.is_(False))
            d = digits_of(phone)
            if d:
                row = q.filter(BookingFunnel.phone_digits == d).order_by(
                    BookingFunnel.updated_at.desc()).first()
            if row is None and email:
                row = q.filter(BookingFunnel.email == str(email).strip().lower()).order_by(
                    BookingFunnel.updated_at.desc()).first()
        if row is None:
            return None
        row.converted = True
        row.max_step = LAST_STEP
        if job is not None:
            row.job_id = getattr(job, "id", None)
        db.session.commit()
        return row
    except Exception:
        logger.exception("could not mark a booking funnel session converted")
        db.session.rollback()
        return None


def abandoned(days=30, priced_only=False, reachable_only=False, limit=200):
    """Attempts that stopped. Anyone still moving is left alone."""
    since = _now() - timedelta(days=max(1, min(int(days), 365)))
    cutoff = _now() - timedelta(minutes=ABANDON_AFTER_MINUTES)
    q = (BookingFunnel.query
         .filter(BookingFunnel.created_at >= since,
                 BookingFunnel.converted.is_(False),
                 BookingFunnel.updated_at <= cutoff))
    if priced_only:
        q = q.filter(BookingFunnel.quoted_price.isnot(None))
    rows = q.order_by(BookingFunnel.updated_at.desc()).limit(limit).all()
    if reachable_only:
        rows = [r for r in rows if r.reachable]
    return rows


def open_leads(days=14):
    """Priced, abandoned, and someone can actually ring them."""
    return abandoned(days=days, priced_only=True, reachable_only=True)


def report(days=30):
    """Where the booking page loses people.

    `reached` is cumulative — everyone whose furthest step was at least N — so
    the drop between two rows is the number who left on that step.
    """
    since = _now() - timedelta(days=max(1, min(int(days), 365)))
    rows = BookingFunnel.query.filter(BookingFunnel.created_at >= since).all()
    started = len(rows)
    booked = sum(1 for r in rows if r.converted)

    steps = []
    prev = None
    for n in range(1, LAST_STEP + 1):
        reached = sum(1 for r in rows if (r.max_step or 1) >= n)
        lost = None if prev is None else prev - reached
        steps.append({
            "step": n, "name": STEP_LABELS[n], "reached": reached,
            "lost_here": lost,
            "pct_of_start": round(100.0 * reached / started, 1) if started else 0.0,
        })
        prev = reached

    priced = [r for r in rows if r.quoted_price is not None]
    priced_lost = [r for r in priced if not r.converted]
    reachable_lost = [r for r in priced_lost if r.reachable]
    values = [r.quoted_price for r in priced if r.quoted_price]

    by_source = {}
    for r in rows:
        key = (r.lead_source or "direct").lower()
        s = by_source.setdefault(key, {"source": key, "started": 0, "priced": 0, "booked": 0})
        s["started"] += 1
        if r.quoted_price is not None:
            s["priced"] += 1
        if r.converted:
            s["booked"] += 1

    return {
        "days": days,
        "started": started,
        "booked": booked,
        "conversion": round(100.0 * booked / started, 1) if started else 0.0,
        "steps": steps,
        "saw_a_price": len(priced),
        "saw_a_price_and_left": len(priced_lost),
        "left_and_reachable": len(reachable_lost),
        "money_left_on_the_table": round(sum(r.quoted_price or 0 for r in priced_lost), 2),
        "avg_quote": round(sum(values) / len(values), 2) if values else None,
        "by_source": sorted(by_source.values(), key=lambda s: -s["started"]),
        "recoverable": [r.to_dict() for r in reachable_lost[:25]],
    }
