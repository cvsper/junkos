"""Text a photo, get a firm price in minutes.

The promise, exactly: **the price we text is the price you pay for what is in
the photo.** Anything not in the photo is priced before it goes on the truck,
and the customer approves it first. That is a real commitment, so this module
is built to be careful rather than clever:

  * the category list the vision model is allowed to use is generated FROM the
    live price table, so it can never name a category we cannot price (the old
    prompt asked for "sectional" — not a real key — and quoted $119 for a
    $193 sofa_sectional, a 38% underquote on a "firm" number);
  * the model reports its own confidence and what it could not see, and a
    quote it is unsure about goes to Tracy instead of out the door;
  * every quote is a row, so the two questions (stairs, anything not pictured)
    can be answered later, Tracy can see who never booked, and the quoted
    price can be checked against what the job actually billed.

Entry points:
    handle_photos(phone, body, media_urls)   an MMS arrived
    handle_reply(phone, body)                a text arrived that answers one
    desk_leads(since)                        rows for the desk's lead list
    record_final(job)                        drift, once a job is priced for real
"""
from __future__ import annotations

import base64
import json
import logging
import os
import random
import re
import string
from datetime import datetime, timedelta, timezone

from models import db
from models_quote import PhotoQuote

logger = logging.getLogger(__name__)

SOURCE = "photo"
OPEN_STATUSES = ("new", "quoted", "needs_human", "answered")
REPLY_WINDOW_HOURS = 48
# Below this the model is guessing, and a guess must never go out as a firm price.
MIN_CONFIDENCE = float(os.environ.get("PHOTO_QUOTE_MIN_CONFIDENCE", "0.72"))
MODEL = os.environ.get("PHOTO_QUOTE_MODEL", "claude-haiku-4-5-20251001")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _env(k):
    return (os.environ.get(k) or "").strip()


def digits_of(v):
    d = "".join(ch for ch in str(v or "") if ch.isdigit())
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d if len(d) == 10 else ""


def _ref():
    alphabet = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"
    for _ in range(12):
        code = "".join(random.choice(alphabet) for _ in range(6))
        if not PhotoQuote.query.filter_by(ref=code).first():
            return code
    return "Q" + datetime.now(timezone.utc).strftime("%H%M%S")


# ---------------------------------------------------------------------------
# categories: whatever we can price, and nothing else
# ---------------------------------------------------------------------------
# Words a vision model reaches for, mapped onto the key the price table uses.
SYNONYMS = {
    "sectional": "sofa_sectional", "couch": "sofa", "loveseat": "sofa", "sleeper_sofa": "sofa_sleeper",
    "sofabed": "sofa_sleeper", "sofa_bed": "sofa_sleeper", "recliner": "chair_recliner",
    "armchair": "chair_recliner", "chair": "chair_office", "office_chair": "chair_office",
    "dining_table": "table_dining", "kitchen_table": "table_kitchen", "coffee_table": "table_coffee",
    "end_table": "table_end", "side_table": "table_end", "conference_table": "table_conference",
    "dining_chairs": "table_dining_chairs", "desk": "desk_large", "small_desk": "desk_small",
    "tv": "tv_flatscreen", "television": "tv_flatscreen", "flat_screen": "tv_flatscreen",
    "flatscreen": "tv_flatscreen", "tv_stand_unit": "tv_stand", "media_console": "tv_console",
    "fridge": "refrigerator", "mini_fridge": "refrigerator_bar", "freezer": "freezer_upright",
    "stove_oven": "stove", "oven": "stove", "range": "stove", "washing_machine": "washer",
    "washer_dryer": "washer_dryer_set", "appliance": "appliances",
    "boxspring": "box_spring", "bed": "bed_frame", "headboard": "bed_frame",
    "bookshelf": "bookcase", "shelf": "bookcase", "shelving": "bookcase",
    "wardrobe": "cabinet", "armoire": "cabinet", "chest_of_drawers": "dresser",
    "exercise_bike": "bike_stationary", "stationary_bike": "bike_stationary", "bicycle": "bike",
    "grill": "bbq_grill", "bbq": "bbq_grill", "lawnmower": "lawn_mower_push",
    "push_mower": "lawn_mower_push", "riding_mower": "lawn_mower_riding",
    "yard_debris": "yard_waste", "brush": "yard_waste", "branches": "yard_waste",
    "construction_debris": "construction", "debris": "construction", "wood": "construction",
    "boxes": "general", "bags": "general", "trash": "general", "junk": "general",
    "clothes": "general", "misc": "general", "miscellaneous": "general", "household": "general",
    "monitor": "computer", "pc": "computer", "laptop": "computer", "electronic": "electronics",
}


