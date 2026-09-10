"""Audit remediation tests — F03 (socket auth), F21 (operator data / tracking),
F22 (uploads + SSRF), F29 (ratings).

Each attack scenario from the audit is exercised the way an attacker would
run it and must now fail; the legitimate flows next to it must still work.
"""

import io
import time
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from auth_routes import generate_token
from models import (
    db, User, Contractor, Job, Rating, ChatMessage, generate_uuid,
)

_seq = iter(range(1, 100000))


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _user(role="customer", status="active", name="Pat Customer"):
    n = next(_seq)
    u = User(id=generate_uuid(), name=name, role=role, status=status,
             email="u{}@test.local".format(n), phone="+1561555{:04d}".format(n % 10000))
    db.session.add(u)
    db.session.flush()
    return u


def _contractor(user=None, **kw):
    user = user or _user(role="driver", name="Sam Hauler")
    fields = dict(is_online=True, truck_type="Box truck", stripe_connect_id="acct_secret",
                  drivers_license_url="/api/documents/file/dl.jpg",
                  insurance_document_url="https://bucket.s3.us-east-1.amazonaws.com/onboarding/ins.pdf",
                  rejection_reason="n/a")
    fields.update(kw)
    c = Contractor(id=generate_uuid(), user_id=user.id, approval_status="approved", **fields)
    db.session.add(c)
    db.session.flush()
    return c


def _job(customer, contractor=None, status="assigned", scheduled=None, **kw):
    fields = dict(lat=26.6, lng=-80.1)
    fields.update(kw)
    j = Job(id=generate_uuid(), customer_id=customer.id, status=status,
            address="1 Main St, Lake Worth, FL", total_price=120.0,
            driver_id=contractor.id if contractor else None,
            scheduled_at=scheduled or datetime.now(timezone.utc) + timedelta(hours=2),
            confirmation_code="C{:07d}".format(next(_seq)), **fields)
    db.session.add(j)
    db.session.commit()
    return j


def _bearer(user):
    return {"Authorization": "Bearer " + generate_token(user.id)}


def _sock(app, user=None, **kw):
    from socket_events import socketio
    auth = {"token": generate_token(user.id)} if user else None
    return socketio.test_client(app, auth=auth, **kw)


def _events(client, name):
    return [m for m in client.get_received() if m["name"] == name]


