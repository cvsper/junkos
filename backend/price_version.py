"""Pricing integrity helpers (audit F09 / F11).

One server-issued *price version* ties the estimate the customer saw to the
charge the platform makes. The version is a hash of every input that moves
the price — items, address, schedule, add-ons, promo/discount, fees and the
total — so any drift between "shown" and "charged" surfaces as a 409 that
the UI must re-confirm, never as a silent difference on the card.

The same module owns strict item validation so every caller (estimate,
booking, quote conversion) rejects malformed carts *before* any arithmetic.
"""

import hashlib
import hmac
import json
import math
import os
import re

MAX_ITEMS = 50
MAX_QUANTITY = 99
MAX_SIZE_LEN = 32

_ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")


class ItemValidationError(ValueError):
    """Raised for a cart that must not be priced."""


def _known_categories():
    from routes.booking import CATEGORY_PRICES, RECYCLING_FEE_TRIGGERS
    return set(CATEGORY_PRICES.keys()) | set(RECYCLING_FEE_TRIGGERS.keys())


def _db_rule_exists(item_type):
    try:
        from models import PricingRule
        return PricingRule.query.filter(
            PricingRule.item_type == item_type, PricingRule.is_active == True,  # noqa: E712
        ).first() is not None
    except Exception:
        return False


def _coerce_quantity(raw):
    """Return a positive bounded int or raise ItemValidationError."""
    if isinstance(raw, bool):
        raise ItemValidationError("quantity must be a whole number between 1 and {}".format(MAX_QUANTITY))
    if raw is None:
        return 1
    if isinstance(raw, float):
        if not math.isfinite(raw) or not raw.is_integer():
            raise ItemValidationError("quantity must be a whole number between 1 and {}".format(MAX_QUANTITY))
        raw = int(raw)
    elif isinstance(raw, str):
        if not raw.strip().isdigit():
            raise ItemValidationError("quantity must be a whole number between 1 and {}".format(MAX_QUANTITY))
        raw = int(raw.strip())
    elif not isinstance(raw, int):
        raise ItemValidationError("quantity must be a whole number between 1 and {}".format(MAX_QUANTITY))
    if raw < 1 or raw > MAX_QUANTITY:
        raise ItemValidationError("quantity must be between 1 and {}".format(MAX_QUANTITY))
    return raw


def validate_items(items, strict_categories=True):
    """Return a clean ``[{category, quantity, size?}]`` list or raise.

    - list of 1..MAX_ITEMS dicts
    - category: known pricing category (or an active admin PricingRule)
    - quantity: int in 1..MAX_QUANTITY (no negatives, floats, bools, NaN)
    - size: optional short string; unknown sizes for the category are dropped
      (they never change the price) rather than rejected.
    """
    if not isinstance(items, list) or not items:
        raise ItemValidationError("items array is required")
    if len(items) > MAX_ITEMS:
        raise ItemValidationError("too many items (max {})".format(MAX_ITEMS))

    from routes.booking import CATEGORY_PRICES
    known = _known_categories()
    clean = []
    for entry in items:
        if not isinstance(entry, dict):
            raise ItemValidationError("each item must be an object")
        category = entry.get("category")
        if not isinstance(category, str) or not category.strip():
            raise ItemValidationError("item category is required")
        category = category.strip().lower()[:64]
        if strict_categories and category not in known and not _db_rule_exists(category):
            raise ItemValidationError("unknown item category '{}'".format(category))
        quantity = _coerce_quantity(entry.get("quantity", 1))

        line = {"category": category, "quantity": quantity}
        size = entry.get("size")
        if size is not None:
            if not isinstance(size, str):
                raise ItemValidationError("item size must be a string")
            size = size.strip().lower()[:MAX_SIZE_LEN]
            sizes = CATEGORY_PRICES.get(category) or {}
            if size and (size in sizes or _db_rule_exists("{}:{}".format(category, size))):
                line["size"] = size
        clean.append(line)
    return clean