def price_categories():
    try:
        from routes.booking import CATEGORY_PRICES
        return sorted(CATEGORY_PRICES)
    except Exception:
        logger.exception("could not read the price table")
        return ["general"]


def normalize_category(raw):
    """Anything the model says → a key the price table actually has."""
    key = re.sub(r"[^a-z0-9]+", "_", str(raw or "").strip().lower()).strip("_")
    if not key:
        return "general"
    real = set(price_categories())
    if key in real:
        return key
    if key in SYNONYMS and SYNONYMS[key] in real:
        return SYNONYMS[key]
    singular = key[:-1] if key.endswith("s") else key
    if singular in real:
        return singular
    if singular in SYNONYMS and SYNONYMS[singular] in real:
        return SYNONYMS[singular]
    # "brown leather sectional" → the longest real key it contains
    hits = [k for k in real if k != "general" and k in key]
    if hits:
        return max(hits, key=len)
    hits = [v for k, v in SYNONYMS.items() if k in key and v in real]
    if hits:
        return max(hits, key=len)
    return "general"


def _prompt(body_text):
    cats = ", ".join(price_categories())
    p = (
        "You price junk removal for Umuve from customer photos. The number we send is a FIRM "
        "price the customer will be held to, so be accurate and say when you are unsure.\n\n"
        "Identify every item that would be hauled away. Use ONLY these category values:\n"
        + cats + "\n\n"
        "Return ONLY JSON, no markdown:\n"
        '{"items":[{"category":"sofa_sectional","quantity":1,"description":"grey sectional",'
        '"confidence":0.9}],"confidence":0.86,"stairs":false,"unclear":["a pile behind the sofa is cut off"]}\n\n'
        "Rules:\n"
        "- confidence is 0-1 for the whole read. Use below 0.7 when the photo is dark, "
        "cluttered, partly out of frame, or you are guessing at quantity.\n"
        "- unclear: short plain sentences about anything you cannot price with confidence. "
        "Empty list when the photo is clear.\n"
        "- stairs: true only if the photo clearly shows the items are up or down stairs.\n"
        "- Loose bags, boxes and small household clutter are 'general' — one entry, quantity = "
        "roughly how many items.\n"
        "- Do not invent items you cannot see. Do not guess to fill the list."
    )
    if body_text:
        p += "\n\nThe customer wrote: \"{}\"".format(str(body_text)[:300])
    return p


def _fetch_images(media_urls, limit=4):
    import requests
    sid, token = _env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN")
    out = []
    for url in (media_urls or [])[:limit]:
        try:
            r = requests.get(url, auth=(sid, token) if sid else None, timeout=20)
            if r.status_code != 200 or not r.content:
                logger.warning("photo quote: media %s came back %s", url[-24:], r.status_code)
                continue
            ctype = (r.headers.get("Content-Type") or "image/jpeg").split(";")[0]
            if not ctype.startswith("image/"):
                continue
            out.append({"type": "image", "source": {"type": "base64", "media_type": ctype,
                                                    "data": base64.standard_b64encode(r.content).decode()}})
        except Exception:
            logger.exception("photo quote: could not fetch media")
    return out


def _json_from(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[:-3]
    t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None


def analyze(media_urls, body_text=""):
    """→ {items, confidence, stairs, unclear} or None when vision is unavailable."""
    key = _env("ANTHROPIC_API_KEY")
    if not key:
        logger.warning("photo quote: no ANTHROPIC_API_KEY")
        return None
    images = _fetch_images(media_urls)
    if not images:
        return {"items": [], "confidence": 0.0, "stairs": False, "unclear": ["the photo did not load"]}
    import requests
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={"model": MODEL, "max_tokens": 700, "temperature": 0.1,
                  "messages": [{"role": "user", "content": [*images, {"type": "text", "text": _prompt(body_text)}]}]},
            timeout=45)
    except Exception:
        logger.exception("photo quote: vision call failed")
        return None
    if r.status_code != 200:
        logger.error("photo quote: vision %s %s", r.status_code, r.text[:200])
        return None
    try:
        text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    except Exception:
        logger.exception("photo quote: unreadable vision response")
        return None
    data = _json_from(text)
    if not isinstance(data, dict):
        return {"items": [], "confidence": 0.0, "stairs": False, "unclear": ["could not read the photo"]}

    items = []
    for it in (data.get("items") or []):
        if not isinstance(it, dict):
            continue
        try:
            qty = max(1, min(60, int(float(it.get("quantity", 1)))))
        except Exception:
            qty = 1
        items.append({"category": normalize_category(it.get("category")), "quantity": qty,
                      "description": str(it.get("description") or "").strip()[:80] or None,
                      "confidence": _f(it.get("confidence"))})
    unclear = [str(u)[:160] for u in (data.get("unclear") or []) if str(u).strip()][:4]
    conf = _f(data.get("confidence"))
    if conf is None:
        per = [i["confidence"] for i in items if i["confidence"] is not None]
        conf = min(per) if per else (0.8 if items else 0.0)
    return {"items": items, "confidence": conf, "stairs": bool(data.get("stairs")), "unclear": unclear}