# ===========================================================================
# F03 — Socket authentication / authorisation
# ===========================================================================
class TestSocketAuth:
    def test_unauthenticated_connect_is_rejected(self, app, db_session):
        c = _sock(app, None)
        assert not c.is_connected()

    def test_garbage_token_is_rejected(self, app, db_session):
        from socket_events import socketio
        c = socketio.test_client(app, auth={"token": "not-a-jwt"})
        assert not c.is_connected()

    def test_expired_token_is_rejected(self, app, db_session):
        import jwt as pyjwt
        from auth_routes import JWT_SECRET
        from socket_events import socketio
        u = _user()
        tok = pyjwt.encode({"user_id": u.id, "exp": datetime.utcnow() - timedelta(minutes=1)},
                           JWT_SECRET, algorithm="HS256")
        c = socketio.test_client(app, auth={"token": tok})
        assert not c.is_connected()

    def test_deleted_user_is_rejected(self, app, db_session):
        u = _user(status="deleted")
        assert not _sock(app, u).is_connected()

    def test_valid_token_connects_via_auth_query_and_header(self, app, db_session):
        from socket_events import socketio
        u = _user()
        tok = generate_token(u.id)
        assert socketio.test_client(app, auth={"token": tok}).is_connected()
        assert socketio.test_client(app, query_string="token=" + tok).is_connected()
        assert socketio.test_client(app, headers={"Authorization": "Bearer " + tok}).is_connected()

    def test_customer_cannot_join_another_customers_job_room(self, app, db_session):
        victim, attacker = _user(), _user()
        job = _job(victim)
        c = _sock(app, attacker)
        c.emit("join", {"room": job.id})
        assert _events(c, "join:denied")
        assert not _events(c, "joined")
        c.emit("customer:join", {"job_id": job.id})
        assert len(_events(c, "join:denied")) == 1
        assert not _events(c, "joined")

    def test_customer_joins_own_job_room(self, app, db_session):
        cust = _user()
        job = _job(cust)
        c = _sock(app, cust)
        c.emit("join", {"room": job.id})
        assert _events(c, "joined") == [{"name": "joined", "args": [{"room": job.id}], "namespace": "/"}]
        c.emit("customer:join", {"job_id": job.id})
        assert _events(c, "joined")

    def test_admin_room_requires_admin_role(self, app, db_session):
        c = _sock(app, _user())
        c.emit("admin:join")
        assert _events(c, "join:denied")
        c.emit("join", {"room": "admin"})
        assert len(_events(c, "join:denied")) == 1
        a = _sock(app, _user(role="admin"))
        a.emit("admin:join")
        assert _events(a, "joined")

    def test_driver_room_only_for_that_contractor(self, app, db_session):
        mine, other = _contractor(), _contractor()
        c = _sock(app, db.session.get(User, mine.user_id))
        c.emit("join", {"room": "driver:" + other.id})
        assert _events(c, "join:denied")
        c.emit("join", {"room": "driver:" + mine.id})
        assert _events(c, "joined")
        c.emit("operator:join", {"operator_id": other.id})
        assert len(_events(c, "join:denied")) == 1
        c.emit("operator:join", {})
        assert _events(c, "joined")[-1]["args"][0]["room"] == "operator:" + mine.id

    def test_forged_driver_location_from_customer_is_rejected(self, app, db_session):
        cust = _user()
        victim = _contractor()
        victim.current_lat, victim.current_lng = 26.0, -80.0
        db.session.commit()
        c = _sock(app, cust)
        c.emit("driver:location", {"contractor_id": victim.id, "lat": 0.0, "lng": 0.0})
        assert _events(c, "error")
        db.session.refresh(victim)
        assert (victim.current_lat, victim.current_lng) == (26.0, -80.0)

    def test_contractor_cannot_spoof_another_contractor_id(self, app, db_session):
        me, victim = _contractor(), _contractor()
        victim.current_lat = 26.0
        db.session.commit()
        c = _sock(app, db.session.get(User, me.user_id))
        c.emit("driver:location", {"contractor_id": victim.id, "lat": 1.0, "lng": 1.0})
        assert _events(c, "error")
        db.session.refresh(victim)
        assert victim.current_lat == 26.0

    def test_driver_location_rejects_unassigned_or_inactive_job(self, app, db_session):
        import socket_events
        me = _contractor()
        other_job = _job(_user(), _contractor(), status="en_route")
        done_job = _job(_user(), me, status="completed")
        c = _sock(app, db.session.get(User, me.user_id))
        socket_events._LAST_LOCATION_WRITE.clear()
        c.emit("driver:location", {"lat": 26.1, "lng": -80.1, "job_id": other_job.id})
        c.emit("driver:location", {"lat": 26.1, "lng": -80.1, "job_id": done_job.id})
        assert len(_events(c, "error")) == 2
        db.session.refresh(me)
        assert me.current_lat is None

    def test_driver_location_validates_ranges(self, app, db_session):
        import socket_events
        me = _contractor()
        c = _sock(app, db.session.get(User, me.user_id))
        socket_events._LAST_LOCATION_WRITE.clear()
        for lat, lng in ((91, 0), (-91, 0), (0, 181), (0, -181), ("x", 1), (None, 1), (float("nan"), 0)):
            c.emit("driver:location", {"lat": lat, "lng": lng})
        assert len(_events(c, "error")) == 7
        db.session.refresh(me)
        assert me.current_lat is None

    def test_driver_location_happy_path_and_rate_limit(self, app, db_session):
        import socket_events
        me = _contractor()
        cust = _user()
        job = _job(cust, me, status="en_route")
        d = _sock(app, db.session.get(User, me.user_id))
        watcher = _sock(app, cust)
        watcher.emit("join", {"room": job.id})
        watcher.get_received()
        socket_events._LAST_LOCATION_WRITE.clear()
        d.emit("driver:location", {"lat": 26.5, "lng": -80.05, "job_id": job.id})
        db.session.refresh(me)
        assert (me.current_lat, me.current_lng) == (26.5, -80.05)
        got = _events(watcher, "driver:location")
        assert got and got[0]["args"][0] == {"contractor_id": me.id, "lat": 26.5, "lng": -80.05}
        # A second write within 1s is dropped, no error, no broadcast
        d.emit("driver:location", {"lat": 27.0, "lng": -81.0, "job_id": job.id})
        db.session.refresh(me)
        assert me.current_lat == 26.5
        assert not _events(watcher, "driver:location")
        # After the interval it is accepted again
        socket_events._LAST_LOCATION_WRITE[me.id] = time.monotonic() - 2
        d.emit("driver:location", {"lat": 27.0, "lng": -81.0, "job_id": job.id})
        db.session.refresh(me)
        assert me.current_lat == 27.0

    def test_chat_send_uses_server_identity_and_membership(self, app, db_session):
        cust, outsider = _user(), _user()
        hauler = _contractor()
        job = _job(cust, hauler)
        o = _sock(app, outsider)
        o.emit("chat:send", {"job_id": job.id, "sender_id": cust.id, "sender_role": "customer", "message": "hi"})
        assert _events(o, "chat:error")
        assert ChatMessage.query.filter_by(job_id=job.id).count() == 0

        c = _sock(app, cust)
        c.emit("join", {"room": job.id})
        # claims to be the driver — server derives 'customer' from the session
        c.emit("chat:send", {"job_id": job.id, "sender_id": hauler.user_id, "sender_role": "driver", "message": "hi"})
        msgs = ChatMessage.query.filter_by(job_id=job.id).all()
        assert len(msgs) == 1 and msgs[0].sender_id == cust.id and msgs[0].sender_role == "customer"
        assert _events(c, "chat:message")[0]["args"][0]["sender_role"] == "customer"

    def test_chat_typing_and_read_require_membership(self, app, db_session):
        cust, outsider = _user(), _user()
        hauler = _contractor()
        job = _job(cust, hauler)
        db.session.add(ChatMessage(id=generate_uuid(), job_id=job.id, sender_id=hauler.user_id,
                                   sender_role="driver", message="on my way"))
        db.session.commit()
        c = _sock(app, cust)
        c.emit("join", {"room": job.id})
        c.get_received()
        o = _sock(app, outsider)
        o.emit("chat:typing", {"job_id": job.id, "sender_id": cust.id, "sender_role": "customer", "is_typing": True})
        o.emit("chat:read", {"job_id": job.id, "reader_role": "customer"})
        assert not _events(c, "chat:typing") and not _events(c, "chat:read")
        assert ChatMessage.query.filter_by(job_id=job.id).first().read_at is None
        c.emit("chat:read", {"job_id": job.id, "reader_role": "driver"})  # role claim ignored
        got = _events(c, "chat:read")
        assert got and got[0]["args"][0]["read_by"] == "customer"

    def test_no_coordinates_job_goes_to_admin_room_only(self, app, db_session):
        import socket_events
        job = _job(_user(), lat=None, lng=None)
        with mock.patch.object(socket_events.socketio, "emit") as em:
            socket_events.notify_nearby_drivers(job)
        em.assert_called_once()
        assert em.call_args.kwargs.get("room") == "admin"


