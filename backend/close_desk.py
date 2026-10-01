"""Close Desk — the rules that turn a conversation into a dated next step.

Why this exists (1 Oct 2026): thirty days of dialing read 124 "interested" and
0 jobs. Sixty-two of ninety-three win-type logs had no call in the previous
eight minutes, ninety had an empty note, every "converted" row was a hauler
sign-up, and the only live close in the script was "can I leave a card on
file?" — an ask a leasing agent can say yes to without anything happening.

What changes, in one place:

  outcomes        a win is one of three dated things — a truck date, a packet
                  to a NAMED person's cell or email, or a callback with a name,
                  role, day and time. Each has required fields; the desk can't
                  save one empty. "interested" and "sent the link" are gone.
  texting         the follow-up text goes only to a number that can receive
                  one (Twilio Lookup line type, cached), is short, signed, and
                  ends in a two-slot question. Office landlines get a call.
  window          demand calls are served 10–12 and 2–4 Florida time, the
                  hours that connect; lunch is for the inbox; the last three
                  and first five business days of a month put multifamily
                  rows first, because that is when units are left full.
  inbox           consent bots and auto-responders are flagged so a human
                  reply is never buried under "Reply START to receive…".

Evidence for each rule is in reports/Umuve B2B phone close tactics.md.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# --- outcomes ---------------------------------------------------------------

# The three things a call can end in that count. Everything else is bookkeeping.
PIPELINE_OUTCOMES = ("booked", "packet_requested", "callback")

OUTCOME_LABELS = {
    "booked": "Booked a pickup",
    "packet_requested": "Packet to a named person",
    "callback": "Callback with a name and time",
    "vendor_listed": "On their vendor list",
    "no_need_now": "Nothing now — next turn",
    "voicemail": "Voicemail",
    "no_answer": "No answer",
    "not_interested": "Not interested",
    "dnc": "Do not call",
    "bad_number": "Bad number",
    "skip": "Skip",
}

ROLES = ("maintenance_supervisor", "community_manager", "regional", "owner", "realtor", "office_manager", "other")
ROLE_LABELS = {
    "maintenance_supervisor": "Maintenance supervisor", "community_manager": "Community manager",
    "regional": "Regional / portfolio", "owner": "Owner", "realtor": "Realtor / agent",
    "office_manager": "Office manager", "other": "Other",
}

# A packet to info@ is a packet to nobody.
_GENERIC_MAILBOX = re.compile(
    r"^(info|office|leasing|contact|admin|hello|hi|sales|support|frontdesk|front\.?desk|reception|"
    r"team|mail|general|inquiries|enquiries|service|noreply|no-reply|donotreply|manager|management|rentals?|"
    r"lease|apply|applications?|customerservice|customer\.?service|help)@", re.I)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def digits_of(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())[-10:]


def is_generic_mailbox(email):
    return bool(email) and bool(_GENERIC_MAILBOX.match(email.strip()))


def is_email(s):
    return bool(s) and bool(_EMAIL.match(s.strip()))


def missing_for(outcome, data):
    """→ list of plain-English things still needed before this outcome can be
    saved. Empty list = good to go."""
    need = []
    name = (data.get("contact_name") or "").strip()
    role = (data.get("role") or "").strip()
    cell = digits_of(data.get("cell") or data.get("direct_phone"))
    email = (data.get("email") or "").strip()
    if outcome == "packet_requested":
        if not name:
            need.append("the person's name")
        if role not in ROLES:
            need.append("their role")
        if len(cell) != 10 and not is_email(email):
            need.append("a cell number or their own email")
        elif len(cell) != 10 and is_generic_mailbox(email):
            need.append("their own email, not a shared mailbox like info@")
    elif outcome == "callback":
        if not name:
            need.append("who you're calling back")
        if role not in ROLES:
            need.append("their role")
        if not (data.get("preset") or data.get("at")):
            need.append("a day and time")
    elif outcome == "booked":
        if not data.get("job_id"):
            need.append("the booking itself — tap Book it, which opens the dispatch desk prefilled")
    return need


# --- texting: can this number even get a text? ------------------------------

LINE_CACHE_PREFIX = "linetype:"
LINE_CACHE_DAYS = 90
TEXTABLE_TYPES = ("mobile", "nonFixedVoip", "fixedVoip", "voip", "personal", "unknown", "")


def line_type(digits, lookup=None):
    """mobile | landline | tollFree | nonFixedVoip | fixedVoip | unknown.
    Cached in DeskSetting for 90 days; Twilio Lookup costs a cent and the
    answer doesn't change. `lookup` is injectable for tests."""
    digits = digits_of(digits)
    if len(digits) != 10:
        return "unknown"
    try:
        from models import DeskSetting
        raw = DeskSetting.get(LINE_CACHE_PREFIX + digits)
        if raw:
            cached = json.loads(raw)
            at = datetime.fromisoformat(cached["at"])
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - at < timedelta(days=LINE_CACHE_DAYS):
                return cached.get("type") or "unknown"
    except Exception:
        pass
    kind = "unknown"
    try:
        if lookup is None:
            lookup = _twilio_lookup
        kind = lookup(digits) or "unknown"
    except Exception:
        logger.debug("line type lookup failed for …%s", digits[-4:], exc_info=True)
    try:
        from models import DeskSetting
        DeskSetting.put(LINE_CACHE_PREFIX + digits,
                        json.dumps({"type": kind, "at": datetime.now(timezone.utc).isoformat()}))
    except Exception:
        pass
    return kind


