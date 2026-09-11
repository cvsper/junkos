"""A caller must never be connected to a personal phone.

Maya's prompt hardcoded a personal mobile as the transfer target for both
complaints and routine questions, and four alert paths fell back to that same
number when OPERATOR_PHONE was unset. So the owner's cell rang for anything
Maya could not handle, and no environment variable could stop it.
"""
import os
from unittest import mock

import pytest

import ops_contacts

PERSONAL = "5618883427"


@pytest.fixture(autouse=True)
def clean_env():
    keep = {k: os.environ.get(k) for k in
            ("DESK_TWILIO_NUMBER", "PUBLIC_PHONE_NUMBER", "TWILIO_FROM_NUMBER",
             "ALERT_PHONE", "ADMIN_PHONE", "OPERATOR_PHONE")}
    for k in keep:
        os.environ.pop(k, None)
    ops_contacts._warned.clear()
    yield
    for k, v in keep.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
    ops_contacts._warned.clear()


def test_no_personal_number_survives_anywhere_in_live_code():
    """The regression guard: grep the shipped source, not just one call site."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for path in root.rglob("*.py"):
        if "tests" in path.parts or path.name == "test_ops_contacts.py":
            continue
        try:
            if PERSONAL in path.read_text(errors="ignore"):
                offenders.append(str(path.relative_to(root)))
        except OSError:
            pass
    assert not offenders, "personal number hardcoded in: {}".format(offenders)


def test_human_line_prefers_the_staffed_desk_line():
    os.environ["DESK_TWILIO_NUMBER"] = "+15617824350"
    assert ops_contacts.human_line() == "+15617824350"


def test_human_line_is_empty_rather_than_a_personal_fallback():
    assert ops_contacts.human_line() == ""


def test_alert_phone_is_separate_from_the_public_line():
    os.environ["DESK_TWILIO_NUMBER"] = "+15617824350"
    os.environ["ALERT_PHONE"] = "+15615559999"
    assert ops_contacts.alert_phone() == "+15615559999"
    assert ops_contacts.human_line() != ops_contacts.alert_phone()


def test_alert_without_a_configured_phone_is_logged_not_sent():
    with mock.patch("sms_service.send_sms_async") as sms:
        assert ops_contacts.alert_sms("test", why="unit") is False
    assert sms.call_count == 0


def test_maya_transfers_to_the_desk_line():
    os.environ["DESK_TWILIO_NUMBER"] = "+15617824350"
    import importlib
    import vapi_setup
    importlib.reload(vapi_setup)
    prompt = vapi_setup.assistant_config["model"]["messages"][0]["content"]
    assert PERSONAL not in prompt
    assert "+15617824350" in prompt


def test_with_no_staffed_line_maya_takes_a_message_instead_of_transferring():
    import importlib
    import vapi_setup
    importlib.reload(vapi_setup)
    prompt = vapi_setup.assistant_config["model"]["messages"][0]["content"]
    assert "{{DESK_LINE}}" not in prompt, "an unresolved placeholder would be read aloud"
    assert PERSONAL not in prompt
    assert "schedule_callback" in prompt


def test_health_flags_the_owners_cell_in_the_ring_group():
    """DESK_FORWARD_NUMBER rings alongside the browser. If it is the private
    alert number, every customer call rings the owner's cell."""
    from unittest import mock
    import desk_health

    with mock.patch.dict(os.environ, {"DESK_FORWARD_NUMBER": "+15618883427",
                                      "ALERT_PHONE": "+15618883427"}):
        rep = desk_health.check_desk_health()
    chk = rep["checks"]["inbound_forward"]
    assert chk["state"] == "fail" and "3427" in chk["reason"]
    assert "5618883427" not in chk["reason"], "the full number must not be published"

    with mock.patch.dict(os.environ, {"DESK_FORWARD_NUMBER": "", "ALERT_PHONE": "+15618883427"}):
        rep = desk_health.check_desk_health()
    assert rep["checks"]["inbound_forward"]["state"] == "ok"
