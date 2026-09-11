"""Inbound calls reach a person, and never ping-pong.

Maya transfers anything she can't handle to the desk line. If nobody answers,
the desk's own fallback hands it straight back to Maya, who transfers again —
the caller bounces between them and never reaches anyone. One hand-off per
caller per window; after that, take a message.
"""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db
import desk_line


@pytest.fixture(autouse=True)
def env(app):
    from models_inbound import InboundCall
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code"}):
        yield
    InboundCall.query.delete(); db.session.commit()


def _call(digits, disposition, minutes_ago=0):
    from models_inbound import InboundCall
    from models import generate_uuid
    row = InboundCall(id=generate_uuid(), call_sid="CA" + generate_uuid()[:20],
                      phone_digits=digits, kind="unknown", disposition=disposition,
                      created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                      - timedelta(minutes=minutes_ago))
    db.session.add(row); db.session.commit()
    return row


def test_a_fresh_caller_can_go_to_maya():
    assert desk_line._maya_loop_risk("9545550100") is False


def test_a_caller_maya_just_handled_is_not_sent_back():
    _call("9545550100", "to_maya", minutes_ago=1)
    assert desk_line._maya_loop_risk("9545550100") is True


def test_the_guard_expires_so_a_later_call_still_reaches_maya():
    _call("9545550100", "to_maya", minutes_ago=60)
    assert desk_line._maya_loop_risk("9545550100") is False


def test_other_dispositions_do_not_trip_the_guard():
    _call("9545550100", "answered_by_human", minutes_ago=1)
    _call("9545550100", "voicemail", minutes_ago=1)
    assert desk_line._maya_loop_risk("9545550100") is False


def test_a_different_caller_is_unaffected():
    _call("9545550100", "to_maya", minutes_ago=1)
    assert desk_line._maya_loop_risk("7865550199") is False


def test_a_broken_lookup_does_not_block_the_call():
    """If the check itself fails, the caller must still be routed."""
    with mock.patch("models_inbound.InboundCall.query", new_callable=mock.PropertyMock,
                    side_effect=RuntimeError("db down")):
        assert desk_line._maya_loop_risk("9545550100") is False


def test_blank_caller_id_never_trips_the_guard():
    assert desk_line._maya_loop_risk("") is False
    assert desk_line._maya_loop_risk(None) is False
