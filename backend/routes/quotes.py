"""
Vision-Based Binding Quote Engine (spec 01-vision-quote-engine.md).

POST /api/v1/quotes/estimate
    Accept customer photos (image URLs and/or base64), run a cloud VISION model
    to identify junk items + estimate volume, map that to a binding price using
    the EXISTING pricing engine (``routes.booking.calculate_estimate`` — reused,
    not reinvented), persist a Quote + QuoteItem rows + a VisionInferenceLog
    audit row, and return the itemized breakdown, volume, and price.

Provider strategy (PROVIDER-AGNOSTIC, env-driven — NEVER hardcode a key):
    - If ``OPENAI_API_KEY`` is set        -> OpenAI ``gpt-4o-mini`` vision.
    - Else if ``GEMINI_API_KEY`` is set   -> Google ``gemini-1.5-flash`` vision.
    - Else                                -> rules-based fallback (item-count
      heuristic). The quote is still produced and persisted with ``origin='rules'``
      so the feature works on a box with no vision key (e.g. local dev).

CRITICAL: Render prod cannot reach zino/Ollama (Tailscale-only), so the vision
call MUST go to a public cloud API. Both supported providers are public.

GET  /api/v1/quotes/<quote_id>
    Fetch a persisted quote + items (for the booking flow to resume / confirm).
"""

import base64
import hashlib
import json
import logging
import os
import sys
import threading
import time
from datetime import timedelta

from flask import Blueprint, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (  # noqa: E402
    db, Quote, QuoteItem, VisionInferenceLog, generate_uuid, utcnow,
)
from extensions import limiter  # noqa: E402

# Reuse the existing, battle-tested pricing engine + per-item price table.
from routes.booking import (  # noqa: E402
    calculate_estimate,
    _get_item_price,
)

quotes_bp = Blueprint("quotes", __name__, url_prefix="/api/v1/quotes")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config / constants
# ---------------------------------------------------------------------------
MAX_PHOTOS = 6
QUOTE_TTL_HOURS = 48
CALIBRATION_VERSION = "cal-v1-2026-06"

# A binding quote requires the model to be confident enough. Below this we
# still return a price but flag it non-binding (pending_review band).
BINDING_CONFIDENCE_THRESHOLD = 0.85

# Cubic ft per cubic yard (vision model is prompted in cubic FEET; the Quote
# schema stores cubic YARDS).
CU_FT_PER_CU_YARD = 27.0

# Rough per-category volume (cubic feet) used to synthesize a volume figure
# when the model gives items but no usable volume number, and for the
# rules-based fallback.
CATEGORY_CU_FT = {
    "furniture": 18.0,
    "appliances": 22.0,
    "electronics": 4.0,
    "mattress": 20.0,
    "hot_tub": 90.0,
    "yard_waste": 15.0,
    "construction": 20.0,
    "general": 8.0,
    "other": 8.0,
}
DEFAULT_ITEM_CU_FT = 10.0

# Token cost (USD cents) — coarse, audit-only. gpt-4o-mini pricing.
_OPENAI_IN_CENTS_PER_1K = 0.015
_OPENAI_OUT_CENTS_PER_1K = 0.060
_GEMINI_FLASH_CENTS_PER_1K = 0.0075  # blended, very rough

# ---------------------------------------------------------------------------
# Cost-leakage guards (the estimate endpoint is unauthenticated and bills a
# paid vision call, so it must be defended against runaway spend / abuse).
# ---------------------------------------------------------------------------
# Hard daily ceiling on paid vision spend. Once today's logged spend reaches
# this, new estimates fall back to the (free) rules heuristic instead of
# billing a provider. Override via env.
VISION_DAILY_BUDGET_CENTS = float(os.environ.get("VISION_DAILY_BUDGET_CENTS", "500"))

# Short-lived dedupe so a double-submitted photo set returns the first quote
# instead of billing a second vision call. Backed by Redis when REDIS_URL is
# set (shared across workers), else an in-process dict (single worker).
_DEDUPE_TTL_SECONDS = 600
_DEDUPE_PREFIX = "vq:dedupe:"
_dedupe_lock = threading.Lock()
_dedupe_cache = {}  # img_hash -> (quote_id, epoch_ts)
_redis_client = None
_redis_init = False


