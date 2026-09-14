"""Web checkout recovery uses main's Job/Payment records and checkout capability."""
from io import BytesIO
from unittest import mock
from uuid import uuid4

import pytest
from PIL import Image

from models import db, Job, Payment
from tests.test_audit_pricing import _booking_payload, _estimate, _customer, _token


@pytest.fixture(autouse=True)
def quiet_external_services(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "")
    with mock.patch("dispatcher.has_active_coverage", return_value=True), \
         mock.patch("booking_alerts.notify_booking"), \
         mock.patch("sms_service.schedule_abandoned_booking_sms"):
        yield


def payload(client):
    items = [{"category": "sofa", "quantity": 1}]
    shown = _estimate(client, items).get_json()
    return _booking_payload(items, shown["price_version"], booking_request_id=str(uuid4()))


def image_form():
    content = BytesIO()
    Image.new("RGB", (4, 4), "green").save(content, format="PNG")
    content.seek(0)
    return {"files": (content, "pickup.png")}


def test_lost_guest_create_response_reuses_job_and_payment(client):
    request = payload(client)
    first = client.post("/api/booking", json=request)
    assert first.status_code == 201, first.get_json()
    # The original estimate may expire and coverage may change after creation.
    with mock.patch("dispatcher.has_active_coverage", return_value=False):
        retry = client.post("/api/booking", json={**request, "price_version": "expired"})
    assert retry.status_code == 200, retry.get_json()
    assert retry.json["job"]["id"] == first.json["job"]["id"]
    assert retry.json["payment"]["id"] == first.json["payment"]["id"]
    assert retry.json["checkout_token"]
    assert Job.query.count() == Payment.query.count() == 1


@pytest.mark.parametrize("change", [{"notes": "Different pickup"}, {"disposition_preference": "donate"}, {"scheduledTimeSlot": "14-16"}])
def test_same_nonce_cannot_change_saved_checkout(client, change):
    request = payload(client)
    assert client.post("/api/booking", json=request).status_code == 201
    response = client.post("/api/booking", json={**request, **change})
    assert response.status_code == 409
    assert response.json["code"] == "checkout_changed"
    assert Job.query.count() == Payment.query.count() == 1


def test_recovery_is_scoped_to_authenticated_account(client):
    request = payload(client)
    a, b = _customer(), _customer()
    first = client.post("/api/booking", json=request, headers=_token(a.id))
    second = client.post("/api/booking", json=request, headers=_token(b.id))
    assert first.status_code == second.status_code == 201
    assert first.json["job"]["id"] != second.json["job"]["id"]
    assert second.json["job"]["customer_id"] == b.id


def test_concurrent_retry_primary_key_collision_recovers_committed_booking(client):
    import routes.booking as booking
    request = payload(client)
    first = client.post("/api/booking", json=request)
    original = booking._replay_web_booking
    calls = 0
    def miss_before_insert(body, user_id):
        nonlocal calls
        calls += 1
        return None if calls == 1 else original(body, user_id)
    # Reproduce a read before the other transaction commits, then PK conflict.
    with mock.patch.object(booking, "_replay_web_booking", side_effect=miss_before_insert):
        retry = client.post("/api/booking", json=request)
    assert retry.status_code == 200, retry.get_json()
    assert retry.json["job"]["id"] == first.json["job"]["id"]
    assert Job.query.count() == Payment.query.count() == 1


def test_request_nonce_requires_random_uuid(client):
    request = payload(client)
    response = client.post("/api/booking", json={**request, "booking_request_id": "public-job-id"})
    assert response.status_code == 400
    assert Job.query.count() == 0


