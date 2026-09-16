"""Desk runway in minutes and texts — never in dollars.

The Call Desk runs on Twilio's prepaid balance. A VA working the queue needs
exactly one thing from that number: will the line last my shift? They do not
need the account balance, and on a shared screen they shouldn't see it — so
this converts balance into units and reports only units. The dollar figure
never leaves this file; nothing returned here carries a price.

Minutes and texts come out of the same balance, so they are alternatives, not
two pools — "≈400 texts or ≈280 minutes", whichever the desk actually spends it
on. Every caller of this module has to say it that way.

Rates are blended from what the account really spent (Usage Records), so the
estimate follows real destinations and carrier fees instead of list price. When
usage is too thin to divide — a new account, or a quiet month — it falls back
to env overrides and then to US list rates, and always reports which it used.

Cached in DeskSetting so a desk page load never costs a Twilio round trip; the
desk health job refreshes it every 30 minutes, and a stale cache refreshes
in-line so this still works on an instance with the scheduler switched off.

Env:
  TWILIO_RATE_SMS        override $/message     (default 0.0109 = 0.0079 + carrier)
  TWILIO_RATE_CALL_MIN   override $/call-minute (default 0.014)
  DESK_LOW_TEXTS         low-runway mark        (default 200)
  DESK_LOW_MINUTES       low-runway mark        (default 100)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CACHE_KEY = "capacity:desk"
CACHE_TTL_SECONDS = 1800

# US list rates, used only when the account has no usage to blend from.
LIST_RATE_SMS = 0.0109      # $0.0079 Twilio + ~$0.003 carrier pass-through
LIST_RATE_CALL_MIN = 0.014

# Below this, a month's usage is too small to divide into a trustworthy rate.
MIN_SAMPLE_MESSAGES = 25.0
MIN_SAMPLE_MINUTES = 10.0


def _env_float(key, default):
    try:
        raw = (os.environ.get(key) or "").strip()
        return float(raw) if raw else float(default)
    except (TypeError, ValueError):
        return float(default)


def _now():
    return datetime.now(timezone.utc)


def _client():
    sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    tok = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    if not sid or not tok:
        return None
    from twilio.rest import Client
    return Client(sid, tok)


def _blended(client, category, min_sample):
    """→ $/unit from real spend, or None. Last month first (a full month),
    then this month for an account too young to have one."""
    for window in ("last_month", "this_month"):
        try:
            records = getattr(client.usage.records, window).list(category=category, limit=1)
        except Exception:
            logger.debug("usage records unavailable for %s/%s", category, window, exc_info=True)
            continue
        for rec in records:
            try:
                used = float(rec.usage or 0)
                spent = float(rec.price or 0)
            except (TypeError, ValueError):
                continue
            if used >= min_sample and spent > 0:
                return spent / used
    return None


def _rates(client):
    """→ (sms_rate, call_minute_rate, source). Blended spend wins, then env
    overrides, then list price — whichever we used is reported, because a
    number on a wall needs to say how much to trust it."""
    sms_env = (os.environ.get("TWILIO_RATE_SMS") or "").strip()
    min_env = (os.environ.get("TWILIO_RATE_CALL_MIN") or "").strip()

    sms = _blended(client, "sms-outbound", MIN_SAMPLE_MESSAGES) if client else None
    per_min = _blended(client, "calls-outbound", MIN_SAMPLE_MINUTES) if client else None
    if sms and per_min:
        return sms, per_min, "usage"

    # Partial blend still beats list price for the half we measured.
    source = "env" if (sms_env or min_env) else "list"
    if sms or per_min:
        source = "usage+" + source
    return (sms or _env_float("TWILIO_RATE_SMS", LIST_RATE_SMS),
            per_min or _env_float("TWILIO_RATE_CALL_MIN", LIST_RATE_CALL_MIN),
            source)


def _measure():
    """Hit Twilio once: balance in, units out. Never raises, never returns money."""
    client = _client()
    if client is None:
        return {"configured": False, "ok": False, "texts": None, "minutes": None,
                "level": "unknown", "rate_source": None,
                "reason": "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set",
                "checked_at": _now().isoformat()}

    try:
        balance = float(client.balance.fetch().balance)
    except Exception as e:
        logger.warning("twilio capacity: balance unavailable (%s)", type(e).__name__)
        return {"configured": True, "ok": False, "texts": None, "minutes": None,
                "level": "unknown", "rate_source": None,
                "reason": "Twilio did not answer: " + type(e).__name__,
                "checked_at": _now().isoformat()}

    sms_rate, min_rate, source = _rates(client)
    balance = max(balance, 0.0)
    # Binary floats make $100 / $0.01 land at 9999.999…, and a desk that reads
    # 9,999 when it means 10,000 looks broken. Nudge before flooring.
    def units(rate):
        return int(balance / rate + 1e-6) if rate > 0 else None

    texts, minutes = units(sms_rate), units(min_rate)

    low_texts = int(_env_float("DESK_LOW_TEXTS", 200))
    low_minutes = int(_env_float("DESK_LOW_MINUTES", 100))
    if not texts and not minutes:
        level = "empty"
    elif (texts or 0) < low_texts or (minutes or 0) < low_minutes:
        level = "low"
    else:
        level = "ok"

    return {"configured": True, "ok": True, "texts": texts, "minutes": minutes,
            "level": level, "rate_source": source,
            "reason": "either/or — texts and minutes come out of the same pot",
            "checked_at": _now().isoformat()}


def _read_cache(max_age_seconds):
    try:
        from models import DeskSetting
        raw = DeskSetting.get(CACHE_KEY)
        if not raw:
            return None
        cached = json.loads(raw)
        stamped = datetime.fromisoformat(cached.get("checked_at"))
        if stamped.tzinfo is None:
            stamped = stamped.replace(tzinfo=timezone.utc)
        if (_now() - stamped).total_seconds() > max_age_seconds:
            return None
        return cached
    except Exception:
        return None


def _write_cache(payload):
    try:
        from models import DeskSetting
        DeskSetting.put(CACHE_KEY, json.dumps(payload))
    except Exception:
        logger.debug("twilio capacity: could not cache", exc_info=True)


def desk_capacity(refresh=False, max_age_seconds=CACHE_TTL_SECONDS):
    """→ {"configured","ok","texts","minutes","level","rate_source","reason","checked_at"}

    Units only, by design: no balance, no price, no currency. Never raises —
    a desk that can't reach Twilio shows nothing rather than a wrong number.
    """
    if not refresh:
        cached = _read_cache(max_age_seconds)
        if cached:
            return cached
    result = _measure()
    if result.get("ok") or result.get("configured") is False:
        _write_cache(result)
    return result


def summary_line(cap=None):
    """One line for a header chip. Empty string when there's nothing honest to say."""
    cap = cap if cap is not None else desk_capacity()
    if not cap.get("ok"):
        return ""
    texts, minutes = cap.get("texts"), cap.get("minutes")
    if texts is None and minutes is None:
        return ""
    parts = []
    if texts is not None:
        parts.append("{:,} texts".format(texts))
    if minutes is not None:
        parts.append("{:,} min".format(minutes))
    return "≈ " + " or ".join(parts) + " left"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(desk_capacity(refresh=True), indent=2))