def _f(v):
    try:
        f = float(v)
        return max(0.0, min(1.0, f))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# pricing + wording
# ---------------------------------------------------------------------------
def price(items, addons=None):
    from routes.booking import calculate_estimate
    rows = [{"category": i["category"], "quantity": i["quantity"]} for i in items if i.get("quantity")]
    if not rows:
        return None
    est = calculate_estimate(rows, addons=addons or None)
    return est


def _line(item):
    name = item.get("description") or item["category"].replace("_", " ")
    qty = item.get("quantity", 1)
    return "• {}{}".format(name, " x{}".format(qty) if qty > 1 else "")


def _book_url(q):
    base = (_env("FRONTEND_URL") or "https://app.goumuve.com").rstrip("/")
    return "{}/book?q={}".format(base, q.ref)


def quote_text(q):
    """The promise, in the customer's hands."""
    lines = [_line(i) for i in (q.items or [])][:6]
    extra = len(q.items or []) - len(lines)
    if extra > 0:
        lines.append("• plus {} more".format(extra))
    stairs = (q.addons or {}).get("stair_flights") or 0
    msg = ["Umuve — your price for what's in the photo:", ""]
    msg += lines
    msg += ["", "${:.0f} all in. Labor, hauling, dump fees, taxes — nothing added on the day."
            .format(q.price or 0)]
    if stairs:
        msg[-1] += " Includes the stairs."
    msg += ["", "That price holds for what I can see. Anything not pictured we price and you "
                "approve before it goes on the truck."]
    if not q.asked:
        msg += ["", "Two things so nothing changes on the day: any stairs, and anything not in "
                    "the photo? Reply here and I'll lock it in."]
    msg += ["", "Book: " + _book_url(q), "Reply STOP to opt out."]
    return "\n".join(msg)


def holding_text(q):
    """Low confidence: a person prices it. Never send a guess as a firm price."""
    va = (_env("DESK_VA_NAME") or "Tracy").split()[0]
    return ("Umuve — got your photo, thanks. I want to give you a firm price rather than a guess, "
            "so {} is looking at it now and will text your number in a few minutes. "
            "If there's anything not in the photo, send it over and it'll be included. "
            "Reply STOP to opt out.".format(va))


# ---------------------------------------------------------------------------
# the flow
# ---------------------------------------------------------------------------
def open_quote_for(digits, hours=REPLY_WINDOW_HOURS):
    return (PhotoQuote.query
            .filter(PhotoQuote.phone_digits == digits,
                    PhotoQuote.status.in_(OPEN_STATUSES),
                    PhotoQuote.created_at >= _now() - timedelta(hours=hours))
            .order_by(PhotoQuote.created_at.desc()).first())


def _send(digits, body):
    try:
        from sms_service import send_sms_async
        send_sms_async("+1" + digits, body)
        return True
    except Exception:
        logger.exception("photo quote: could not text %s", digits[-4:])
        return False


def _alert(q, why):
    try:
        from booking_alerts import _phones
        phones = _phones()
    except Exception:
        phones = []
    head = "Photo quote · {}".format(why)
    body = "\n".join([head,
                      "{} · {}".format(q.phone_digits, q.name or "no name"),
                      ", ".join(i["category"] for i in (q.items or [])[:6]) or "nothing identified",
                      "Quoted ${:.0f}".format(q.price) if q.price else "not priced",
                      "; ".join(q.unclear or []),
                      "Desk: {}/va/calls".format(_env("DESK_PUBLIC_URL") or "https://ops.goumuve.com")])
    for p in phones:
        try:
            from sms_service import send_sms_async
            send_sms_async(p, body)
        except Exception:
            logger.exception("photo quote alert sms failed")
    hook = _env("SLACK_ALERT_WEBHOOK")
    if hook:
        try:
            import requests
            requests.post(hook, json={"text": "*{}*\n```{}```".format(head, body)}, timeout=10)
        except Exception:
            logger.exception("photo quote alert slack failed")


