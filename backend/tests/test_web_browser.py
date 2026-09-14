"""Opt-in browser checks against the real Flask routes and scratch database.

Start the production frontend on 127.0.0.1:3107 with its API pointing at
127.0.0.1:3108, then run with UMUVE_WEB_BROWSER=1 and AGENT_BROWSER_CLI set.
Only outbound notification/payment services are stubbed; HTTP handlers,
authentication, image validation, job transitions and storage are real.
"""
import json
import os
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

from models import db, Job, Notification, generate_uuid, utcnow
from tests.test_audit_pricing import _hauler, _job, _token


@pytest.mark.skipif(os.environ.get("UMUVE_WEB_BROWSER") != "1", reason="Opt-in local browser integration")
def test_pro_browser_completion_recovery(client, app, monkeypatch, tmp_path):
    import flags
    import storage
    import eventlet
    import eventlet.wsgi
    from eventlet.green import subprocess
    from assignment import mint_pin
    from socket_events import socketio

    assert os.environ.get("AGENT_BROWSER_CLI"), "Set AGENT_BROWSER_CLI to the local agent-browser.js"
    monkeypatch.setattr(storage, "LOCAL_UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(storage, "AWS_S3_BUCKET", None)
    monkeypatch.setattr(socketio.server.eio, "cors_allowed_origins", ["http://127.0.0.1:3107"])
    photo = tmp_path.parent / (tmp_path.name + "-proof.png")
    Image.new("RGB", (8, 8), "green").save(photo)
    driver = _hauler()
    driver.is_online = False
    job = _job(driver=driver, status="arrived")
    job.arrived_at = utcnow()
    pin, job.completion_pin_salt, job.completion_pin_hash = mint_pin(job.id)
    job.payment.driver_payout_amount = 144.0
    job.payment.payout_status = "pending_connect"
    reminder = Notification(id=generate_uuid(), user_id=driver.user_id, type="job_update",
                            title="Pickup reminder", body="Your saved pickup is ready.")
    update = Notification(id=generate_uuid(), user_id=driver.user_id, type="job_update",
                          title="Pickup update", body="Check your latest pickup details.")
    other_driver = _hauler()
    foreign = Notification(id=generate_uuid(), user_id=other_driver.user_id, type="job_update",
                           title="Private pickup", body="Another driver's notification.")
    db.session.add_all([reminder, update, foreign])
    db.session.commit()
    job_id = job.id
    reminder_id = reminder.id
    update_id = update.id
    foreign_id = foreign.id
    config = {
        "user": {"id": driver.user_id, "name": "Local Pro", "email": "pro@example.test", "role": "driver"},
        "token": _token(driver.user_id)["Authorization"].removeprefix("Bearer "),
        "jobId": job_id, "pin": pin, "photoFile": str(photo),
    }
    original_flag = flags.flag
    monkeypatch.setattr(flags, "flag", lambda name: name == "completion_pin_required" or original_flag(name))
    transitions = []
    requests = []
    lost_completion = False
    socket_connected = False

    def local_api(environ, start_response):
        nonlocal lost_completion, socket_connected
        cors = [("Access-Control-Allow-Origin", "http://127.0.0.1:3107"),
                ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Checkout-Token"),
                ("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")]
        if environ["REQUEST_METHOD"] == "OPTIONS":
            start_response("204 No Content", cors)
            return [b""]
        captured = {}

        def capture(status, headers, exc_info=None):
            captured.update(status=status, headers=headers)

        result = app(environ, capture)
        try:
            body = b"".join(result)
        finally:
            if hasattr(result, "close"):
                result.close()
        if environ["PATH_INFO"].endswith("/status") and environ["REQUEST_METHOD"] == "PUT":
            response = json.loads(body)
            transitions.append(response)
            if response.get("job", {}).get("status") == "completed" and not lost_completion:
                lost_completion = True
                body = json.dumps({"error": "Test connection interrupted after completion. Retry the saved update."}).encode()
                captured.update(status="503 Service Unavailable", headers=[("Content-Type", "application/json")])
        if environ["PATH_INFO"].startswith("/socket.io/") and b'40{"sid"' in body:
            socket_connected = True
        headers = [(k, v) for k, v in captured["headers"] if not k.lower().startswith("access-control-")]
        if not environ["PATH_INFO"].startswith("/socket.io/"):
            requests.append(environ["REQUEST_METHOD"] + " " + environ["PATH_INFO"] + " " + captured["status"])
        start_response(captured["status"], headers + cors)
        return [body]

    with ExitStack() as stack:
        for target in (
            "notifications.send_push_notification", "notifications.send_driver_en_route_email",
            "notifications.send_driver_en_route_sms", "notifications.send_job_status_update_email",
            "email_service.email_job_completed", "sms_service.send_sms", "sms_service.send_sms_async",
            "dispatcher.auto_assign_job_async",
        ):
            stack.enter_context(mock.patch(target))
        payout = stack.enter_context(mock.patch("routes.payments.attempt_payout", return_value={"status": "pending_connect"}))
        listener = eventlet.listen(("127.0.0.1", 3108))
        server = eventlet.spawn(eventlet.wsgi.server, listener, local_api, log_output=False)
        try:
            script = Path(__file__).resolve().parents[2] / "platform/scripts/check-web-backend.mjs"
            result = subprocess.run(["node", str(script)], input=json.dumps(config), text=True,
                                    capture_output=True, timeout=180)
            assert result.returncode == 0, result.stdout + result.stderr + "\n" + "\n".join(requests)
            print(result.stdout)
        finally:
            server.kill()
            listener.close()

    db.session.expire_all()
    completed = db.session.get(Job, job_id)
    assert completed.status == "completed"
    assert completed.completion_pin_verified_at is not None
    assert len(completed.before_photos) == len(completed.after_photos) == 1
    assert len(list(tmp_path.iterdir())) == 2
    assert sum(row.get("job", {}).get("status") == "completed" for row in transitions) == 1
    assert {row.get("code") for row in transitions} >= {"pin_required", "pin_invalid"}
    payout.assert_called_once_with(job_id)
    assert socket_connected, "The production browser must authenticate over the backend's polling transport"
    assert db.session.get(Notification, reminder_id).is_read is True
    assert db.session.get(Notification, update_id).is_read is True
    assert db.session.get(Notification, foreign_id).is_read is False
    assert all("404 NOT FOUND" not in row for row in requests), "\n".join(requests)