def _finite(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


def validate_coordinates(lat, lng):
    """Return (lat, lng) floats or raise ValueError with a customer-facing message."""
    if lat is None or lng is None or (isinstance(lat, str) and not lat.strip()) or (
        isinstance(lng, str) and not lng.strip()
    ):
        raise ValueError(
            "We need the exact pickup location — please select your address "
            "from the suggestions so we can price and dispatch it correctly."
        )
    if isinstance(lat, bool) or isinstance(lng, bool):
        raise ValueError("Invalid pickup coordinates.")
    flat, flng = _finite(lat), _finite(lng)
    if flat is None or flng is None:
        raise ValueError("Invalid pickup coordinates.")
    if not (-90.0 <= flat <= 90.0) or not (-180.0 <= flng <= 180.0):
        raise ValueError("Pickup coordinates are out of range.")
    if flat == 0.0 and flng == 0.0:
        raise ValueError("Invalid pickup coordinates.")
    return flat, flng


def normalize_schedule(scheduled_date, scheduled_time):
    """Canonical (date 'YYYY-MM-DD' | '', slot 'HH:MM' | '')."""
    from timeutils import normalize_slot
    date_part = ""
    if scheduled_date:
        date_part = str(scheduled_date).strip()[:10]
    slot = normalize_slot(scheduled_time) if scheduled_time else ""
    return date_part, slot


def zip_from_address(address):
    """Best-effort 5-digit ZIP from an address dict or string."""
    if isinstance(address, dict):
        z = address.get("zip") or address.get("postal_code") or address.get("zipCode") or ""
        z = str(z).strip()
        if z:
            m = _ZIP_RE.search(z)
            return m.group(1) if m else z[:5]
        address = address.get("street") or address.get("formatted") or ""
    m = _ZIP_RE.search(str(address or ""))
    return m.group(1) if m else ""


def _digest(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def items_scope(items):
    """Order-independent canonical item scope: [[category, quantity, size]]."""
    scope = []
    for it in items:
        scope.append([
            (it.get("category") or "").lower(),
            int(it.get("quantity") or 0),
            (it.get("size") or "").lower(),
        ])
    scope.sort()
    return scope


def compute_price_version(items, lat, lng, address_text, scheduled_date, scheduled_time,
                          addons, promo_code, discount_amount, service_fee, total,
                          quote_id=None):
    """Hash of everything that moves the price. Deterministic across processes."""
    date_part, slot = normalize_schedule(scheduled_date, scheduled_time)
    payload = {
        "v": 1,
        "items": items_scope(items),
        "lat": round(float(lat), 5) if lat is not None else None,
        "lng": round(float(lng), 5) if lng is not None else None,
        "addr": " ".join(str(address_text or "").lower().split())[:200],
        "date": date_part,
        "slot": slot,
        "addons": {k: int(v) for k, v in sorted((addons or {}).items()) if v},
        "promo": (promo_code or "").strip().upper(),
        "discount": round(float(discount_amount or 0.0), 2),
        "fee": round(float(service_fee or 0.0), 2),
        "total": round(float(total or 0.0), 2),
        "quote": quote_id or "",
    }
    return _digest(payload)


def quote_scope_hash(items, zip_code, scheduled_date):
    """Canonical scope a binding vision quote is bound to (items + ZIP + date)."""
    date_part, _ = normalize_schedule(scheduled_date, None)
    zip_code = (zip_code or "").strip()
    if zip_code == "00000":
        zip_code = ""
    return _digest({
        "v": 1,
        "items": [[c, q] for c, q, _s in items_scope(items)],
        "zip": zip_code[:5],
        "date": date_part,
    })


def _secret():
    secret = os.environ.get("QUOTE_TOKEN_SECRET") or os.environ.get("JWT_SECRET") or ""
    if not secret:
        try:
            from app_config import Config
            secret = Config.SECRET_KEY
        except Exception:
            secret = "dev-only-secret"
    return secret.encode("utf-8")


def quote_claim_token(quote_id):
    """Bearer proof that the caller created this quote (guest quotes with no
    email/user). Returned once at creation; required to convert such a quote."""
    return hmac.new(_secret(), ("quote:" + str(quote_id)).encode("utf-8"), hashlib.sha256).hexdigest()[:40]


def verify_quote_claim_token(quote_id, token):
    if not token:
        return False
    return hmac.compare_digest(quote_claim_token(quote_id), str(token))
