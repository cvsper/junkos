"""
Partner Acquisition Agent — Claude-powered outreach crafting (spec 07 §9 v1).

`craft_outreach(lead, channel)` returns a personalized SMS or email body.

  * SMS body <= 320 characters (TCR 10DLC compliance — 2 segments max).
  * Email body <= 500 words (soft cap).
  * Every SMS body ALWAYS ends with "Reply STOP to opt out." (§8 rail).
  * Falls back to a deterministic template when ANTHROPIC_API_KEY is unset
    or the Anthropic SDK call fails — never raises into the caller.

Model: claude-haiku-4-5-20251001 (fast, cheap, good enough for <=320ch bodies).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
STOP_FOOTER = "Reply STOP to opt out."

SMS_MAX = 320
EMAIL_WORD_MAX = 500

SMS_FALLBACK_TMPL = (
    "Hey{name_bit} — Umuve routes junk/hauling jobs to drivers in {metro}: "
    "$80-180/load, no fees. Want a 3-min qualifier? Reply YES. " + STOP_FOOTER
)
EMAIL_FALLBACK_TMPL = (
    "Hi{name_bit},\n\n"
    "I'm reaching out because Umuve is onboarding 40+ owner-operator haulers "
    "in {metro} this month. We route junk-removal jobs directly to your phone — "
    "average $80-180/load, same-day pay, no platform fees for the first 30 days.\n\n"
    "If you have a truck, a license, and liability insurance, reply YES and I'll "
    "send over a 3-minute qualifier. Otherwise " + STOP_FOOTER + "\n\n"
    "— Umuve Driver Team"
)


def _anthropic_client():
    """Return an Anthropic client or None if key/SDK missing. No raise."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic  # type: ignore
        return anthropic.Anthropic(api_key=key)
    except Exception:
        logger.warning("anthropic SDK unavailable; falling back to template")
        return None


def _fallback(channel: str, lead) -> str:
    """Deterministic template used when Claude is unavailable."""
    name_bit = " " + (lead.name_guess.split()[0]) if getattr(lead, "name_guess", None) else ""
    metro = (getattr(lead, "metro", None) or "your area").title()

    if channel == "sms":
        body = SMS_FALLBACK_TMPL.format(name_bit=name_bit, metro=metro)
        return _enforce_sms(body)
    body = EMAIL_FALLBACK_TMPL.format(name_bit=name_bit, metro=metro)
    return body


def _enforce_sms(body: str) -> str:
    """Cap at SMS_MAX and guarantee STOP footer. Never raises."""
    body = (body or "").strip()
    if STOP_FOOTER.lower() not in body.lower():
        # Room for footer? Trim to fit.
        room = SMS_MAX - (len(STOP_FOOTER) + 1)
        if len(body) > room:
            body = body[: max(0, room)].rstrip()
        body = (body + " " + STOP_FOOTER).strip()
    if len(body) > SMS_MAX:
        body = body[: SMS_MAX - 1].rstrip() + "…"
        # Still need footer — re-trim and re-append.
        room = SMS_MAX - (len(STOP_FOOTER) + 1)
        body = body[:room].rstrip() + " " + STOP_FOOTER
    return body


def _enforce_email(body: str) -> str:
    body = (body or "").strip()
    if STOP_FOOTER.lower() not in body.lower():
        body = body + "\n\n" + STOP_FOOTER
    # Soft word cap.
    words = body.split()
    if len(words) > EMAIL_WORD_MAX:
        body = " ".join(words[:EMAIL_WORD_MAX]) + "…\n\n" + STOP_FOOTER
    return body


def _build_prompt(lead, channel: str) -> str:
    name = getattr(lead, "name_guess", None) or "driver"
    metro = (getattr(lead, "metro", None) or "Miami").title()
    platform = getattr(lead, "platform", None) or "craigslist"

    if channel == "sms":
        return (
            "You are an outreach agent for Umuve, an on-demand junk-removal "
            "marketplace hiring owner-operator drivers. Write a single SMS to a "
            "prospective driver named {name} in {metro}, found via {platform}. "
            "The pitch: $80-180/load, same-day pay, no platform fees for 30 days, "
            "3-minute qualifier. Ask them to reply YES to continue. "
            "Hard constraints: max 280 characters, plain text only (no emojis or links), "
            "end with exactly 'Reply STOP to opt out.' Output ONLY the SMS body."
        ).format(name=name, metro=metro, platform=platform)
    return (
        "You are an outreach agent for Umuve, an on-demand junk-removal "
        "marketplace hiring owner-operator drivers. Write a short email (<=180 "
        "words) to a prospective driver named {name} in {metro}, found via "
        "{platform}. Pitch: $80-180/load, same-day pay, no fees for 30 days. "
        "Ask them to reply YES for a 3-minute qualifier. Use plain text. "
        "End with 'Reply STOP to opt out.' Output ONLY the email body."
    ).format(name=name, metro=metro, platform=platform)


def craft_outreach(lead, channel: str = "sms") -> str:
    """Return a body string. Never raises.

    `lead` is a DriverLead ORM object (or any object with name_guess / metro /
    platform attributes). `channel` is 'sms' or 'email'.
    """
    channel = (channel or "sms").lower()
    if channel not in ("sms", "email"):
        channel = "sms"

    client = _anthropic_client()
    if client is None:
        return _fallback(channel, lead)

    try:
        prompt = _build_prompt(lead, channel)
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400 if channel == "email" else 120,
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text from the first content block.
        parts = []
        for block in getattr(resp, "content", []) or []:
            text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
            if text:
                parts.append(text)
        body = "".join(parts).strip()
        if not body:
            return _fallback(channel, lead)
    except Exception:
        logger.exception("claude outreach failed; falling back to template")
        return _fallback(channel, lead)

    if channel == "sms":
        return _enforce_sms(body)
    return _enforce_email(body)