def _twilio_lookup(digits):
    sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    tok = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    if not sid or not tok:
        return "unknown"
    import requests
    r = requests.get("https://lookups.twilio.com/v2/PhoneNumbers/+1{}".format(digits),
                     params={"Fields": "line_type_intelligence"}, auth=(sid, tok), timeout=8)
    if r.status_code != 200:
        return "unknown"
    return ((r.json() or {}).get("line_type_intelligence") or {}).get("type") or "unknown"


def textable(digits, lookup=None):
    """(ok, reason). Landlines and toll-free numbers can't take a text."""
    kind = line_type(digits, lookup=lookup)
    if kind in ("landline", "tollFree"):
        return False, "that's a {} — call it, don't text it; ask for a cell".format(
            "landline" if kind == "landline" else "toll-free line")
    return True, kind


# --- the text that goes out while they're still on the line -----------------

def _first(name):
    return (name or "").strip().split()[0] if (name or "").strip() else ""


def _slots():
    """Two concrete slots, both in the future, both in hours a crew works:
    the next weekday morning at 8 and the weekday after at 2."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        now = datetime.now()
    d = now
    found = []
    while len(found) < 2:
        d = d + timedelta(days=1)
        if d.weekday() < 5:
            found.append(d)
    a, b = found
    return "{} 8am".format(a.strftime("%a")), "{} 2pm".format(b.strftime("%a"))


def packet_text(prospect, va_name=None, rate_card_url=None):
    """≤ 250 chars, signed, refers to the call, ends in a two-slot question.
    (Hatch: 160–250 chars with a one-word answer beat long texts 90% to 8.5%.)"""
    va = _first(va_name) or "Tracy"
    first = _first(getattr(prospect, "contact_name", None))
    greet = "{} — ".format(first) if first else ""
    s1, s2 = _slots()
    link = rate_card_url or "goumuve.com/partners"
    coi = os.environ.get("COI_URL", "").strip()
    docs = "rate card + COI" if coi else "rate card"
    body = "{greet}{va} from Umuve, the {docs} we talked about: {link}. For that unit — {s1} or {s2}? Reply STOP to opt out.".format(
        greet=greet, va=va, docs=docs, link=link, s1=s1, s2=s2)
    return body[:250]


def callback_text(prospect, when_label, va_name=None):
    va = _first(va_name) or "Tracy"
    first = _first(getattr(prospect, "contact_name", None))
    greet = "{} — ".format(first) if first else ""
    return "{greet}{va} from Umuve. I'll call you {when} like we said. If a unit comes up before then, text a photo here and I'll price it in minutes. Reply STOP to opt out.".format(
        greet=greet, va=va, when=when_label)[:250]


# --- the calling window --------------------------------------------------

def _now_et():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(timezone.utc) - timedelta(hours=4)


def calling_window(now=None):
    """What the desk should be doing right now, from the hours that connected:
    42–44% at 10–11 ET against 12–21% at 1–3 pm, with 59% of dials in the bad
    block (Sep 2026 pull). → {"side", "label", "demand_hours"}"""
    now = now or _now_et()
    h, wd = now.hour, now.weekday()
    if wd >= 5:
        return {"side": "any", "label": "Weekend — follow-ups and the inbox", "demand_hours": False}
    if 10 <= h < 12:
        return {"side": "demand", "label": "Prime window (10–12) — customers first", "demand_hours": True}
    if h == 12:
        return {"side": "inbox", "label": "Lunch — work the inbox, no cold dials", "demand_hours": False}
    if 14 <= h < 16:
        return {"side": "demand", "label": "Afternoon window (2–4) — customers", "demand_hours": True}
    if 9 <= h < 10 or 13 <= h < 14 or 16 <= h < 18:
        return {"side": "supply", "label": "Off-peak — haulers, callbacks, admin", "demand_hours": False}
    return {"side": "any", "label": "Outside calling hours", "demand_hours": False}


def month_end_priority(now=None):
    """True in the last three business days and first five of a month —
    leases end on the last day, move-ins land on the 1st, and that is when a
    unit is left full."""
    now = now or _now_et()
    d = now.date()
    # first five calendar days
    if d.day <= 5:
        return True
    # last three business days
    nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    biz = []
    cur = nxt - timedelta(days=1)
    while len(biz) < 3:
        if cur.weekday() < 5:
            biz.append(cur)
        cur -= timedelta(days=1)
    return d in biz


MULTIFAMILY_WORDS = ("apartment", "property", "hoa", "condo", "community", "residential", "multifamily", "complex")


def is_multifamily(category):
    c = (category or "").lower()
    return any(w in c for w in MULTIFAMILY_WORDS)


# --- inbox: who is a person --------------------------------------------------

_BOT = re.compile(
    r"reply\s+(start|yes|y)\b.{0,80}(receive|consent|updates|agree)|"
    r"\bconsent is not required\b|\bcan'?t be received by this\b|\bcannot receive\b|"
    r"\bthanks? for (contacting|reaching out to)\b|\bthank you for contacting\b|"
    r"\ba staff member will respond\b|\bwe'?ll (get back|respond) (to you )?(shortly|as soon)\b|"
    r"\bsorry (to|we) miss(ed)? your call\b|\bi'?m here to help\b.{0,60}\btour\b|\bset up a tour\b|"
    r"\bautomated\b.{0,30}\bmessage\b|\bauto-?reply\b|\bout of (the )?office\b|"
    r"\bour (office )?hours are\b|\bthis (number|line) (is|does) not\b|\bunmonitored\b|"
    r"\bmsg\s*&\s*data rates\b|\bmessage frequency varies\b", re.I)


def is_bot_reply(body):
    """Consent prompts, auto-responders and leasing-AI greetings. 17 of the 26
    inbound texts in one week were these; the one real price request sat
    unread under them."""
    b = " ".join((body or "").split())
    if not b:
        return False
    if b.strip().lower() in ("stop", "unsubscribe", "start", "yes", "y", "ok", "okay", "thanks", "thank you"):
        return False
    return bool(_BOT.search(b))