# ===========================================================================
# F21 — operator data exposure + perpetual tracking
# ===========================================================================
_PRIVATE_KEYS = {
    "stripe_connect_id", "drivers_license_url", "insurance_document_url",
    "vehicle_registration_url", "license_url", "insurance_url", "insurance_expiry",
    "license_expiry", "rejection_reason", "availability_schedule", "user", "user_id",
    "email", "phone", "onboarding_status", "background_check_status",
}


class TestOperatorDataAndTracking:
    def test_customer_job_detail_has_arrival_profile_only(self, client, db_session):
        cust = _user()
        hauler = _contractor()
        job = _job(cust, hauler)
        r = client.get("/api/jobs/" + job.id, headers=_bearer(cust))
        assert r.status_code == 200, r.get_json()
        contractor = r.get_json()["job"]["contractor"]
        assert contractor["first_name"] == "Sam"
        assert contractor["vehicle"] == "Box truck"
        assert not (_PRIVATE_KEYS & set(contractor)), contractor

    def test_public_booking_status_is_sanitised(self, client, db_session):
        cust = _user()
        hauler = _contractor()
        job = _job(cust, hauler, reminder_call_id="call_123", lead_source="meta")
        r = client.get("/api/booking/" + job.id)
        assert r.status_code == 200
        b = r.get_json()["booking"]
        assert "reminder_call_id" not in b and "lead_source" not in b and "driver_id" not in b
        assert not (_PRIVATE_KEYS & set(b["contractor"]))
        assert b["tracking_url"].startswith("https://app.goumuve.com/track/code/")

    def test_tracking_requires_token_or_participant(self, client, db_session):
        cust, stranger = _user(), _user()
        hauler = _contractor()
        job = _job(cust, hauler, status="en_route")
        assert client.get("/api/tracking/" + job.id).status_code == 401
        assert client.get("/api/tracking/" + job.id + "?t=123.deadbeef").status_code == 401
        assert client.get("/api/tracking/" + job.id, headers=_bearer(stranger)).status_code == 401
        assert client.get("/api/tracking/" + job.id + "/driver-location").status_code == 401
        assert client.get("/api/tracking/code/" + job.confirmation_code).status_code == 401
        # participants via JWT
        assert client.get("/api/tracking/" + job.id, headers=_bearer(cust)).status_code == 200
        assert client.get("/api/tracking/" + job.id,
                          headers=_bearer(db.session.get(User, hauler.user_id))).status_code == 200
        # the texted link's token
        token = job.tracking_url().split("?t=")[1]
        r = client.get("/api/tracking/code/{}?t={}".format(job.confirmation_code, token))
        assert r.status_code == 200
        hauler_view = r.get_json()["tracking"]["hauler"]
        assert hauler_view["first_name"] == "Sam" and not (_PRIVATE_KEYS & set(hauler_view))
        # token for one job doesn't open another
        other = _job(cust, hauler)
        assert client.get("/api/tracking/{}?t={}".format(other.id, token)).status_code == 401

    def test_token_expires(self, client, db_session):
        from tracking_token import make_tracking_token, verify_tracking_token
        job = _job(_user())
        stale = make_tracking_token(job.id, int(time.time()) - 10)
        assert not verify_tracking_token(job.id, stale)
        assert client.get("/api/tracking/{}?t={}".format(job.id, stale)).status_code == 401
        assert not verify_tracking_token(job.id, make_tracking_token(job.id, int(time.time()) + 100)[:-2] + "zz")

    def test_location_only_while_active(self, client, db_session):
        cust = _user()
        hauler = _contractor()
        hauler.current_lat, hauler.current_lng = 26.7, -80.2
        db.session.commit()
        active = _job(cust, hauler, status="en_route")
        done = _job(cust, hauler, status="completed")
        cancelled = _job(cust, hauler, status="cancelled")
        stale = _job(cust, hauler, status="en_route",
                     scheduled=datetime.now(timezone.utc) - timedelta(hours=7))
        h = _bearer(cust)

        r = client.get("/api/tracking/" + active.id, headers=h).get_json()["tracking"]
        assert r["driver"]["lat"] == 26.7 and r["location_live"] is True
        assert not (_PRIVATE_KEYS & set(r["driver"]))
        loc = client.get("/api/tracking/" + active.id + "/driver-location", headers=h).get_json()
        assert loc["location"]["lat"] == 26.7 and loc["location"]["driver_name"] == "Sam"

        for j in (done, cancelled, stale):
            t = client.get("/api/tracking/" + j.id, headers=h).get_json()["tracking"]
            assert t["driver"]["lat"] is None and t["driver"]["lng"] is None and t["location_live"] is False
            loc = client.get("/api/tracking/" + j.id + "/driver-location", headers=h).get_json()
            assert loc["location"] is None

    def test_serializer_contract(self, db_session):
        from serializers import contractor_public_arrival, job_for_customer
        hauler = _contractor()
        prof = contractor_public_arrival(hauler)
        assert set(prof) == {"id", "first_name", "photo_url", "avg_rating", "total_jobs",
                             "vehicle", "vehicle_photo_url", "plate_last3"}
        job = _job(_user(), hauler)
        data = job_for_customer(job)
        assert data["contractor"] == prof and "?t=" in data["tracking_url"]
        assert "noshow_t30_alerted" not in data and "operator_id" not in data


