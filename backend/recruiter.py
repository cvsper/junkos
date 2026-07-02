"""
Automated supply acquisition — the marketplace recruits its own haulers.

Three funnels, one destination (a concierge Contractor on the offer wave):

  1. Inbound keyword: a hauler texts JOBS to the Umuve number -> auto-
     registered, welcomed, receiving SMS job offers. Inbound-initiated, so
     it's consent-clean (TCPA).
  2. /optext (Trixie / staff): "send setup link" now also registers the
     hauler as concierge in the same tap.
  3. Maya Recruiter (outbound Vapi calls, kill-switched): dials DriverLead
     rows, pitches, and on a warm outcome auto-registers + texts the setup
     link. See recruiter_calls.py for the caller; this module holds the
     shared registration used by all three.

Design rule: registration is idempotent and phone-keyed. The same number can
arrive from a text, a Trixie tap, and a Maya call without creating
duplicates — whoever gets there first wins, the rest are no-ops.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# Default service-area anchor (WPB) for concierge ops with no geo yet — puts
# them in dispatch range so the coverage gate opens. Overridable via env.
try:
    DEFAULT_LAT = float(os.environ.get("RECRUIT_DEFAULT_LAT", "26.7153"))
    DEFAULT_LNG = float(os.environ.get("RECRUIT_DEFAULT_LNG", "-80.0534"))
except (TypeError, ValueError):
    DEFAULT_LAT, DEFAULT_LNG = 26.7153, -80.0534

# Inbound keywords that mean "sign me up to haul" (matched on a stripped,
# lowercased first word so "JOBS please" and "jobs!" both hit).
SIGNUP_KEYWORDS = {"jobs", "job", "haul", "hauler", "drive", "driver", "work", "signup"}


def normalize_phone(raw):
    """Best-effort US E.164. Returns None if unusable."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return ("+" + digits) if len(digits) > 10 else None


def is_signup_keyword(body):
    """True if an inbound SMS body is a hauler signup request."""
    if not body:
        return False
    first = re.sub(r"[^a-z]", "", body.strip().lower().split()[0]) if body.strip() else ""
    return first in SIGNUP_KEYWORDS


def register_concierge(phone, name=None, source="inbound", lat=None, lng=None,
                       send_welcome=True):
    """Idempotently register a hauler as an approved, online concierge operator.

    Returns a dict: {"ok", "status", "contractor_id", "message"}.
      status one of: created | exists_concierge | exists_app | invalid | error

    Never raises. Safe to call from an SMS webhook, a Vapi outcome handler, or
    the /optext tool. Registering the first one in range opens the WPB coverage
    gate for real bookings.
    """
    try:
        from models import db, Contractor, User, generate_uuid, utcnow

        e164 = normalize_phone(phone)
        if not e164:
            return {"ok": False, "status": "invalid", "contractor_id": None,
                    "message": "Invalid phone."}

        user = User.query.filter_by(phone=e164).first()
        if user and user.contractor_profile:
            c = user.contractor_profile
            # Already a hauler in some form — don't duplicate. If they were a
            # concierge who opted out or got suspended for inactivity, a fresh
            # signup keyword re-activates them.
            if c.is_concierge:
                reactivated = False
                if c.approval_status != "approved" or not c.is_online:
                    c.approval_status = "approved"
                    c.is_online = True
                    c.updated_at = utcnow()
                    db.session.commit()
                    reactivated = True
                if reactivated and send_welcome:
                    _welcome_sms(e164, user.name)
                return {"ok": True, "status": "exists_concierge",
                        "contractor_id": c.id,
                        "message": "Already a concierge hauler"
                                   + (" — reactivated" if reactivated else "")}
            return {"ok": False, "status": "exists_app", "contractor_id": c.id,
                    "message": "Phone belongs to an app-registered contractor"}

        if not user:
            user = User(
                id=generate_uuid(),
                name=(name or "").strip()[:120] or None,
                phone=e164,
                role="driver",
                # No password — the account can't log in; the hauler acts only
                # through unguessable offer tokens + the /w/ console.
            )
            db.session.add(user)
        elif name and not user.name:
            user.name = name.strip()[:120]

        contractor = Contractor(
            id=generate_uuid(),
            user_id=user.id,
            truck_type="pickup",
            truck_capacity=15.0,
            current_lat=lat if lat is not None else DEFAULT_LAT,
            current_lng=lng if lng is not None else DEFAULT_LNG,
            is_online=True,
            approval_status="approved",
            onboarding_status="approved",
            is_concierge=True,
        )
        db.session.add(contractor)
        db.session.commit()

        logger.info("RECRUIT: concierge %s registered via %s (%s)",
                    contractor.id, source, e164)

        if send_welcome:
            _welcome_sms(e164, name)

        # A new approved hauler in range may cover waitlisted demand — the same
        # reactivation the driver availability route fires.
        try:
            from flask import current_app
            import threading
            app_obj = current_app._get_current_object()
            plat = contractor.current_lat
            plng = contractor.current_lng

            def _reactivate():
                try:
                    from waitlist import notify_waitlist_for_coverage
                    notify_waitlist_for_coverage(app_obj, plat, plng)
                except Exception:
                    logger.exception("waitlist reactivation after recruit failed")

            threading.Thread(target=_reactivate, daemon=True).start()
        except Exception:
            pass

        return {"ok": True, "status": "created", "contractor_id": contractor.id,
                "message": "Registered as concierge hauler"}
    except Exception:
        logger.exception("register_concierge failed for %s", phone)
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass
        return {"ok": False, "status": "error", "contractor_id": None,
                "message": "Registration failed"}


APPLY_URL = os.environ.get("OPERATOR_APPLY_URL", "https://goumuve.com/operators")
APP_URL = os.environ.get(
    "OPERATOR_APP_URL", "https://apps.apple.com/us/app/umuve-pro/id6759131650")


def _welcome_sms(phone, name):
    """Welcome + how-it-works text to a freshly registered concierge hauler."""
    try:
        from sms_service import send_sms_async
        first = (name or "").strip().split()[0] if (name or "").strip() else "there"
        send_sms_async(
            phone,
            "Hi {}, you're on Umuve's paid-jobs list for your area. Here's how "
            "it works: we text you a job (pay + address), you reply to grab it, "
            "haul it, and we pay you same day. No app needed to start. "
            "First job coming soon. Reply STOP to opt out.".format(first),
        )
    except Exception:
        logger.exception("welcome SMS failed for %s", phone)


def send_setup_link(phone, name=None):
    """The /optext 'send setup link' message — full app + Stripe onboarding.

    Used after a hauler has proven out on concierge jobs (graduation), or by
    Trixie for someone who wants the app straight away.
    """
    try:
        from sms_service import send_sms_async
        greeting = "Hi {},".format(name.strip().split()[0]) if (name or "").strip() else "Hi there,"
        send_sms_async(
            phone,
            "{} it's Umuve (you-move) — get fully set up to get paid instantly:\n"
            "1) Apply: {}\n"
            "2) Umuve Pro app: {}\n"
            "3) Connect Stripe, then tap Go Online.\n"
            "Reply with any questions. Reply STOP to opt out.".format(
                greeting, APPLY_URL, APP_URL),
        )
        return True
    except Exception:
        logger.exception("setup-link SMS failed for %s", phone)
        return False