def _get_redis():
    """Return a Redis client if REDIS_URL is configured, else None (cached)."""
    global _redis_client, _redis_init
    if _redis_init:
        return _redis_client
    _redis_init = True
    url = os.environ.get("REDIS_URL")
    if url:
        try:
            import redis  # dependency already pinned in requirements.txt
            _redis_client = redis.Redis.from_url(url, socket_timeout=1)
        except Exception:
            logger.warning("vision dedupe: Redis unavailable — using in-process cache")
            _redis_client = None
    return _redis_client


def _images_hash(images):
    """Stable sha256 over the normalized image set (URLs + inline bytes)."""
    h = hashlib.sha256()
    for img in images:
        h.update(b"\x00")
        h.update((img.get("kind") or "").encode("utf-8"))
        h.update(b"\x01")
        h.update((img.get("value") or "").encode("utf-8"))
    return h.hexdigest()


def _dedupe_get(img_hash):
    """Return a still-fresh quote_id previously produced for this image set."""
    r = _get_redis()
    if r is not None:
        try:
            val = r.get(_DEDUPE_PREFIX + img_hash)
            return val.decode() if isinstance(val, bytes) else val
        except Exception:
            return None
    now = time.time()
    with _dedupe_lock:
        entry = _dedupe_cache.get(img_hash)
        if not entry:
            return None
        quote_id, ts = entry
        if now - ts > _DEDUPE_TTL_SECONDS:
            _dedupe_cache.pop(img_hash, None)
            return None
        return quote_id


def _dedupe_put(img_hash, quote_id):
    r = _get_redis()
    if r is not None:
        try:
            r.setex(_DEDUPE_PREFIX + img_hash, _DEDUPE_TTL_SECONDS, quote_id)
            return
        except Exception:
            pass
    now = time.time()
    with _dedupe_lock:
        if len(_dedupe_cache) > 1000:  # bound memory: drop expired entries
            for k, (_, ts) in list(_dedupe_cache.items()):
                if now - ts > _DEDUPE_TTL_SECONDS:
                    _dedupe_cache.pop(k, None)
        _dedupe_cache[img_hash] = (quote_id, now)


def _vision_spend_today_cents():
    """Sum today's (UTC) logged vision spend. Used to enforce the daily cap."""
    from datetime import datetime, timezone
    midnight = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    try:
        total = db.session.query(
            db.func.coalesce(db.func.sum(VisionInferenceLog.cost_cents), 0.0)
        ).filter(VisionInferenceLog.created_at >= midnight).scalar()
        return float(total or 0.0)
    except Exception:
        logger.exception("vision budget: failed to sum today's spend")
        return 0.0

# ---------------------------------------------------------------------------
# Vision prompt (shared across providers)
# ---------------------------------------------------------------------------
VISION_SYSTEM_PROMPT = """You are a junk-removal estimator. Look at the photo(s) of items a customer wants hauled away and return ONLY a JSON object (no markdown, no prose):

{
  "items": [
    {"category": "<category>", "display_name": "<short human name>", "count": <int>, "volume_cubic_feet": <float>, "hazmat": <bool>}
  ],
  "total_volume_cubic_feet": <float>,
  "confidence": <float 0.0-1.0>,
  "hazmat": <bool>,
  "notes": "<one short sentence>"
}

Rules:
- category MUST be one of: furniture, appliances, electronics, yard_waste, construction, general, mattress, hot_tub, other
- volume_cubic_feet is the physical space the item(s) occupy in a truck bed.
- total_volume_cubic_feet is the sum across all items.
- hazmat=true for paint, chemicals, propane, batteries, tires, freon appliances.
- confidence reflects photo clarity + how sure you are of the items.
- Return ONLY valid JSON."""

_PROMPT_HASH = hashlib.sha256(VISION_SYSTEM_PROMPT.encode("utf-8")).hexdigest()