# ===========================================================================
# F22 — uploads + SSRF
# ===========================================================================
def _png(size=(4, 4), mode="RGB"):
    from PIL import Image
    buf = io.BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 120)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_with_exif():
    from PIL import Image
    img = Image.new("RGB", (6, 6), (1, 2, 3))
    exif = img.getexif()
    exif[0x010F] = "SpyPhone"           # Make
    exif[0x0110] = "Model X"            # Model
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


class TestUploadTrustBoundary:
    def test_mime_spoof_rejected(self, client, db_session, tmp_path, monkeypatch):
        import storage
        monkeypatch.setattr(storage, "LOCAL_UPLOAD_FOLDER", str(tmp_path))
        cust = _user()
        # HTML disguised as a jpg, and a real PDF disguised as a png
        spoofs = [(b"<html><script>alert(1)</script></html>", "evil.jpg"),
                  (b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj", "doc.png")]
        for data, name in spoofs:
            r = client.post("/api/upload/photos", headers=_bearer(cust),
                            data={"files": (io.BytesIO(data), name, "image/jpeg")},
                            content_type="multipart/form-data")
            assert r.status_code == 400, r.get_json()
            assert r.get_json()["success"] is False
        assert not list(tmp_path.iterdir())

    def test_real_image_is_reencoded_and_exif_stripped(self, client, db_session, tmp_path, monkeypatch):
        import storage
        from PIL import Image
        monkeypatch.setattr(storage, "LOCAL_UPLOAD_FOLDER", str(tmp_path))
        cust = _user()
        r = client.post("/api/upload/photos", headers=_bearer(cust),
                        data={"files": [(io.BytesIO(_jpeg_with_exif()), "photo.jpg", "text/html"),
                                        (io.BytesIO(_png(mode="RGBA")), "shot.jpg")]},
                        content_type="multipart/form-data")
        assert r.status_code == 201, r.get_json()
        urls = r.get_json()["urls"]
        assert len(urls) == 2
        assert urls[0].endswith(".jpg") and urls[1].endswith(".png")   # server-chosen by content
        stored = Image.open(tmp_path / urls[0].rsplit("/", 1)[1])
        assert stored.format == "JPEG" and not stored.getexif()
        # and the public route serves it
        assert client.get(urls[0]).status_code == 200

    def test_validate_upload_limits(self, monkeypatch):
        import storage
        from storage import validate_upload, UploadValidationError
        with pytest.raises(UploadValidationError):
            validate_upload(io.BytesIO(b""), kind="image", filename="a.jpg")
        with pytest.raises(UploadValidationError):   # declared pdf, content image
            validate_upload(io.BytesIO(_png()), filename="scan.pdf")
        with pytest.raises(UploadValidationError):   # image endpoint refuses pdf
            validate_upload(io.BytesIO(b"%PDF-1.7\n"), kind="image", filename="x.pdf")
        monkeypatch.setattr(storage, "MAX_IMAGE_DIM", 3)
        with pytest.raises(UploadValidationError):
            validate_upload(io.BytesIO(_png(size=(4, 4))), kind="image", filename="big.png")
        monkeypatch.setattr(storage, "MAX_IMAGE_DIM", 8000)
        with pytest.raises(UploadValidationError):
            validate_upload(io.BytesIO(_png()), kind="image", filename="a.png", max_bytes=10)
        doc = validate_upload(io.BytesIO(b"%PDF-1.7\n%%EOF"), kind="document", filename="ins.pdf")
        assert (doc.ext, doc.content_type) == ("pdf", "application/pdf")

    def test_private_documents_need_auth_and_ownership(self, client, db_session, tmp_path, monkeypatch):
        import storage
        monkeypatch.setattr(storage, "LOCAL_PRIVATE_FOLDER", str(tmp_path / "priv"))
        monkeypatch.setattr(storage, "LOCAL_UPLOAD_FOLDER", str(tmp_path / "pub"))
        url = storage.save_file(io.BytesIO(_png()), prefix="onboarding", filename="license.png")
        assert url.startswith("/api/documents/file/")
        name = url.rsplit("/", 1)[1]
        assert (tmp_path / "priv" / name).exists() and not (tmp_path / "pub").exists()
        # not reachable through the public photo route
        assert client.get("/uploads/" + name).status_code == 404

        owner_user = _user(role="driver")
        c = _contractor(user=owner_user, drivers_license_url=url)
        other = _user(role="driver")
        admin = _user(role="admin")
        doc = "/api/documents/contractor/{}/drivers_license".format(c.id)
        assert client.get(doc).status_code == 401
        assert client.get(url).status_code == 401
        assert client.get(doc, headers=_bearer(other)).status_code == 404
        assert client.get(url, headers=_bearer(other)).status_code == 404
        assert client.get(doc, headers=_bearer(owner_user)).status_code == 200
        assert client.get(url, headers=_bearer(owner_user)).status_code == 200
        r = client.get(doc, headers=_bearer(admin))
        assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"

    def test_s3_documents_redirect_to_presigned_url(self, client, db_session, monkeypatch):
        import storage
        monkeypatch.setattr(storage, "AWS_S3_BUCKET", "umuve-docs")
        fake = mock.MagicMock()
        fake.generate_presigned_url.return_value = "https://umuve-docs.s3.amazonaws.com/onboarding/x.pdf?X-Amz-Signature=abc"
        monkeypatch.setattr(storage, "_get_s3_client", lambda: fake)
        admin = _user(role="admin")
        c = _contractor(insurance_document_url="https://umuve-docs.s3.us-east-1.amazonaws.com/onboarding/x.pdf")
        r = client.get("/api/documents/contractor/{}/insurance".format(c.id), headers=_bearer(admin))
        assert r.status_code == 302 and "X-Amz-Signature" in r.headers["Location"]
        assert fake.generate_presigned_url.call_args.kwargs["Params"] == {"Bucket": "umuve-docs", "Key": "onboarding/x.pdf"}
        assert fake.generate_presigned_url.call_args.kwargs["ExpiresIn"] <= 600


class TestSafeFetch:
    def test_blocks_metadata_and_private_literals(self):
        from netsafe import safe_fetch, UnsafeURLError
        with mock.patch("netsafe.requests.get") as get:
            for url in ("http://169.254.169.254/latest/meta-data/", "http://10.0.0.1/", "http://127.0.0.1:5050/",
                        "http://192.168.1.1/", "http://172.16.0.1/", "http://100.64.0.1/", "http://[::1]/",
                        "http://[fe80::1]/", "http://[fc00::1]/", "http://0.0.0.0/", "http://localhost/",
                        "file:///etc/passwd", "ftp://example.com/x", "http://user:pw@example.com/"):
                with pytest.raises(UnsafeURLError):
                    safe_fetch(url, max_bytes=1024)
            get.assert_not_called()

    def test_blocks_hostnames_resolving_to_private(self):
        from netsafe import safe_fetch, UnsafeURLError
        with mock.patch("netsafe.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.1", 80))]), \
             mock.patch("netsafe.requests.get") as get:
            with pytest.raises(UnsafeURLError):
                safe_fetch("http://evil.example.com/img.jpg", max_bytes=1024)
            get.assert_not_called()

    def _resp(self, status, headers=None, body=b""):
        r = mock.MagicMock()
        r.status_code = status
        r.is_redirect = status in (301, 302, 303, 307, 308)
        r.headers = headers or {}
        r.iter_content = lambda chunk_size: iter([body[i:i + chunk_size] for i in range(0, len(body), chunk_size)])
        r.raise_for_status = lambda: None
        return r

    def test_redirect_to_private_is_blocked_and_hops_capped(self):
        from netsafe import safe_fetch, UnsafeURLError
        public = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with mock.patch("netsafe.socket.getaddrinfo", return_value=public), \
             mock.patch("netsafe.requests.get") as get:
            get.return_value = self._resp(302, {"Location": "http://169.254.169.254/latest/"})
            with pytest.raises(UnsafeURLError):
                safe_fetch("http://example.com/a", max_bytes=1024)
            assert get.call_count == 1
            get.reset_mock()
            get.return_value = self._resp(302, {"Location": "http://example.com/loop"})
            with pytest.raises(UnsafeURLError, match="redirects"):
                safe_fetch("http://example.com/a", max_bytes=1024)
            assert get.call_count == 4  # original + 3 hops, then refused
            assert all(c.kwargs["allow_redirects"] is False and c.kwargs["stream"] is True
                       for c in get.call_args_list)

    def test_byte_cap_and_success(self):
        from netsafe import safe_fetch, UnsafeURLError
        public = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with mock.patch("netsafe.socket.getaddrinfo", return_value=public), \
             mock.patch("netsafe.requests.get") as get:
            get.return_value = self._resp(200, {"Content-Type": "image/png; charset=x"}, b"x" * 2000)
            with pytest.raises(UnsafeURLError, match="exceeds"):
                safe_fetch("https://example.com/big", max_bytes=1000)
            get.return_value = self._resp(200, {"Content-Type": "image/png"}, b"ok")
            assert safe_fetch("https://example.com/small", max_bytes=1000) == (b"ok", "image/png")

    def test_quotes_and_doc_verifier_use_the_guard(self):
        from routes.quotes import _image_to_inline
        import operator_doc_verifier as odv
        with mock.patch("netsafe.requests.get") as get:
            assert _image_to_inline({"kind": "url", "value": "http://169.254.169.254/latest/"}) == (None, None)
            assert odv._load_image("http://10.0.0.1:5050/memory") == (None, None)
            get.assert_not_called()


