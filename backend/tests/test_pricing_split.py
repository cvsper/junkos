"""
Regression tests for the single source of truth on the payment split.

Before pricing_constants.compute_payment_split existed, the commission math was
duplicated: routes/payments.py subtracted the service fee (driver keeps ~72%)
while the volume-adjustment paths in drivers.py / jobs.py hardcoded ``* 0.20`` /
``* 0.80`` (ignoring the service fee and the operator cut). These tests lock the
split so the numbers can never drift apart again.
"""

import pytest

from pricing_constants import (
    PLATFORM_COMMISSION,
    SERVICE_FEE_RATE,
    compute_payment_split,
)


class TestPaymentSplit:
    def test_independent_hauler_250(self):
        s = compute_payment_split(250.0)
        assert s["commission"] == 50.0          # 20%
        assert s["service_fee"] == 20.0          # 8%
        assert s["operator_payout"] == 0.0
        assert s["driver_payout"] == 180.0       # 72%, NOT 80%

    def test_under_operator_umbrella_250(self):
        s = compute_payment_split(250.0, operator_rate=0.15)
        assert s["commission"] == 50.0
        assert s["service_fee"] == 20.0
        assert s["operator_payout"] == 27.0      # 15% of the $180 driver gross
        assert s["driver_payout"] == 153.0

    def test_split_always_sums_to_amount(self):
        for amount in (0, 79, 99.99, 250, 579, 1240.50):
            s = compute_payment_split(amount, operator_rate=0.15)
            total = (
                s["commission"]
                + s["service_fee"]
                + s["operator_payout"]
                + s["driver_payout"]
            )
            assert abs(total - round(float(amount), 2)) < 0.011, amount

    def test_never_negative(self):
        s = compute_payment_split(0)
        assert all(v >= 0 for v in s.values())

    def test_rates_are_canonical(self):
        # If these change intentionally, update marketing + this assertion together.
        assert PLATFORM_COMMISSION == 0.20
        assert SERVICE_FEE_RATE == 0.08
