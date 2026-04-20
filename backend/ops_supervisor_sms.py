"""
Ops Supervisor — SMS body crafting with Claude Haiku (spec 11, 72h MVP).

The ONLY place Claude touches the 72h MVP. We never let Claude decide the
action, only write the customer-facing SMS copy. Haiku (claude-haiku-4-5) is
sufficient for 280 chars of copy and ~40x cheaper than Opus.

Fallbacks:
  * If ``ANTHROPIC_API_KEY`` is unset → return the tag's static template.
  * If the SDK is missing or raises → static template.
  * If Claude returns > 320 chars → truncate at a word boundary.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
MAX_SMS_CHARS = 320

SYSTEM_PROMPT = (
    "You write a <=280 character SMS to an Umuve customer about a live "
    "junk-removal booking. Warm, direct, Florida tone. No emoji unless the "
    "customer used one first. Include the concrete action already taken "
    "(exact credit amount, ETA, retry link). Never apologize vaguely -- "
    "state the fact. Never invent facts not supplied in the input JSON."
)

# Deterministic fallbacks. These are also used as the final safety net if
# Claude times out. Keep them under 280 chars.
TEMPLATES = {
    "truck_late": (
        "Hi {name} -- your Umuve driver is running {minutes_late} min behind. "
        "We dropped ${credit_dollars} in your account as an apology. "
        "New ETA: {eta}. Reply HELP if you need us."
    ),
    "payment_failed_post_job": (
        "Hi {name} -- the charge for your Umuve job didn't go through. "
        "Retry here: {retry_link}. Reply HELP if you need a hand."
    ),
    "gps_deviation": (
        "Quick check-in from Umuve: our GPS shows your driver 2+ mi off "
        "route for 8 min. We're looking into it and will update shortly."
    ),
}


def _render_template(tag: str, booking_summary: dict, action_taken: dict) -> str:
    tpl = TEMPLATES.get(tag)
    if tpl is None:
        return "Umuve update: we're working on an issue with your booking and will follow up shortly."

    name = (booking_summary.get("customer_name") or "").split(" ")[0] or "there"
    fields = {
        "name": name,
        "minutes_late": booking_summary.get("minutes_late") or action_taken.get("minutes_late") or "a few",
        "credit_dollars": action_taken.get("credit_dollars") or action_taken.get("amount_usd") or 0,
        "eta": booking_summary.get("eta") or action_taken.get("eta") or "soon",
        "retry_link": action_taken.get("retry_link") or booking_summary.get("retry_link") or "goumuve.com/pay",
    }
    try:
        return tpl.format(**fields)
    except Exception:
        return tpl


def _truncate(body: str, limit: int = MAX_SMS_CHARS) -> str:
    if not body:
        return ""
    if len(body) <= limit:
        return body
    cut = body[: limit - 1]
    # Back off to the last whitespace so we don't truncate mid-word.
    last_space = cut.rfind(" ")
    if last_space > limit * 0.6:
        cut = cut[:last_space]
    return cut.rstrip() + "..."


def craft_sms(
    situation_tag: str,
    booking_summary: dict,
    action_taken: dict,
    *,
    client=None,
) -> str:
    """Return an SMS body string for ``situation_tag``.

    ``client`` lets tests inject a fake Anthropic client; pass ``None`` for
    production code and we build one lazily.
    """
    booking_summary = booking_summary or {}
    action_taken = action_taken or {}
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    # No key -> template path. Deterministic, no surprises.
    if not api_key and client is None:
        logger.debug("craft_sms: ANTHROPIC_API_KEY missing, using template")
        return _truncate(_render_template(situation_tag, booking_summary, action_taken))

    try:
        if client is None:
            import anthropic  # noqa: WPS433 (lazy import is intentional)
            client = anthropic.Anthropic(api_key=api_key)

        user_payload = json.dumps(
            {
                "tag": situation_tag,
                "booking_summary": booking_summary,
                "action_taken": action_taken,
            },
            default=str,
        )

        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_payload}],
        )

        # Anthropic returns a list of content blocks.
        text_parts = []
        content = getattr(resp, "content", None) or []
        for block in content:
            txt = getattr(block, "text", None)
            if txt:
                text_parts.append(txt)
        body = "".join(text_parts).strip().strip('"')
        if not body:
            raise RuntimeError("empty response from Claude")
        return _truncate(body)
    except Exception:
        logger.exception("craft_sms: Claude call failed, falling back to template")
        return _truncate(_render_template(situation_tag, booking_summary, action_taken))


__all__ = ["craft_sms", "TEMPLATES", "ANTHROPIC_MODEL", "MAX_SMS_CHARS"]
