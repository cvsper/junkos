"""
Payment authorize-only helpers — Tier 2-F of the airtight stack (SCAFFOLD).

The current payment flow (routes/payments.py) creates PaymentIntents WITHOUT
``capture_method='manual'``, which means the customer's card is **captured
immediately** at booking time. If a contractor never accepts the job, the
customer is left with a refund to chase (today's Sy scenario, $116.64).

The airtight alternative: **authorize at booking, capture only when a
contractor accepts**. Under Stripe's auth+capture model the hold sits on
the card for up to 7 days; if we void it, the customer never sees a charge.

This file ships the helper functions (safe to import). routes/payments.py
is INTENTIONALLY UNCHANGED in this pass — switching live payment behavior
needs sevs's eyes on the diff and a tested rollout (test mode → small %
of bookings → all bookings). See "DEPLOY PATH" below.

================================================================================
DEPLOY PATH (when ready)
================================================================================

1. **Test in Stripe test mode.** Use a Stripe test secret key and create one
   booking end-to-end via the new auth path. Verify in the Stripe dashboard:
   PaymentIntent shows "requires_capture" status, not "succeeded".

2. **Decide the trigger condition.** Recommendation: use auth-only for jobs
   in any area where ``has_active_coverage()`` returns True but fewer than
   N contractors (marginal coverage). Areas with strong supply can stay on
   instant-capture for now to minimize Stripe API calls and customer
   confusion about pending charges.

3. **Wire the capture trigger.** When dispatcher.auto_assign_job finds a
   contractor and they ACCEPT the job (status transition to "accepted"),
   call ``capture_authorized_intent(payment_intent_id)``. The webhook for
   job-accepted is the natural hook.

4. **Wire the void trigger.** If a job stays unassigned for X hours past
   creation (or the customer cancels before acceptance), call
   ``void_authorized_intent``. Suggest a background sweeper that runs every
   30 min, voids holds older than 6 hours that never got captured.

5. **Update customer messaging.** Booking confirmation needs to say:
   "Your card is on hold until a hauler accepts — you'll only be charged
   then. If we can't fulfill, the hold is released within a few days."

6. **Roll out gradually.** Start with 5% of marginal-coverage bookings,
   then 25%, then 100%. Watch dispute rate, fulfillment rate, and
   customer-confusion support tickets.

================================================================================
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _stripe():
    """Return the stripe module with the API key set, or None if unconfigured."""
    try:
        import stripe
        key = os.environ.get("STRIPE_SECRET_KEY", "")
        if not key:
            logger.warning("STRIPE_SECRET_KEY not set — payment helpers will no-op")
            return None
        stripe.api_key = key
        return stripe
    except ImportError:
        logger.warning("stripe module not installed")
        return None


def create_authorize_only_intent(
    amount_cents,
    currency="usd",
    customer_id=None,
    payment_method_id=None,
    confirm=False,
    description=None,
    metadata=None,
):
    """Create a PaymentIntent with ``capture_method='manual'`` (auth-only).

    Returns the PaymentIntent dict on success, None on failure. Never raises.

    Parameters mirror stripe.PaymentIntent.create. The KEY behavioral difference
    vs. routes/payments.py is the ``capture_method='manual'`` flag — Stripe
    will authorize the amount and place a hold on the card, but will NOT
    capture (i.e. move the money) until ``capture_authorized_intent`` is
    called.
    """
    stripe = _stripe()
    if stripe is None:
        return None

    intent_kwargs = {
        "amount": int(amount_cents),
        "currency": currency,
        "capture_method": "manual",
        "confirm": bool(confirm),
        "metadata": metadata or {},
    }
    if customer_id:
        intent_kwargs["customer"] = customer_id
    if payment_method_id:
        intent_kwargs["payment_method"] = payment_method_id
    if description:
        intent_kwargs["description"] = description

    try:
        intent = stripe.PaymentIntent.create(**intent_kwargs)
        logger.info(
            "Created auth-only PaymentIntent %s (amount=%d %s, status=%s)",
            intent.id, amount_cents, currency, intent.status,
        )
        return intent
    except Exception:
        logger.exception("Failed to create auth-only PaymentIntent")
        return None


def capture_authorized_intent(payment_intent_id, amount_cents=None):
    """Capture (charge) a previously-authorized PaymentIntent.

    Called when a contractor ACCEPTS the job and we're committing to
    fulfilling. Optionally accepts ``amount_cents`` to capture less than
    the authorized amount (e.g. customer agreed to a reduced scope).

    Returns the updated PaymentIntent dict on success, None on failure.
    Never raises.
    """
    stripe = _stripe()
    if stripe is None:
        return None

    try:
        kwargs = {}
        if amount_cents is not None:
            kwargs["amount_to_capture"] = int(amount_cents)
        intent = stripe.PaymentIntent.capture(payment_intent_id, **kwargs)
        logger.info(
            "Captured PaymentIntent %s (amount=%s, status=%s)",
            payment_intent_id, amount_cents or "full", intent.status,
        )
        return intent
    except Exception:
        logger.exception(
            "Failed to capture PaymentIntent %s", payment_intent_id,
        )
        return None


def void_authorized_intent(payment_intent_id, cancellation_reason="abandoned"):
    """Cancel (void) an authorized-but-not-captured PaymentIntent.

    Called when we can't fulfill the booking (no contractor accepted in
    time, customer cancelled pre-acceptance, etc.). Releases the hold on
    the customer's card without ever charging.

    ``cancellation_reason`` is a Stripe enum: one of "duplicate", "fraudulent",
    "requested_by_customer", "abandoned".

    Returns the updated PaymentIntent dict on success, None on failure.
    Never raises.
    """
    stripe = _stripe()
    if stripe is None:
        return None

    try:
        intent = stripe.PaymentIntent.cancel(
            payment_intent_id,
            cancellation_reason=cancellation_reason,
        )
        logger.info(
            "Voided PaymentIntent %s (reason=%s, status=%s)",
            payment_intent_id, cancellation_reason, intent.status,
        )
        return intent
    except Exception:
        logger.exception(
            "Failed to void PaymentIntent %s", payment_intent_id,
        )
        return None
