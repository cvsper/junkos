"""
Single source of truth for the platform payment split.

Before this module the commission math was scattered: routes/payments.py used
``PLATFORM_COMMISSION``/``SERVICE_FEE_RATE`` and subtracted the service fee from
driver gross (driver keeps ~72%), while the on-site volume-adjustment paths in
routes/drivers.py and routes/jobs.py hardcoded ``* 0.20`` / ``* 0.80`` — ignoring
the service fee and the operator cut, so the Payment record desynced from the
amount actually transferred at payout.

Everything that computes a split now imports ``compute_payment_split`` so the
numbers can never drift again. Rates are env-overridable so the platform take
can be tuned in one place without a code change.
"""

import os

# Platform's cut of the gross job amount.
PLATFORM_COMMISSION = float(os.environ.get("PLATFORM_COMMISSION", "0.20"))

# Service fee — collected from the customer (baked into the quoted total in
# booking.calculate_estimate) and retained by the platform at payout.
SERVICE_FEE_RATE = float(os.environ.get("SERVICE_FEE_RATE", "0.08"))


def _env_flag(name, default=False):
    return os.environ.get(name, "true" if default else "false").lower() in (
        "1", "true", "yes", "on",
    )


# --- Auth-and-capture rollout (default OFF) ---------------------------------
# When enabled, booking authorizes a hold (capture_method="manual") instead of
# charging immediately, and the platform captures only the volume-verified
# final amount at job completion. This closes the under-declaration and the
# silent operator-skim leakage vectors: the captured amount is set by verified
# on-site volume + photo proof, not by either party's claim at booking.
#
# Leave OFF until tested in Stripe test mode (intent should show
# "requires_capture", not "succeeded") and rolled out gradually. See
# backend/payment_auth_capture.py for the full deploy path.
PAYMENT_AUTH_CAPTURE_ENABLED = _env_flag("PAYMENT_AUTH_CAPTURE_ENABLED", default=False)

# Headroom authorized above the booking estimate so an honest on-site upward
# volume adjustment can be captured without re-authorizing the card. The hold
# is up to estimate*(1+buffer); we only ever capture the verified amount, and
# capturing less than authorized is always allowed by Stripe.
PAYMENT_AUTH_BUFFER_PCT = float(os.environ.get("PAYMENT_AUTH_BUFFER_PCT", "0.25"))

# --- Proof gate (default ON) ------------------------------------------------
# Require arrival (before) photos of the load before a job can be marked
# complete, and before any downward on-site price adjustment is applied. The
# before-photo is the record of what was actually hauled — the backstop against
# both customer under-declaration and operator under-reporting. Set to "false"
# to disable (e.g. to unblock a first live test booking).
REQUIRE_COMPLETION_PHOTOS = _env_flag("REQUIRE_COMPLETION_PHOTOS", default=True)


def compute_payment_split(amount, operator_rate=0.0):
    """Return the canonical money split for a job ``amount``.

    Parameters
    ----------
    amount : float
        Gross amount the customer pays (already includes the service fee that
        was added to the quoted total).
    operator_rate : float
        Fleet-operator commission taken from the driver's gross when the job is
        run under an operator umbrella (Contractor.operator_commission_rate).
        0.0 for independent haulers.

    Returns
    -------
    dict with keys: amount, commission, service_fee, driver_gross,
    operator_payout, driver_payout. ``driver_gross`` = amount − commission −
    service_fee (what's left for the hauler side); the operator cut, if any,
    comes out of that, leaving ``driver_payout`` for the person doing the haul.
    """
    amount = round(float(amount or 0.0), 2)
    commission = round(amount * PLATFORM_COMMISSION, 2)
    service_fee = round(amount * SERVICE_FEE_RATE, 2)
    driver_gross = max(0.0, round(amount - commission - service_fee, 2))
    operator_payout = round(driver_gross * (operator_rate or 0.0), 2)
    driver_payout = max(0.0, round(driver_gross - operator_payout, 2))
    return {
        "amount": amount,
        "commission": commission,
        "service_fee": service_fee,
        "driver_gross": driver_gross,
        "operator_payout": operator_payout,
        "driver_payout": driver_payout,
    }
