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

    sig = _text(data.get("signal"), 40)
    if sig:
        row.signals = _merge_signal(row.signals, sig, data)

    row.updated_at = _now()
    db.session.commit()
    return row


# The address step is where most visitors leave. These say what they did
# there before they went: nothing, typed, saw suggestions, picked one, or
# hit a wall (no suggestions for what they typed, a fetch error, or our own
# validation). The page posts one small beacon per event.
SIGNALS = ("typed", "suggestions", "no_suggestions", "picked", "fetch_failed", "rejected")


def _merge_signal(current, sig, data):
    out = dict(current or {})
    if sig not in SIGNALS:
        return out
    out[sig] = int(out.get(sig) or 0) + 1
    if sig == "suggestions":
        try:
            n = int(data.get("count") or 0)
        except (TypeError, ValueError):
            n = 0
        out["suggestions_max"] = max(int(out.get("suggestions_max") or 0), n)
    if sig == "no_suggestions":
        q = _text(data.get("query"), 60)
        if q:
            out["no_suggestions_query"] = q
    if sig == "rejected":
        why = _text(data.get("reason"), 80)
        if why:
            out["rejected_reason"] = why
    return out


def address_step(rows):
    """What people did on the address step, split by whether they got past
    it. The interesting column is the ones who left: did they never type,
    type and get nothing back, or pick an address and still not continue?"""
    def tally(group):
        t = {"visitors": len(group), "untouched": 0, "typed": 0, "saw_suggestions": 0,
             "no_suggestions": 0, "picked": 0, "fetch_failed": 0, "rejected": 0}
        for r in group:
            sg = r.signals or {}
            if not sg.get("typed"):
                t["untouched"] += 1
                continue
            t["typed"] += 1
            if sg.get("suggestions"):
                t["saw_suggestions"] += 1
            if sg.get("no_suggestions"):
                t["no_suggestions"] += 1
            if sg.get("picked"):
                t["picked"] += 1
            if sg.get("fetch_failed"):
                t["fetch_failed"] += 1
            if sg.get("rejected"):
                t["rejected"] += 1
        return t
    left = [r for r in rows if (r.max_step or 1) < 2]
    passed = [r for r in rows if (r.max_step or 1) >= 2]
    queries, reasons = {}, {}
    for r in left:
        sg = r.signals or {}
        q = sg.get("no_suggestions_query")
        if q:
            queries[q] = queries.get(q, 0) + 1
        why = sg.get("rejected_reason")
        if why:
            reasons[why] = reasons.get(why, 0) + 1
    return {
        "left_here": tally(left),
        "got_past": tally(passed),
        "no_suggestion_queries": sorted(queries.items(), key=lambda kv: -kv[1])[:15],
        "rejected_reasons": sorted(reasons.items(), key=lambda kv: -kv[1])[:10],
        "instrumented_since": "2026-09-21",
    }


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


def forget(session_id):
    """Drop one row — a smoke test, or a session recorded in error.

    An analytics table nobody can correct becomes an analytics table nobody
    trusts, and a single synthetic row skews a funnel this small.
    """
    row = BookingFunnel.query.filter_by(session_id=str(session_id)[:64]).first()
    if row is None:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


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


# --------------------------------------------------------------------------
# Who the visitors are
# --------------------------------------------------------------------------
# The booking page is the only place we can see a visitor without a third
# party: the beacon carries their zip, and the request carries the browser
# and where they came from. That is enough for "who, where, on what, when,
# and how far they got", which is what a person asks before touching an ad.

# Three-digit zip prefixes for the seven coastal counties we serve.
_ZIP_COUNTY = {
    "330": "Miami-Dade", "331": "Miami-Dade", "332": "Miami-Dade",
    "333": "Broward", "334": "Palm Beach",
    "349": "Martin / St. Lucie", "329": "Brevard / Indian River",
}
_CITY_OF_ZIP = {
    "334": "West Palm Beach area", "333": "Fort Lauderdale area",
    "330": "Miami / Hialeah", "331": "Miami", "332": "Miami",
    "349": "Stuart / Port St. Lucie", "329": "Melbourne / Vero Beach",
}
# Florida runs 320-349; anything else is a visitor we cannot serve.
_FL_PREFIXES = {str(n) for n in range(320, 350)}

# The time of day people book is only meaningful in their clock, not UTC.
_ET_OFFSET_HOURS = -4


def county_of_zip(zip_code):
    z = re.sub(r"\D", "", zip_code or "")[:3]
    if not z:
        return None
    if z in _ZIP_COUNTY:
        return _ZIP_COUNTY[z]
    return "Florida, outside service area" if z in _FL_PREFIXES else "Outside Florida"


