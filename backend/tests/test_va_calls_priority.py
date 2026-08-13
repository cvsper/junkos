"""Fresh-queue ordering: recurring-demand categories outrank one-offs.

Within a tier, a property manager (standing monthly demand) must be served
before an estate sale company (single job), regardless of insert order.
"""

import os
from unittest import mock

import pytest

from models import db, CallProspect
from va_calls import next_card


@pytest.fixture(autouse=True)
def passcode_env():
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield


@pytest.fixture()
def queue(app):
    rows = [
        CallProspect(tier=1, category="estate sales", company="A Estate Co",
                     phone="5615550001", phone_digits="5615550001"),
        CallProspect(tier=1, category="moving company", company="B Movers",
                     phone="5615550002", phone_digits="5615550002"),
        CallProspect(tier=1, category="property management", company="C Props",
                     phone="5615550003", phone_digits="5615550003"),
        CallProspect(tier=0, category="restaurant", company="D Diner",
                     phone="5615550004", phone_digits="5615550004"),
    ]
    db.session.add_all(rows)
    db.session.commit()
    yield rows
    for r in rows:
        db.session.delete(r)
    db.session.commit()


def test_tier_still_dominates(app, queue):
    # Tier 0 one-off beats tier 1 recurring — tiers are geography/launch order.
    assert next_card().company == "D Diner"


def test_recurring_first_within_tier(app, queue):
    queue[3].status = "converted"  # take tier 0 off the board
    db.session.commit()
    order = []
    for _ in range(3):
        card = next_card()
        order.append(card.company)
        card.status = "converted"
        db.session.commit()
    # property mgmt (rank 0) → movers (rank 1 referrer) → estate sales (rank 2)
    assert order == ["C Props", "B Movers", "A Estate Co"]
