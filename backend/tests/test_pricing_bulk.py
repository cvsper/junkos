"""Pricing-engine guards added 2026-07-17.

Covers the bulk-debris fixes: marginal construction pricing, volume-discount
exclusion for catch-all categories, optional add-on fees, and the specialty
price bumps. All through calculate_estimate — the shared core used by both
the estimate and booking endpoints.
"""
import pytest

from routes.booking import (
    ADDON_FEES,
    BULK_MARGINAL_RATES,
    calculate_estimate,
)


def _est(items, **kwargs):
    return calculate_estimate(items, **kwargs)


class TestBulkConstructionPricing:
    def test_small_construction_jobs_keep_item_pricing(self, app, db_session):
        result = _est([{"category": "construction", "quantity": 5}])
        assert result["items_subtotal"] == 5 * 45.0
        assert len(result["items"]) == 1

    def test_bulk_construction_bills_marginal_rate(self, app, db_session):
        base_qty, marginal = BULK_MARGINAL_RATES["construction"]
        result = _est([{"category": "construction", "quantity": 20}])
        expected = base_qty * 45.0 + (20 - base_qty) * marginal
        assert result["items_subtotal"] == expected  # 225 + 900 = 1125
        # Two breakdown lines: base + bulk, quantities preserved
        lines = result["items"]
        assert len(lines) == 2
        assert lines[0]["quantity"] == base_qty
        assert lines[1]["quantity"] == 20 - base_qty
        assert lines[1]["size"] == "bulk"
        assert result["total_quantity"] == 20

    def test_demo_scale_job_lands_at_market_not_consumer_prices(self, app, db_session):
        """The original leak: 20x construction quoted $777.60 all-in."""
        result = _est([{"category": "construction", "quantity": 20}])
        assert result["volume_discount"] == 0.0
        assert result["total"] > 1100.0  # was 777.60 before the guard


class TestVolumeDiscountExclusion:
    def test_catchalls_earn_no_discount(self, app, db_session):
        result = _est([{"category": "general", "quantity": 16}])
        assert result["volume_discount"] == 0.0
        assert result["volume_discount_label"] is None

    def test_real_items_still_discount(self, app, db_session):
        result = _est([{"category": "sofa", "quantity": 16}])
        assert result["volume_discount"] == round(16 * 119.0 * 0.20, 2)

    def test_mixed_cart_discounts_only_eligible_lines(self, app, db_session):
        result = _est([
            {"category": "sofa", "quantity": 4},       # eligible: 4 items, $476
            {"category": "general", "quantity": 12},   # excluded
        ])
        # Tier comes from eligible quantity (4 -> 10%), applied to $476 only.
        assert result["volume_discount"] == round(4 * 119.0 * 0.10, 2)


class TestAddons:
    def test_addons_add_flat_fees(self, app, db_session):
        base = _est([{"category": "sofa", "quantity": 2}])
        with_addons = _est(
            [{"category": "sofa", "quantity": 2}],
            addons={"disassembly_items": 2, "stair_flights": 3},
        )
        expected = 2 * ADDON_FEES["disassembly_items"] + 3 * ADDON_FEES["stair_flights"]
        assert with_addons["addons_total"] == expected
        assert with_addons["total"] == round(base["total"] + expected, 2)
        assert len(with_addons["addons"]) == 2

    def test_missing_or_garbage_addons_are_ignored(self, app, db_session):
        result = _est(
            [{"category": "sofa", "quantity": 1}],
            addons={"stair_flights": "lots", "unknown_addon": 5},
        )
        assert result["addons_total"] == 0.0
        assert result["addons"] == []


class TestSpecialtyPriceBumps:
    @pytest.mark.parametrize("category,price", [("hot_tub", 549.0), ("piano", 399.0)])
    def test_specialty_prices(self, app, db_session, category, price):
        result = _est([{"category": category, "quantity": 1}])
        assert result["items_subtotal"] == price

    def test_large_hot_tub_tier(self, app, db_session):
        """Large tubs (7-9 ft / 6-8 seats / raised deck) price via size=large."""
        large = _est([{"category": "hot_tub", "quantity": 1, "size": "large"}])
        assert large["items_subtotal"] == 699.0
        # unknown / small / medium sizes all fall back to the standard tier
        for size in ("small", "medium", "weird"):
            assert _est([{"category": "hot_tub", "quantity": 1, "size": size}])["items_subtotal"] == 549.0