def device_of(user_agent):
    """Phone / tablet / desktop, plus whether it was Meta's in-app browser.

    The in-app flag matters more than the OS: a visitor inside Facebook's or
    Instagram's browser is one tap from an ad, on a webview that drops cookies
    and autofill, and that is where most of our paid traffic lands.
    """
    ua = (user_agent or "")
    low = ua.lower()
    in_app = None
    if "instagram" in low:
        in_app = "Instagram"
    elif "fban" in low or "fbav" in low or "fb_iab" in low:
        in_app = "Facebook"
    if "ipad" in low or ("android" in low and "mobile" not in low):
        kind = "tablet"
    elif "iphone" in low or "android" in low or "mobile" in low:
        kind = "phone"
    elif not ua:
        kind = "unknown"
    else:
        kind = "desktop"
    if "iphone" in low or "ipad" in low:
        os_name = "iOS"
    elif "android" in low:
        os_name = "Android"
    elif "windows" in low:
        os_name = "Windows"
    elif "mac os" in low or "macintosh" in low:
        os_name = "Mac"
    else:
        os_name = "other"
    return {"kind": kind, "os": os_name, "in_app": in_app}


def referrer_host(referrer):
    m = re.match(r"^\s*https?://([^/?#]+)", referrer or "")
    if not m:
        return "direct"
    host = m.group(1).lower()
    if host.startswith("www."):
        host = host[4:]
    if host.endswith("goumuve.com"):
        return "goumuve.com"
    if "facebook.com" in host or host.startswith("l.") or host.startswith("lm."):
        return "facebook"
    if "instagram.com" in host:
        return "instagram"
    if "google." in host:
        return "google"
    return host


def _bucket(counter, key, row, reached_two, priced):
    b = counter.setdefault(key, {"key": key, "visitors": 0, "past_address": 0,
                                 "saw_a_price": 0, "booked": 0})
    b["visitors"] += 1
    if reached_two:
        b["past_address"] += 1
    if priced:
        b["saw_a_price"] += 1
    if row.converted:
        b["booked"] += 1
    return b


def _finish(counter, limit=None):
    out = sorted(counter.values(), key=lambda b: -b["visitors"])
    for b in out:
        v = b["visitors"]
        b["past_address_pct"] = round(100.0 * b["past_address"] / v, 1) if v else 0.0
    return out[:limit] if limit else out


def visitors(rows):
    """Everything the funnel rows say about who came, in one shape.

    Each breakdown carries the same four counts so any slice can be compared
    to any other: how many came, how many got past the address step, how many
    saw a price, how many booked.
    """
    by_county, by_zip, by_device, by_os, by_in_app = {}, {}, {}, {}, {}
    by_referrer, by_hour, by_weekday, by_source = {}, {}, {}, {}
    with_zip = 0
    for r in rows:
        reached_two = (r.max_step or 1) >= 2
        priced = r.quoted_price is not None
        d = device_of(r.user_agent)
        _bucket(by_device, d["kind"], r, reached_two, priced)
        _bucket(by_os, d["os"], r, reached_two, priced)
        _bucket(by_in_app, d["in_app"] or "regular browser", r, reached_two, priced)
        _bucket(by_referrer, referrer_host(r.referrer), r, reached_two, priced)
        _bucket(by_source, (r.lead_source or "direct").lower(), r, reached_two, priced)
        county = county_of_zip(r.zip_code)
        if county:
            with_zip += 1
            _bucket(by_county, county, r, reached_two, priced)
            _bucket(by_zip, re.sub(r"\D", "", r.zip_code)[:5], r, reached_two, priced)
        when = r.created_at + timedelta(hours=_ET_OFFSET_HOURS)
        _bucket(by_hour, when.hour, r, reached_two, priced)
        _bucket(by_weekday, when.strftime("%a"), r, reached_two, priced)

    hours = _finish(by_hour)
    hours.sort(key=lambda b: b["key"])
    order = {d: i for i, d in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])}
    weekdays = _finish(by_weekday)
    weekdays.sort(key=lambda b: order.get(b["key"], 9))
    return {
        "total": len(rows),
        "with_zip": with_zip,
        "by_county": _finish(by_county),
        "by_zip": _finish(by_zip, limit=15),
        "by_device": _finish(by_device),
        "by_os": _finish(by_os),
        "by_in_app_browser": _finish(by_in_app),
        "by_referrer": _finish(by_referrer, limit=10),
        "by_source": _finish(by_source),
        "by_hour_et": hours,
        "by_weekday": weekdays,
        "address_step": address_step(rows),
    }


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

    # Someone who saw a price two minutes ago has not walked away — they are
    # probably typing their card in. Only a session that has sat still for
    # ABANDON_AFTER_MINUTES counts as lost, which is the same rule the desk
    # lead queue uses, so the page and the call list never disagree.
    idle_before = _now() - timedelta(minutes=ABANDON_AFTER_MINUTES)
    priced = [r for r in rows if r.quoted_price is not None]
    still_going = [r for r in priced
                   if not r.converted and (r.updated_at or r.created_at) > idle_before]
    priced_lost = [r for r in priced
                   if not r.converted and (r.updated_at or r.created_at) <= idle_before]
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
        "still_booking": len(still_going),
        "saw_a_price_and_left": len(priced_lost),
        "left_and_reachable": len(reachable_lost),
        "money_left_on_the_table": round(sum(r.quoted_price or 0 for r in priced_lost), 2),
        "avg_quote": round(sum(values) / len(values), 2) if values else None,
        "by_source": sorted(by_source.values(), key=lambda s: -s["started"]),
        "recoverable": [r.to_dict() for r in reachable_lost[:25]],
        "visitors": visitors(rows),
    }
