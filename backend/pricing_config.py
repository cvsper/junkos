"""Single source of truth for platform economics (the take rate).

Both the dispatcher (the payout PREVIEW shown to operators before they accept)
and payments.py (the ACTUAL payout split) read from here, so the number an
operator is shown can never drift from what they're actually paid — that drift
was real: the dispatcher previewed 80% while payments paid 72%.

Two env-tunable levers, so you can set a lower "launch" take to win operator
supply in a new market without a code change (e.g. PLATFORM_COMMISSION_RATE=0.10
for the WPB launch, then raise it once the market is liquid):

    PLATFORM_COMMISSION_RATE   platform commission, default 0.20
    SERVICE_FEE_RATE           service fee,        default 0.08

Operator nets:  amount * (1 - commission - service_fee).

NOT the same thing: Contractor.operator_commission_rate is a FLEET operator's
cut of their own sub-driver's pay — a separate B2B2C relationship, not the
platform's take. Leave it alone here.
"""

import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_COMMISSION = 0.20
_DEFAULT_SERVICE_FEE = 0.08


def _rate(env_name, default):
    """Read a [0,1) rate from env; fall back to default on missing/invalid."""
    raw = os.environ.get(env_name)
    if raw is None or raw == "":
        return default
    try:
        v = float(raw)
    except (TypeError, ValueError):
        logger.warning("%s=%r is not a number; using default %.3f", env_name, raw, default)
        return default
    if not (0.0 <= v < 1.0):
        logger.warning("%s=%r out of range [0,1); using default %.3f", env_name, raw, default)
        return default
    return v


def commission_rate():
    return _rate("PLATFORM_COMMISSION_RATE", _DEFAULT_COMMISSION)


def service_fee_rate():
    return _rate("SERVICE_FEE_RATE", _DEFAULT_SERVICE_FEE)


def platform_take_rate():
    """Total fraction of the job the platform keeps (commission + service fee)."""
    return commission_rate() + service_fee_rate()


def operator_payout(amount):
    """What the operator nets on a job of size `amount`. Never raises."""
    try:
        return max(0.0, round(float(amount or 0.0) * (1.0 - platform_take_rate()), 2))
    except (TypeError, ValueError):
        return 0.0