def handle_photos(phone, body_text, media_urls):
    """An MMS arrived. Returns the PhotoQuote, or None when we couldn't take it."""
    digits = digits_of(phone)
    if not digits:
        return None
    started = _now()
    q = PhotoQuote(ref=_ref(), phone_digits=digits, media_urls=list(media_urls or []),
                   body=(body_text or "")[:1000], status="new")
    try:
        from inbound import find_customer
        c = find_customer(digits)
        if c and getattr(c, "name", None):
            q.name = c.name
    except Exception:
        pass
    db.session.add(q)
    db.session.commit()

    read = analyze(media_urls, body_text)
    if read is None:                                   # vision is down — a person handles it
        q.status = "needs_human"
        q.unclear = ["photo pricing is offline"]
        db.session.commit()
        _send(digits, holding_text(q))
        _alert(q, "vision unavailable — price it by hand")
        return q

    q.items = read["items"]
    q.confidence = read["confidence"]
    q.unclear = read["unclear"]
    addons = {"stair_flights": 1} if read.get("stairs") else {}
    est = price(q.items, addons) if q.items else None
    if est:
        q.addons = addons
        q.price = round(float(est.get("total") or 0), 2)
        q.breakdown = {k: est.get(k) for k in ("items_subtotal", "service_fee", "disposal_fee",
                                               "volume_discount", "surge_amount", "total")}
    q.seconds_to_quote = int((_now() - started).total_seconds())

    sure = est and q.items and (q.confidence or 0) >= MIN_CONFIDENCE and not read["unclear"]
    if sure:
        q.status = "quoted"
        q.sent_at = _now()
        body = quote_text(q)          # composed while `asked` is still False, so
        q.asked = True                # the two questions go out with the price
        db.session.commit()
        _send(digits, body)
        _alert(q, "firm price sent")
    else:
        q.status = "needs_human"
        db.session.commit()
        _send(digits, holding_text(q))
        _alert(q, "needs a human price ({})".format(
            "nothing identified" if not q.items else
            "unclear: " + "; ".join(read["unclear"]) if read["unclear"] else
            "confidence {:.2f}".format(q.confidence or 0)))
    return q


