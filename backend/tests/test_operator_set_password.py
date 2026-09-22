"""Approved operators can actually sign in.

September: approval created a user with no password, the email said
"sign in with this email", and there was no reset flow. Three haulers
were locked out. Now the approval email carries a set-password link, a
sweep can send one to anyone still without a password, and the reset
endpoint turns the link into a working login.
"""
import re
from unittest import mock

import pytest

from models import db, User, OperatorApplication, generate_uuid, utcnow


@pytest.fixture()
def admin(client):
    u = User(id=generate_uuid(), email="admin@example.com", name="Admin", role="admin", status="active")
    u.set_password("admin-pass-2026")
    db.session.add(u)
    db.session.commit()
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin-pass-2026"})
    assert r.status_code == 200, r.get_json()
    return {"Authorization": "Bearer " + r.get_json()["token"]}


def _application(email="wright@example.com"):
    a = OperatorApplication(id=generate_uuid(), first_name="Terrington", last_name="Wright",
                            email=email, phone="(786) 227-4711", city="Miami", status="pending",
                            created_at=utcnow())
    db.session.add(a)
    db.session.commit()
    return a


def _link_from(html):
    m = re.search(r'https://app\.goumuve\.com/reset-password\?token=([A-Za-z0-9_\-]+)&to=operator', html)
    assert m, "no set-password link in the email"
    return m.group(0), m.group(1)


def test_approval_sends_a_link_that_becomes_a_working_login(client, admin):
    app_row = _application()
    with mock.patch("routes.operator_applications.send_email") as send:
        r = client.put("/api/admin/operator-applications/%s/review" % app_row.id,
                       json={"action": "approve"}, headers=admin)
    assert r.status_code == 200, r.get_json()
    user = User.query.filter_by(email="wright@example.com").one()
    assert user.role == "operator" and not user.password_hash

    assert send.call_count == 1
    html = send.call_args.kwargs["html_content"]
    assert "Set your password" in html and "app.goumuve.com/operator with this email" not in html
    url, token = _link_from(html)

    # the link sets a password …
    r = client.post("/api/auth/reset-password", json={"token": token, "password": "haul-it-2026"})
    assert r.status_code == 200, r.get_json()
    # … and only once
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "again-2026"}).status_code == 400
    # … and the login works
    r = client.post("/api/auth/login", json={"email": "wright@example.com", "password": "haul-it-2026"})
    assert r.status_code == 200 and r.get_json()["user"]["role"] == "operator"


def test_operators_without_a_password_get_a_link_in_one_sweep(client, admin):
    for email in ("degarmo@example.com", "parker@example.com"):
        db.session.add(User(id=generate_uuid(), email=email, name=email.split("@")[0].title(),
                            role="operator", status="active"))
    db.session.add(User(id=generate_uuid(), email="fine@example.com", name="Fine", role="operator",
                        status="active", password_hash="pbkdf2:sha256:1$x$y"))
    db.session.commit()

    dry = client.post("/api/admin/operators/send-set-password", json={}, headers=admin).get_json()
    assert not dry["apply"] and sorted(o["email"] for o in dry["operators"]) == ["degarmo@example.com", "parker@example.com"]

    with mock.patch("routes.operator_applications.send_email") as send:
        done = client.post("/api/admin/operators/send-set-password",
                           json={"apply": True, "emails": ["parker@example.com"]}, headers=admin).get_json()
    assert done["count"] == 1 and done["operators"][0]["sent"] is True
    assert send.call_count == 1 and send.call_args.kwargs["to_email"] == "parker@example.com"
    url, token = _link_from(send.call_args.kwargs["html_content"])
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "parker-2026"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "parker@example.com", "password": "parker-2026"}).status_code == 200


def test_the_customer_reset_email_points_at_the_app_not_the_marketing_site():
    import notifications
    with mock.patch.dict("os.environ", {"FRONTEND_URL": "https://goumuve.com"}):
        assert notifications.set_password_url("abc", audience="customer") == \
            "https://app.goumuve.com/reset-password?token=abc&to=customer"