VALID_CATEGORIES = set(CATEGORY_CU_FT.keys())


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------
def _select_provider():
    """Return ('openai'|'gemini'|None, api_key|None, model_name)."""
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return "openai", openai_key, "gpt-4o-mini"
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        return "gemini", gemini_key, "gemini-1.5-flash"
    return None, None, "rules-heuristic-v1"


# ---------------------------------------------------------------------------
# Image normalization — accept URLs and/or base64
# ---------------------------------------------------------------------------
def _normalize_images(data):
    """Return a list of dicts: {"kind": "url"|"data_uri", "value": str}.

    Accepts:
      - photo_urls / photoUrls / image_urls : list[str] (http(s) URLs)
      - images_base64 / imagesBase64        : list[str] (raw b64 or data URIs)
    """
    out = []

    urls = (
        data.get("photo_urls")
        or data.get("photoUrls")
        or data.get("image_urls")
        or []
    )
    if isinstance(urls, list):
        for u in urls:
            if isinstance(u, str) and u.strip():
                out.append({"kind": "url", "value": u.strip()})

    b64s = (
        data.get("images_base64")
        or data.get("imagesBase64")
        or data.get("images")
        or []
    )
    if isinstance(b64s, list):
        for b in b64s:
            if not isinstance(b, str) or not b.strip():
                continue
            b = b.strip()
            if b.startswith("data:"):
                out.append({"kind": "data_uri", "value": b})
            else:
                # bare base64 -> wrap as a jpeg data URI
                out.append({"kind": "data_uri", "value": "data:image/jpeg;base64," + b})

    return out[:MAX_PHOTOS]


def _public_photo_urls(images):
    """The Quote.photo_urls column requires a non-empty list. Persist URLs we
    have; for inline base64 we store a stable placeholder marker (the raw bytes
    themselves are not re-stored)."""
    urls = [img["value"] for img in images if img["kind"] == "url"]
    inline = sum(1 for img in images if img["kind"] == "data_uri")
    for i in range(inline):
        urls.append("inline://photo-{}".format(i))
    return urls or ["inline://no-photo"]


# ---------------------------------------------------------------------------
# Vision calls
# ---------------------------------------------------------------------------
def _to_openai_content(images):
    content = [{"type": "text", "text": VISION_SYSTEM_PROMPT}]
    for img in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": img["value"], "detail": "low"},
        })
    return content