_STAIR_RE = re.compile(r"\b(\d+)\s*(?:nd|rd|th|st)?\s*(?:floor|flight|story|storey)\b|\b(second|third|fourth|2nd|3rd|4th)\s*floor\b", re.I)
_NO_RE = re.compile(r"^\s*(no|nope|nothing|that'?s it|thats it|all of it|just that|no stairs|ground floor|first floor)\b", re.I)
_WORD_FLOOR = {"second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3}


def parse_answer(text):
    """Their reply → {stair_flights, more_text}. Cheap and literal; the model
    re-reads it only when there is something we could not parse."""
    t = (text or "").strip()
    out = {"stair_flights": 0, "more": None}
    if not t:
        return out
    if _NO_RE.match(t):
        return out
    m = _STAIR_RE.search(t)
    if m:
        if m.group(1):
            try:
                out["stair_flights"] = max(0, min(6, int(m.group(1)) - 1))
            except Exception:
                pass
        elif m.group(2):
            out["stair_flights"] = _WORD_FLOOR.get(m.group(2).lower(), 1)
    elif re.search(r"\bstairs?\b", t, re.I) and not re.search(r"\bno stairs?\b", t, re.I):
        out["stair_flights"] = 1
    # anything that is not purely a stairs answer may name extra items
    stripped = _STAIR_RE.sub(" ", t)
    stripped = re.sub(r"\b(stairs?|elevator|floor|yes|no|and|also|plus|there'?s|theres|a|an|the)\b", " ", stripped, flags=re.I)
    if len(re.sub(r"[^a-z]", "", stripped.lower())) >= 3:
        out["more"] = t[:300]
    return out


def handle_reply(phone, body_text):
    """A text with no photo. If it answers an open quote, re-price and re-send.
    Returns the quote when it was handled, else None so normal routing continues."""
    digits = digits_of(phone)
    if not digits or not (body_text or "").strip():
        return None
    q = open_quote_for(digits)
    if q is None:
        return None
    ans = parse_answer(body_text)
    q.answer_text = (body_text or "")[:1000]
    q.answered_at = _now()

    if q.status == "needs_human":
        # a person still owes them the number; just capture it and tell the desk
        db.session.commit()
        _alert(q, "customer replied while waiting for a price")
        return q

    if ans["more"]:
        # they named something we cannot see — a person prices the difference
        q.status = "needs_human"
        db.session.commit()
        _alert(q, "extra items in their reply: " + ans["more"][:120])
        va = (_env("DESK_VA_NAME") or "Tracy").split()[0]
        _send(digits, "Got it — {} will add that and text your updated firm price in a few "
                      "minutes. Reply STOP to opt out.".format(va))
        return q

    addons = dict(q.addons or {})
    if ans["stair_flights"]:
        addons["stair_flights"] = ans["stair_flights"]
    est = price(q.items or [], addons)
    if not est:
        db.session.commit()
        return q
    q.addons = addons
    q.price = round(float(est.get("total") or 0), 2)
    q.breakdown = {k: est.get(k) for k in ("items_subtotal", "service_fee", "disposal_fee",
                                           "volume_discount", "surge_amount", "total")}
    q.status = "answered"
    q.sent_at = _now()
    body = quote_text(q)
    q.asked = True
    db.session.commit()
    _send(digits, body)
    return q


# ---------------------------------------------------------------------------
# the desk: quoted and never booked is a lead, not a lost cause
# ---------------------------------------------------------------------------
def desk_leads(since):
    from leads import _lead
    out = []
    rows = (PhotoQuote.query
            .filter(PhotoQuote.created_at >= since, PhotoQuote.status.in_(OPEN_STATUSES))
            .order_by(PhotoQuote.created_at.desc()).limit(200).all())
    for q in rows:
        what = ", ".join((i.get("description") or i["category"].replace("_", " "))
                         for i in (q.items or [])[:3])
        if q.price:
            what = (what + " · " if what else "") + "${:.0f} quoted".format(q.price)
        elif q.status == "needs_human":
            what = (what + " · " if what else "") + "needs a price"
        out.append(_lead(SOURCE, q.id, phone=q.phone_digits, name=q.name,
                         what=what or "sent a photo", source=SOURCE, created_at=q.created_at,
                         extra={"ref": q.ref, "photos": len(q.media_urls or []),
                                "quote_price": q.price, "confidence": q.confidence,
                                "unclear": q.unclear or [], "quote_status": q.status,
                                "needs_price": q.status == "needs_human"}))
    return out


def link_job(job, ref=None, digits=None):
    """Tie a booking to the photo quote it came from. Never raises."""
    try:
        q = None
        if ref:
            q = PhotoQuote.query.filter_by(ref=str(ref).strip().upper()[:10]).first()
        if q is None and digits:
            q = open_quote_for(digits_of(digits))
        if q is None or q.job_id:
            return None
        q.job_id = job.id
        q.status = "booked"
        db.session.commit()
        return q
    except Exception:
        logger.exception("photo quote: could not link job")
        db.session.rollback()
        return None


def record_final(job):
    """What the job actually billed vs the number we promised. Never raises."""
    try:
        q = PhotoQuote.query.filter_by(job_id=job.id).first()
        if q is None or q.price is None:
            return None
        final = float(getattr(job, "total_price", None) or 0)
        q.final_price = final
        q.drift = round(final - float(q.price), 2)
        db.session.commit()
        if abs(q.drift) >= max(25.0, 0.15 * float(q.price)):
            _alert(q, "price moved ${:+.0f} from the photo quote".format(q.drift))
        return q
    except Exception:
        logger.exception("photo quote: could not record the final price")
        db.session.rollback()
        return None


def drift_report(days=30):
    """Is the promise holding? One number a person can act on."""
    since = _now() - timedelta(days=days)
    rows = (PhotoQuote.query
            .filter(PhotoQuote.created_at >= since, PhotoQuote.drift.isnot(None)).all())
    sent = PhotoQuote.query.filter(PhotoQuote.created_at >= since,
                                   PhotoQuote.price.isnot(None)).count()
    booked = PhotoQuote.query.filter(PhotoQuote.created_at >= since,
                                     PhotoQuote.status == "booked").count()
    human = PhotoQuote.query.filter(PhotoQuote.created_at >= since,
                                    PhotoQuote.status == "needs_human").count()
    drifts = [r.drift for r in rows]
    held = sum(1 for d in drifts if abs(d) < 1.0)
    return {"days": days, "quoted": sent, "booked": booked, "needs_human": human,
            "completed": len(drifts), "held_exactly": held,
            "avg_drift": round(sum(drifts) / len(drifts), 2) if drifts else None,
            "worst": max(drifts, key=abs) if drifts else None,
            "book_rate": round(booked / sent, 3) if sent else None}