def test_checkout_photos_require_owner_or_booking_capability(client, monkeypatch, tmp_path):
    import storage
    monkeypatch.setattr(storage, "LOCAL_UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(storage, "AWS_S3_BUCKET", None)
    booking = client.post("/api/booking", json=payload(client)).json
    path = "/api/booking/{}/photos".format(booking["job"]["id"])
    assert client.post(path, data=image_form()).status_code == 404
    assert client.post(path, data=image_form(), headers=_token(_customer().id)).status_code == 404
    response = client.post(path, data=image_form(), headers={"X-Checkout-Token": booking["checkout_token"]})
    assert response.status_code == 201, response.get_json()
    assert len(response.json["urls"]) == 1
    assert db.session.get(Job, booking["job"]["id"]).photos == response.json["urls"]


def test_uploaded_proof_uses_files_form_field(client, monkeypatch, tmp_path):
    import storage
    monkeypatch.setattr(storage, "LOCAL_UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(storage, "AWS_S3_BUCKET", None)
    headers = _token(_customer().id)
    wrong = client.post("/api/upload/photos", data={"photos": image_form()["files"]}, headers=headers)
    assert wrong.status_code == 400
    correct = client.post("/api/upload/photos", data=image_form(), headers=headers)
    assert correct.status_code == 201, correct.get_json()
    assert len(correct.json["urls"]) == 1


def test_web_earnings_include_actual_payout_and_period_filter(client):
    from tests.test_audit_pricing import _hauler, _job
    from timeutils import local_now
    from datetime import timedelta
    driver = _hauler()
    current = _job(driver=driver, status="completed")
    old = _job(driver=driver, status="completed")
    current.completed_at = local_now()
    old.completed_at = local_now() - timedelta(days=2)
    current.payment.driver_payout_amount = 144.0
    current.payment.tip_amount = 10.0
    current.payment.payout_status = "pending_connect"
    old.payment.driver_payout_amount = 80.0
    db.session.commit()
    response = client.get("/api/driver/earnings?period=today", headers=_token(driver.user_id))
    assert response.status_code == 200, response.json
    assert response.json["summary"]["total"] == 144.0
    assert response.json["summary"]["jobs_completed"] == 1
    assert response.json["records"][0]["payout_status"] == "pending_connect"
    assert response.json["records"][0]["tip"] == 10.0
    assert response.json["earnings"]["total_earned"] == 224.0  # legacy contract preserved
    assert len(response.json["weekly_chart"]) == 7


def test_checkout_cannot_attach_photos_after_payment(client):
    created = client.post("/api/booking", json=payload(client)).json
    job = db.session.get(Job, created["job"]["id"])
    job.status = "confirmed"
    db.session.commit()
    response = client.post("/api/booking/{}/photos".format(job.id), data=image_form(),
                           headers={"X-Checkout-Token": created["checkout_token"]})
    assert response.status_code == 409
    assert job.photos == []


def test_completed_pickup_can_be_reloaded_only_by_its_driver(client):
    from assignment import mint_pin
    from tests.test_audit_pricing import _hauler, _job
    driver, other = _hauler(), _hauler()
    job = _job(driver=driver, status="completed")
    _, job.completion_pin_salt, job.completion_pin_hash = mint_pin(job.id)
    job.payment.driver_payout_amount = 144.0
    job.payment.payout_status = "pending_connect"
    db.session.commit()
    path = "/api/drivers/jobs/{}".format(job.id)
    response = client.get(path, headers=_token(driver.user_id))
    assert response.status_code == 200
    assert response.json["job"]["status"] == "completed"
    assert response.json["job"]["driver_payout"] == 144.0
    assert response.json["job"]["payout_status"] == "pending_connect"
    assert response.json["job"]["completion_pin_set"] is True
    assert "completion_pin_hash" not in response.json["job"]
    assert client.get(path, headers=_token(other.user_id)).status_code == 404
    assert client.get(path, headers=_token(job.customer_id)).status_code == 404
    assert client.get(path).status_code == 401


def test_corrupt_png_returns_validation_error_without_storing_it(client, monkeypatch, tmp_path):
    import base64
    import storage
    monkeypatch.setattr(storage, "LOCAL_UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(storage, "AWS_S3_BUCKET", None)
    # PNG signature is valid, but the IDAT chunk checksum is corrupt.
    image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
    response = client.post("/api/upload/photos", data={"files": (BytesIO(image), "broken.png")}, headers=_token(_customer().id))
    assert response.status_code == 400
    assert response.json["errors"][0]["error"] == "file is not a valid image"
    assert list(tmp_path.iterdir()) == []


def test_driver_notifications_and_read_actions_are_account_scoped(client):
    from models import Notification, generate_uuid
    from tests.test_audit_pricing import _hauler
    driver, other = _hauler(), _hauler()
    first = Notification(id=generate_uuid(), user_id=driver.user_id, type="job_update", title="Pickup reminder")
    second = Notification(id=generate_uuid(), user_id=driver.user_id, type="job_update", title="Another pickup")
    foreign = Notification(id=generate_uuid(), user_id=other.user_id, type="job_update", title="Private pickup")
    db.session.add_all([first, second, foreign])
    db.session.commit()
    headers = _token(driver.user_id)
    path = "/api/driver/notifications"
    response = client.get(path + "?limit=1", headers=headers)
    assert response.status_code == 200
    assert response.json["unread_count"] == 2
    assert len(response.json["notifications"]) == 1
    assert response.json["notifications"][0]["id"] in (first.id, second.id)
    assert client.put(path + "/{}/read".format(foreign.id), headers=headers).status_code == 404
    assert client.put(path + "/{}/read".format(first.id), headers=headers).status_code == 200
    assert client.put(path + "/{}/read".format(first.id), headers=headers).status_code == 200
    assert len(client.get(path + "?include_read=true", headers=headers).json["notifications"]) == 2
    assert client.get(path, headers=headers).json["unread_count"] == 1
    assert client.put(path + "/read-all", headers=headers).status_code == 200
    assert client.get(path, headers=headers).json["notifications"] == []
    db.session.refresh(foreign)
    assert foreign.is_read is False
    assert client.get(path).status_code == 401
    assert client.get(path, headers=_token(_customer().id)).status_code == 404