# ===========================================================================
# F29 — ratings
# ===========================================================================
class TestRatings:
    def test_outsider_gets_403(self, client, db_session):
        cust, outsider = _user(), _user()
        hauler = _contractor()
        job = _job(cust, hauler, status="completed")
        r = client.post("/api/ratings", headers=_bearer(outsider), json={"job_id": job.id, "stars": 1})
        assert r.status_code == 403
        assert Rating.query.count() == 0
        # another (unassigned) hauler is an outsider too
        r = client.post("/api/ratings", headers=_bearer(db.session.get(User, _contractor().user_id)),
                        json={"job_id": job.id, "stars": 1})
        assert r.status_code == 403

    def test_customer_rates_driver_and_average_counts_once(self, client, db_session):
        cust = _user()
        hauler = _contractor()
        j1 = _job(cust, hauler, status="completed")
        j2 = _job(cust, hauler, status="completed")
        r = client.post("/api/ratings", headers=_bearer(cust), json={"job_id": j1.id, "stars": 5})
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["rating"]["to_user_id"] == hauler.user_id
        db.session.refresh(hauler)
        assert hauler.avg_rating == 5.0
        r = client.post("/api/ratings", headers=_bearer(cust), json={"job_id": j2.id, "stars": 3})
        assert r.status_code == 201
        db.session.refresh(hauler)
        assert hauler.avg_rating == 4.0   # (5+3)/2 — the old code produced 3.67

    def test_duplicate_rating_is_409(self, client, db_session):
        cust = _user()
        job = _job(cust, _contractor(), status="completed")
        assert client.post("/api/ratings", headers=_bearer(cust), json={"job_id": job.id, "stars": 4}).status_code == 201
        assert client.post("/api/ratings", headers=_bearer(cust), json={"job_id": job.id, "stars": 1}).status_code == 409
        assert Rating.query.filter_by(job_id=job.id).count() == 1

    def test_assigned_driver_rates_customer(self, client, db_session):
        cust = _user()
        hauler = _contractor()
        job = _job(cust, hauler, status="completed")
        r = client.post("/api/ratings", headers=_bearer(db.session.get(User, hauler.user_id)),
                        json={"job_id": job.id, "stars": 2, "comment": "late"})
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["rating"]["to_user_id"] == cust.id
        db.session.refresh(hauler)
        assert hauler.avg_rating == 0.0   # customer ratings never move the hauler score

    def test_unique_constraint_declared_and_migrated(self):
        from models import Rating
        import migrate
        names = {c.name for c in Rating.__table__.constraints}
        assert "uq_ratings_job_from_user" in names
        assert ("ratings", "uq_ratings_job_from_user", "job_id, from_user_id") in migrate.UNIQUE_INDEXES
