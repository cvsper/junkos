"""Naming an item is not the same as pricing it.

The picker sends a generic bucket as `category` and keeps the real item in
`name`: {"category": "appliances", "name": "Refrigerator"}. The engine priced
the bucket, so a fridge was charged as a generic appliance and — worse —
RECYCLING_FEE_TRIGGERS never fired, because those are keyed to "refrigerator"
and "tv_console". Job AFB22IMO went out at $307.80 for a sofa, fridge,
flat-screen and bags with no freon recovery and no e-waste fee.
"""
import os
from unittest import mock

import pytest

from routes.booking import (
    resolve_item_category, calculate_estimate, CATEGORY_PRICES, RECYCLING_FEES,
)


@pytest.fixture(autouse=True)
def env(app):
    yield


def test_a_named_item_resolves_to_its_own_category():
    assert resolve_item_category({"category": "appliances", "name": "Refrigerator"}) == "refrigerator"
    assert resolve_item_category({"category": "furniture", "name": "Couch / Sofa"}) == "sofa"
    assert resolve_item_category({"category": "electronics", "name": "TV (flat screen)"}) == "tv_flatscreen"
    assert resolve_item_category({"category": "electronics", "name": "TV (CRT / tube)"}) == "tv_console"


def test_an_explicit_specific_category_always_wins():
    """A client that already sends the right category must not be second-guessed."""
    assert resolve_item_category({"category": "sofa_sectional", "name": "Couch / Sofa"}) == "sofa_sectional"


def test_unknown_names_stay_on_their_generic_bucket():
    """Only map where there is a real specific price — never invent one."""
    assert resolve_item_category({"category": "appliances", "name": "Water Heater"}) == "appliances"
    assert resolve_item_category({"category": "general", "name": "Bags of Junk"}) == "general"
    assert resolve_item_category({"category": "furniture"}) == "furniture"
    assert resolve_item_category("not a dict") == "other"


def test_the_sofa_is_charged_as_a_sofa():
    generic = calculate_estimate([{"category": "furniture", "quantity": 1, "name": "Couch / Sofa"}])
    named = calculate_estimate([{"category": "sofa", "quantity": 1}])
    assert generic["total"] == named["total"]
    assert generic["total"] > calculate_estimate(
        [{"category": "furniture", "quantity": 1}])["total"], "a named sofa must beat the bucket"


def test_a_fridge_in_a_generic_bucket_still_pays_freon_recovery():
    est = calculate_estimate([{"category": "appliances", "quantity": 1, "name": "Refrigerator"}])
    assert est["recycling_fees"] == RECYCLING_FEES["appliance_freon"]


def test_the_job_that_exposed_this_prices_correctly_now():
    """AFB22IMO's exact cart: sofa, fridge, flat-screen, bags."""
    cart = [
        {"category": "furniture", "quantity": 1, "name": "Couch / Sofa"},
        {"category": "appliances", "quantity": 1, "name": "Refrigerator"},
        {"category": "electronics", "quantity": 1, "name": "TV (flat screen)"},
        {"category": "general", "quantity": 1, "name": "Bags of Junk"},
    ]
    fixed = calculate_estimate(cart)
    before = calculate_estimate([{k: v for k, v in i.items() if k != "name"} for i in cart])
    assert fixed["total"] > before["total"]
    # the fridge's freon recovery is now charged; it was silently absorbed
    assert fixed["recycling_fees"] >= RECYCLING_FEES["appliance_freon"]
    assert before["recycling_fees"] == 0.0


def test_quantities_still_multiply_correctly():
    one = calculate_estimate([{"category": "appliances", "quantity": 1, "name": "Refrigerator"}])
    two = calculate_estimate([{"category": "appliances", "quantity": 2, "name": "Refrigerator"}])
    assert two["total"] > one["total"]
    assert two["recycling_fees"] == 2 * RECYCLING_FEES["appliance_freon"]