def _call_openai(api_key, model, images):
    """Return (parsed_dict, input_tokens, output_tokens, raw_text)."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": _to_openai_content(images)}],
        max_tokens=1024,
        temperature=0.2,
    )
    raw_text = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) or 0
    out_tok = getattr(usage, "completion_tokens", 0) or 0
    return _parse_vision_json(raw_text), in_tok, out_tok, raw_text


def _call_gemini(api_key, model, images):
    """Return (parsed_dict, input_tokens, output_tokens, raw_text).

    Uses the Generative Language REST API (no extra SDK dependency).
    Gemini needs inline image bytes, so http(s) URLs are fetched first.
    """
    import requests

    parts = [{"text": VISION_SYSTEM_PROMPT}]
    for img in images:
        mime, b64 = _image_to_inline(img)
        if b64 is None:
            continue
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{}:generateContent?key={}".format(model, api_key)
    )
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
    }
    r = requests.post(url, json=body, timeout=45)
    r.raise_for_status()
    payload = r.json()
    raw_text = ""
    try:
        raw_text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raw_text = json.dumps(payload)[:2000]
    usage = payload.get("usageMetadata", {}) or {}
    in_tok = usage.get("promptTokenCount", 0) or 0
    out_tok = usage.get("candidatesTokenCount", 0) or 0
    return _parse_vision_json(raw_text), in_tok, out_tok, raw_text


def _image_to_inline(img):
    """Return (mime, base64_str) for a Gemini inline_data part, or (None, None)."""
    import requests
    if img["kind"] == "data_uri":
        # data:<mime>;base64,<payload>
        try:
            header, payload = img["value"].split(",", 1)
            mime = header.split(":", 1)[1].split(";", 1)[0] or "image/jpeg"
            return mime, payload
        except (ValueError, IndexError):
            return None, None
    # url -> fetch bytes
    try:
        resp = requests.get(img["value"], timeout=20)
        resp.raise_for_status()
        mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        return mime, base64.b64encode(resp.content).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini image fetch failed for %s: %s", img["value"][:80], exc)
        return None, None


def _parse_vision_json(raw_text):
    cleaned = (raw_text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Normalize model output -> priced items
# ---------------------------------------------------------------------------
def _normalize_vision_items(parsed):
    """Sanitize raw model items into a clean list of dicts."""
    items = []
    any_hazmat = False
    for raw in parsed.get("items", []) or []:
        cat = str(raw.get("category", "other")).lower().strip()
        if cat not in VALID_CATEGORIES:
            cat = "other"
        count = max(1, int(raw.get("count") or raw.get("quantity") or 1))
        vol_cf = raw.get("volume_cubic_feet")
        try:
            vol_cf = float(vol_cf)
        except (TypeError, ValueError):
            vol_cf = CATEGORY_CU_FT.get(cat, DEFAULT_ITEM_CU_FT) * count
        if vol_cf <= 0:
            vol_cf = CATEGORY_CU_FT.get(cat, DEFAULT_ITEM_CU_FT) * count
        hazmat = bool(raw.get("hazmat", False))
        any_hazmat = any_hazmat or hazmat
        display = str(raw.get("display_name") or raw.get("description") or cat)[:128]
        items.append({
            "category": cat,
            "display_name": display,
            "count": count,
            "volume_cubic_feet": round(vol_cf, 2),
            "hazmat": hazmat,
        })
    return items, any_hazmat


def _rules_fallback_items(images):
    """No vision key configured (or vision failed): produce a conservative
    default estimate so the feature still works. One 'general' item per photo
    (item-count heuristic)."""
    n = max(1, len(images))
    return [{
        "category": "general",
        "display_name": "Miscellaneous items (estimate)",
        "count": n,
        "volume_cubic_feet": round(CATEGORY_CU_FT["general"] * n, 2),
        "hazmat": False,
    }], False


# ---------------------------------------------------------------------------
# Route: POST /api/v1/quotes/estimate
# ---------------------------------------------------------------------------
@quotes_bp.route("/estimate", methods=["POST"])
@limiter.limit("5 per minute;40 per day")
def estimate_quote():
    """Photo -> binding price. See module docstring."""
    data = request.get_json(silent=True) or {}

    images = _normalize_images(data)
    if not images:
        return jsonify({
            "success": False,
            "error": "At least one image is required (photo_urls or images_base64).",
        }), 400

    # --- Dedupe: an identical photo set submitted again within the TTL returns
    # the first quote instead of billing a second paid vision call. ---
    img_hash = _images_hash(images)
    cached_id = _dedupe_get(img_hash)
    if cached_id:
        cached = db.session.get(Quote, cached_id)
        if cached is not None:
            return jsonify({
                "success": True,
                "quote": _serialize_persisted_quote(cached),
                "deduped": True,
            }), 200

    zip_code = str(data.get("zip_code") or data.get("zipCode") or "").strip()[:10]
    zone = str(data.get("zone") or "palm-beach").strip().lower()[:32]
    scheduled_date = data.get("scheduledDate") or data.get("scheduled_date")
    guest_phone = (data.get("guest_phone") or data.get("guestPhone") or None)
    guest_email = (data.get("guest_email") or data.get("guestEmail") or None)
    user_id = data.get("user_id") or None

    provider, api_key, model_name = _select_provider()

    # --- Daily spend cap: if today's vision spend is at/over budget, skip the
    # paid provider and serve a free rules-based quote instead. ---
    over_budget = False
    if provider and _vision_spend_today_cents() >= VISION_DAILY_BUDGET_CENTS:
        over_budget = True
        logger.warning(
            "vision daily budget reached (>= %.0f cents) — serving rules fallback",
            VISION_DAILY_BUDGET_CENTS,
        )

    # --- Run vision (or fall back) ---
    started = time.time()
    origin = "rules"
    vision_error = "daily budget exceeded" if over_budget else None
    in_tok = out_tok = 0
    raw_text = ""
    parsed = {}
    confidence = 0.55  # default for rules fallback

    if provider and not over_budget:
        try:
            if provider == "openai":
                parsed, in_tok, out_tok, raw_text = _call_openai(api_key, model_name, images)
            else:
                parsed, in_tok, out_tok, raw_text = _call_gemini(api_key, model_name, images)
            items, any_hazmat = _normalize_vision_items(parsed)
            if items:
                origin = "vision"
                try:
                    confidence = float(parsed.get("confidence", 0.7))
                except (TypeError, ValueError):
                    confidence = 0.7
                confidence = min(1.0, max(0.0, confidence))
            else:
                # model returned nothing usable -> fall back
                items, any_hazmat = _rules_fallback_items(images)
                vision_error = "vision returned no items"
        except Exception as exc:  # noqa: BLE001
            logger.error("Vision provider %s failed: %s", provider, exc)
            vision_error = str(exc)[:1000]
            items, any_hazmat = _rules_fallback_items(images)
            confidence = 0.4
    else:
        items, any_hazmat = _rules_fallback_items(images)

    latency_ms = int((time.time() - started) * 1000)

    # --- Volume (cubic feet -> cubic yards) ---
    try:
        total_cu_ft = float(parsed.get("total_volume_cubic_feet") or 0)
    except (TypeError, ValueError):
        total_cu_ft = 0.0
    if total_cu_ft <= 0:
        total_cu_ft = sum(i["volume_cubic_feet"] for i in items)
    total_cu_yd = round(total_cu_ft / CU_FT_PER_CU_YARD, 2)
    if any_hazmat or bool(parsed.get("hazmat")):
        any_hazmat = True

    # --- Price via the EXISTING pricing engine (reuse) ---
    pricing_items = [
        {"category": i["category"], "quantity": i["count"]} for i in items
    ]
    breakdown = calculate_estimate(pricing_items, scheduled_date=scheduled_date)
    price_cents = int(round(breakdown["total"] * 100))

    binding = origin == "vision" and confidence >= BINDING_CONFIDENCE_THRESHOLD
    if binding:
        status = "binding"
        price_floor_cents = None
        price_ceiling_cents = None
    else:
        status = "pending_review"
        # band for non-binding estimates
        price_floor_cents = int(round(price_cents * 0.85))
        price_ceiling_cents = int(round(price_cents * 1.20))

    # --- Persist Quote + items + inference log ---
    now = utcnow()
    quote_id = generate_uuid()
    quote = Quote(
        id=quote_id,
        user_id=user_id,
        guest_phone=guest_phone,
        guest_email=guest_email,
        zip_code=zip_code or "00000",
        zone=zone,
        status=status,
        origin=origin,
        price_cents=price_cents,
        price_floor_cents=price_floor_cents,
        price_ceiling_cents=price_ceiling_cents,
        estimated_volume_cubic_yards=total_cu_yd,
        confidence_score=confidence,
        hazmat_flag=any_hazmat,
        binding=binding,
        model_version=model_name,
        calibration_version=CALIBRATION_VERSION,
        expires_at=now + timedelta(hours=QUOTE_TTL_HOURS),
        created_at=now,
        photo_urls=_public_photo_urls(images),
    )
    db.session.add(quote)

    # Per-item rows with unit pricing pulled from the same price table.
    for i in items:
        unit_price = _get_item_price(i["category"])
        db.session.add(QuoteItem(
            id=generate_uuid(),
            quote_id=quote_id,
            label=i["category"],
            display_name=i["display_name"],
            count=i["count"],
            volume_cubic_yards=round(i["volume_cubic_feet"] / CU_FT_PER_CU_YARD, 3),
            unit_price_cents=int(round(unit_price * 100)),
            hazmat=i["hazmat"],
        ))

    cost_cents = _estimate_cost_cents(provider, in_tok, out_tok)
    log = VisionInferenceLog(
        id=generate_uuid(),
        quote_id=quote_id,
        model=model_name,
        prompt_hash=_PROMPT_HASH,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_cents=cost_cents,
        latency_ms=latency_ms,
        raw_response=(parsed if parsed else {"raw_text": raw_text[:2000]}),
        error=vision_error,
        created_at=now,
    )
    db.session.add(log)

    try:
        # Flush FIRST with quote.raw_inference_id still NULL, so rows insert in a
        # clean dependency order (quote -> items -> log). THEN back-fill the
        # pointer as an UPDATE, now that the vision_inference_logs row exists.
        # Setting it before the flush makes the circular FK
        # (fk_quotes_raw_inference -> vision_inference_logs.id) violate on insert.
        db.session.flush()
        quote.raw_inference_id = log.id
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        logger.error("Failed to persist quote: %s", exc)
        return jsonify({"success": False, "error": "Could not save quote."}), 500

    # Record for dedupe so an immediate re-submit of the same photos is free.
    _dedupe_put(img_hash, quote_id)

    return jsonify({
        "success": True,
        "quote": _serialize_quote(quote, items, breakdown),
    }), 200


def _estimate_cost_cents(provider, in_tok, out_tok):
    if provider == "openai":
        return round(
            (in_tok / 1000.0) * _OPENAI_IN_CENTS_PER_1K
            + (out_tok / 1000.0) * _OPENAI_OUT_CENTS_PER_1K,
            4,
        )
    if provider == "gemini":
        return round(((in_tok + out_tok) / 1000.0) * _GEMINI_FLASH_CENTS_PER_1K, 4)
    return 0.0


def _serialize_quote(quote, items, breakdown):
    return {
        "id": quote.id,
        "status": quote.status,
        "origin": quote.origin,
        "binding": quote.binding,
        "price": round(quote.price_cents / 100.0, 2),
        "price_cents": quote.price_cents,
        "price_floor": (round(quote.price_floor_cents / 100.0, 2)
                        if quote.price_floor_cents is not None else None),
        "price_ceiling": (round(quote.price_ceiling_cents / 100.0, 2)
                          if quote.price_ceiling_cents is not None else None),
        "estimated_volume_cubic_yards": quote.estimated_volume_cubic_yards,
        "confidence": round(quote.confidence_score, 2),
        "hazmat": quote.hazmat_flag,
        "model_version": quote.model_version,
        "expires_at": quote.expires_at.isoformat() if quote.expires_at else None,
        "items": [
            {
                "category": i["category"],
                "display_name": i["display_name"],
                "count": i["count"],
                "volume_cubic_feet": i["volume_cubic_feet"],
                "hazmat": i["hazmat"],
            }
            for i in items
        ],
        "pricing_breakdown": {
            "items_subtotal": breakdown.get("items_subtotal"),
            "volume_discount": breakdown.get("volume_discount"),
            "surge_amount": breakdown.get("surge_amount"),
            "surge_reasons": breakdown.get("surge_reasons"),
            "service_fee": breakdown.get("service_fee"),
            "minimum_applied": breakdown.get("minimum_applied"),
            "total": breakdown.get("total"),
        },
    }


# ---------------------------------------------------------------------------
# Route: GET /api/v1/quotes/<quote_id>
# ---------------------------------------------------------------------------
def _serialize_persisted_quote(quote):
    """Rebuild the estimate response payload from a stored Quote + its items."""
    items = [
        {
            "category": it.label,
            "display_name": it.display_name,
            "count": it.count,
            "volume_cubic_feet": round(it.volume_cubic_yards * CU_FT_PER_CU_YARD, 2),
            "hazmat": it.hazmat,
        }
        for it in quote.items
    ]
    pricing_items = [{"category": it.label, "quantity": it.count} for it in quote.items]
    breakdown = calculate_estimate(pricing_items)
    return _serialize_quote(quote, items, breakdown)


@quotes_bp.route("/<quote_id>", methods=["GET"])
def get_quote(quote_id):
    quote = db.session.get(Quote, quote_id)
    if quote is None:
        return jsonify({"success": False, "error": "Quote not found."}), 404

    return jsonify({
        "success": True,
        "quote": _serialize_persisted_quote(quote),
    }), 200
