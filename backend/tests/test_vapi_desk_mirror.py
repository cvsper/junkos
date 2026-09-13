"""Calls Maya takes on the toll-free line show up on the desk: the end-of-call
report mirrors an InboundCall (source maya) that the leads panel and the
analytics can see, and the follow-up texts point at a live number."""
from unittest import mock

from models import db
from models_inbound import InboundCall
import routes.vapi as vapi
import leads


def _report(call_id, number, secs=7, call_type="inboundPhoneCall"):
    return {"call": {"id": call_id, "customer": {"number": number}, "type": call_type,
                     "startedAt": "2026-09-13T15:41:04Z", "endedAt": "2026-09-13T15:41:%02dZ" % (4 + secs)},
            "durationSeconds": secs, "summary": "Caller hung up during the greeting.", "messages": [], "transcript": ""}


def test_maya_line_call_lands_on_the_desk(app, db_session):
    with mock.patch("sms_service.send_sms_async"):
        vapi._handle_end_of_call_report(_report("vapi-1", "+19543148782"))
    row = InboundCall.query.filter_by(phone_digits="9543148782").one()
    assert row.source == "maya" and row.disposition == "to_maya" and row.duration == 7 and row.call_sid == "vapi:vapi-1"
    assert row.kind in ("customer", "unknown") and row.outcome == "none"
    lead = [l for l in leads.collect(days=1)[0] if l["phone_digits"] == "9543148782"]
    assert lead and lead[0]["source"] == "maya"


def test_desk_logged_calls_are_not_double_counted(app, db_session):
    db.session.add(InboundCall(call_sid="CAdesk1", phone_digits="9543148799", kind="unknown", disposition="to_maya", source="desk"))
    db.session.commit()
    with mock.patch("sms_service.send_sms_async"):
        vapi._handle_end_of_call_report(_report("vapi-2", "+19543148799"))
        vapi._handle_end_of_call_report(_report("vapi-3", "+15615550123", call_type="outboundPhoneCall"))
    assert InboundCall.query.filter_by(phone_digits="9543148799").count() == 1
    assert InboundCall.query.filter_by(phone_digits="5615550123").count() == 0


def test_follow_up_texts_use_the_live_number(app, db_session):
    with mock.patch("sms_service.send_sms_async") as send:
        vapi._handle_end_of_call_report(_report("vapi-4", "+19545550101"))
    bodies = " ".join(str(c.args[1]) for c in send.call_args_list)
    assert "(844) 435-6005" in bodies and "944-1636" not in bodies
