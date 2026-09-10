"""
Audit remediation tests (2026-09-10) — findings F01, F02, F19, F20.

Each finding gets its happy path AND the exact attack scenario from the
audit, which must now fail with a 4xx.

  F01  Apple account takeover      -> /api/auth/apple
  F02  B2B invite / register       -> /portal/v1/orgs/me/members, /orgs/invite/accept, /auth/register
  F19  Phone auth process-local    -> /api/auth/send-code, /verify-code, /forgot-password, /reset-password
  F20  Revocation                  -> require_auth, /refresh, portal_auth, token_version, JWT secret
"""

import datetime as _dt
import hashlib
import uuid

import jwt
import pytest

import auth_routes
from models import db, User, Org, OrgMember, PortalAuditLog
from models_auth import OtpChallenge, PasswordResetToken


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hdr(token):
    return {"Authorization": "Bearer {}".format(token)}


def _mk_user(email=None, password=None, role="customer", **kw):
    u = User(id=uuid.uuid4().hex, email=email, role=role, **kw)
    if password:
        u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u


def _signup(client, email, password="TestPassword123!", name="Someone"):
    resp = client.post("/api/auth/signup", json={"email": email, "password": password, "name": name})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _portal_register(client, business, email, password="Passw0rd!"):
    resp = client.post(
        "/portal/v1/auth/register",
        json={"business_name": business, "email": email, "password": password},
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def _fake_apple(monkeypatch, sub="apple-sub-001", email="claim@example.com", verified=True, nonce_ok=True):
    """Stand in for the JWKS/RS256 verification with a fixed claim set."""
    def _validate(identity_token, nonce=None):
        if identity_token != "good-token" or not nonce_ok:
            return None
        claims = {"sub": sub, "iss": auth_routes.APPLE_ISSUER, "aud": "com.goumuve.app"}
        if email is not None:
            claims["email"] = email
            claims["email_verified"] = "true" if verified else "false"
        return claims
    monkeypatch.setattr(auth_routes, "validate_apple_identity_token", _validate)


# ===========================================================================
# F01 — Apple Sign In
# ===========================================================================
class TestF01Apple:
    def test_legacy_user_identifier_only_is_rejected(self, client, db_session):
        """Audit attack: made-up Apple identifier + admin email + role operator."""
        admin = _mk_user("admin@goumuve.test", "AdminPass123!", role="admin")
        resp = client.post("/api/auth/apple", json={
            "userIdentifier": "attacker-made-up-id",
            "email": admin.email,
            "role": "operator",
        })
        assert resp.status_code == 400
        assert "identity_token" in resp.get_json()["error"]
        assert db.session.get(User, admin.id).apple_id is None

    def test_invalid_token_is_401(self, client, db_session, monkeypatch):
        _fake_apple(monkeypatch)
        resp = client.post("/api/auth/apple", json={"identity_token": "bad-token", "nonce": "n"})
        assert resp.status_code == 401

    def test_body_email_is_ignored_identity_comes_from_claims(self, client, db_session, monkeypatch):
        """Audit attack: valid attacker token + victim email in the body."""
        victim = _mk_user("victim@example.com", "VictimPass123!", role="customer")
        _fake_apple(monkeypatch, sub="attacker-sub", email="attacker@example.com", verified=True)
        resp = client.post("/api/auth/apple", json={
            "identity_token": "good-token", "nonce": "n",
            "email": victim.email, "role": "customer",
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["user"]["id"] != victim.id
        assert body["user"]["email"] == "attacker@example.com"
        assert db.session.get(User, victim.id).apple_id is None

    def test_requested_operator_role_cannot_bypass_mismatch(self, client, db_session, monkeypatch):
        """Audit attack: verified email matches an admin; role=operator used to skip the check."""
        admin = _mk_user("admin2@goumuve.test", "AdminPass123!", role="admin")
        _fake_apple(monkeypatch, sub="sub-x", email=admin.email, verified=True)
        resp = client.post("/api/auth/apple", json={
            "identity_token": "good-token", "nonce": "n", "role": "operator",
        })
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "role_mismatch"
        assert db.session.get(User, admin.id).apple_id is None

    def test_link_by_verified_email_and_audit(self, client, db_session, monkeypatch):
        existing = _mk_user("linkme@example.com", "SomePass123!", role="customer")
        _fake_apple(monkeypatch, sub="sub-link", email="LinkMe@Example.com", verified=True)
        resp = client.post("/api/auth/apple", json={"identity_token": "good-token", "nonce": "n"})
        assert resp.status_code == 200
        assert resp.get_json()["user"]["id"] == existing.id
        assert db.session.get(User, existing.id).apple_id == "sub-link"
        rows = PortalAuditLog.query.filter_by(action="auth.apple_link", user_id=existing.id).all()
        assert len(rows) == 1
        assert rows[0].after["apple_sub_sha256"] == hashlib.sha256(b"sub-link").hexdigest()[:16]

    def test_unverified_email_does_not_link(self, client, db_session, monkeypatch):
        existing = _mk_user("nolink@example.com", "SomePass123!")
        _fake_apple(monkeypatch, sub="sub-unv", email=existing.email, verified=False)
        resp = client.post("/api/auth/apple", json={"identity_token": "good-token", "nonce": "n"})
        assert resp.status_code == 409
        assert db.session.get(User, existing.id).apple_id is None

    def test_email_bound_to_different_apple_id_conflicts(self, client, db_session, monkeypatch):
        existing = _mk_user("taken@example.com", "SomePass123!", apple_id="other-sub")
        _fake_apple(monkeypatch, sub="new-sub", email=existing.email, verified=True)
        resp = client.post("/api/auth/apple", json={"identity_token": "good-token", "nonce": "n"})
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "apple_id_conflict"
        assert db.session.get(User, existing.id).apple_id == "other-sub"

    def test_existing_apple_id_signs_in_and_creates_none(self, client, db_session, monkeypatch):
        existing = _mk_user("apple@example.com", None, apple_id="sub-existing")
        _fake_apple(monkeypatch, sub="sub-existing", email="whatever@example.com", verified=True)
        resp = client.post("/api/auth/apple", json={"identity_token": "good-token", "nonce": "n"})
        assert resp.status_code == 200
        assert resp.get_json()["user"]["id"] == existing.id
        assert User.query.count() == 1
        # the minted token is usable
        me = client.get("/api/auth/me", headers=_hdr(resp.get_json()["token"]))
        assert me.status_code == 200

    def test_deleted_or_suspended_apple_user_cannot_sign_in(self, client, db_session, monkeypatch):
        _mk_user(None, None, apple_id="sub-gone", status="suspended")
        _fake_apple(monkeypatch, sub="sub-gone", email=None)
        resp = client.post("/api/auth/apple", json={"identity_token": "good-token", "nonce": "n"})
        assert resp.status_code == 403


class TestF01AppleTokenVerification:
    """Real RS256 verification against a JWKS we control."""

    @pytest.fixture
    def keys(self, monkeypatch):
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        good = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        rogue = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(good.public_key(), as_dict=True)
        jwk["kid"] = "kid-good"
        monkeypatch.setattr(auth_routes, "get_apple_public_keys", lambda: {"keys": [jwk]})
        pem = lambda k: k.private_bytes(  # noqa: E731
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption())
        return {"good": pem(good), "rogue": pem(rogue)}

    def _token(self, keys, key="good", kid="kid-good", **overrides):
        now = _dt.datetime.utcnow()
        claims = {
            "iss": auth_routes.APPLE_ISSUER, "aud": "com.goumuve.app", "sub": "001.abc",
            "iat": now, "exp": now + _dt.timedelta(minutes=10),
            "email": "u@privaterelay.appleid.com", "email_verified": "true",
            "nonce": hashlib.sha256(b"raw-nonce").hexdigest(),
        }
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, keys[key], algorithm="RS256", headers={"kid": kid})

    def test_valid_token_returns_claims(self, keys):
        claims = auth_routes.validate_apple_identity_token(self._token(keys), "raw-nonce")
        assert claims and claims["sub"] == "001.abc"

    def test_wrong_signature(self, keys):
        assert auth_routes.validate_apple_identity_token(self._token(keys, key="rogue"), "raw-nonce") is None

    def test_wrong_issuer(self, keys):
        assert auth_routes.validate_apple_identity_token(self._token(keys, iss="https://evil.example"), "raw-nonce") is None

    def test_wrong_audience(self, keys):
        assert auth_routes.validate_apple_identity_token(self._token(keys, aud="com.other.app"), "raw-nonce") is None

    def test_expired(self, keys):
        past = _dt.datetime.utcnow() - _dt.timedelta(hours=2)
        assert auth_routes.validate_apple_identity_token(self._token(keys, exp=past), "raw-nonce") is None

    def test_missing_subject(self, keys):
        assert auth_routes.validate_apple_identity_token(self._token(keys, sub=None), "raw-nonce") is None

    def test_nonce_mismatch_and_missing(self, keys):
        assert auth_routes.validate_apple_identity_token(self._token(keys), "other-nonce") is None
        assert auth_routes.validate_apple_identity_token(self._token(keys), None) is None

    def test_token_without_nonce_claim_is_accepted(self, keys):
        claims = auth_routes.validate_apple_identity_token(self._token(keys, nonce=None), None)
        assert claims and claims["sub"] == "001.abc"


# ===========================================================================
# F02 — B2B invitation / registration
# ===========================================================================
class TestF02Invites:
    def _invite(self, client, owner_token, email, role="admin"):
        resp = client.post("/portal/v1/orgs/me/members", json={"email": email, "role": role},
                           headers=_hdr(owner_token))
        assert resp.status_code == 201, resp.get_json()
        return resp.get_json()

    def _db_token(self, org_id, email):
        u = User.query.filter_by(email=email.lower()).first()
        m = OrgMember.query.filter_by(org_id=org_id, user_id=u.id).first()
        return m, m.invite_token

    def test_attacker_org_cannot_claim_existing_admin(self, client, db_session):
        """Audit attack: attacker org invites an existing admin and redeems the
        token with an attacker-chosen password."""
        victim = _mk_user("victim-admin@goumuve.test", "VictimPass123!", role="admin")
        original_hash = victim.password_hash
        attacker = _portal_register(client, "Evil Corp", "attacker@evil.test")

        body = self._invite(client, attacker["token"], victim.email)
        assert "invite_url" not in body and "invite_token" not in body

        member, token = self._db_token(attacker["org_id"], victim.email)
        assert token  # exists in DB, was emailed — not returned

        resp = client.post("/portal/v1/orgs/invite/accept",
                           json={"invite_token": token, "password": "AttackerPass123!"})
        assert resp.status_code == 401
        assert resp.get_json()["code"] == "auth_required"

        db.session.refresh(victim)
        assert victim.password_hash == original_hash
        assert not victim.check_password("AttackerPass123!")
        db.session.refresh(member)
        assert member.joined_at is None

    def test_attacker_bearer_cannot_accept_for_victim(self, client, db_session):
        victim = _mk_user("victim2@goumuve.test", "VictimPass123!")
        attacker = _portal_register(client, "Evil Corp 2", "attacker2@evil.test")
        self._invite(client, attacker["token"], victim.email)
        _, token = self._db_token(attacker["org_id"], victim.email)
        resp = client.post("/portal/v1/orgs/invite/accept", json={"invite_token": token},
                           headers=_hdr(attacker["token"]))
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "wrong_account"

    def test_existing_user_accepts_with_own_bearer(self, client, db_session):
        signup = _signup(client, "member@acme.test")
        owner = _portal_register(client, "Acme", "owner@acme.test")
        self._invite(client, owner["token"], "member@acme.test", role="viewer")
        member, token = self._db_token(owner["org_id"], "member@acme.test")
        resp = client.post("/portal/v1/orgs/invite/accept", json={"invite_token": token},
                           headers=_hdr(signup["token"]))
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["role"] == "viewer"
        db.session.refresh(member)
        assert member.joined_at is not None and member.invite_token is None
        me = client.get("/portal/v1/orgs/me", headers=_hdr(resp.get_json()["token"]))
        assert me.status_code == 200
        # password untouched
        assert User.query.filter_by(email="member@acme.test").first().check_password("TestPassword123!")

    def test_existing_user_accepts_with_own_password(self, client, db_session):
        _signup(client, "pw-member@acme.test", password="MemberPass123!")
        owner = _portal_register(client, "Acme PW", "owner-pw@acme.test")
        self._invite(client, owner["token"], "pw-member@acme.test")
        _, token = self._db_token(owner["org_id"], "pw-member@acme.test")
        bad = client.post("/portal/v1/orgs/invite/accept",
                          json={"invite_token": token, "password": "WrongPass123!"})
        assert bad.status_code == 401
        good = client.post("/portal/v1/orgs/invite/accept",
                           json={"invite_token": token, "password": "MemberPass123!"})
        assert good.status_code == 200
        assert User.query.filter_by(email="pw-member@acme.test").first().check_password("MemberPass123!")

    def test_guest_with_phone_counts_as_existing(self, client, db_session):
        _mk_user("guest@acme.test", None, phone="+15615550123")
        owner = _portal_register(client, "Acme G", "owner-g@acme.test")
        self._invite(client, owner["token"], "guest@acme.test")
        _, token = self._db_token(owner["org_id"], "guest@acme.test")
        resp = client.post("/portal/v1/orgs/invite/accept",
                           json={"invite_token": token, "password": "NewPass123!"})
        assert resp.status_code == 401
        assert User.query.filter_by(email="guest@acme.test").first().password_hash is None

    def test_new_invitee_sets_first_password(self, client, db_session):
        owner = _portal_register(client, "Acme New", "owner-n@acme.test")
        self._invite(client, owner["token"], "Fresh@Acme.test")
        _, token = self._db_token(owner["org_id"], "fresh@acme.test")

        no_pw = client.post("/portal/v1/orgs/invite/accept", json={"invite_token": token})
        assert no_pw.status_code == 400 and no_pw.get_json()["code"] == "password_required"
        weak = client.post("/portal/v1/orgs/invite/accept", json={"invite_token": token, "password": "short"})
        assert weak.status_code == 400 and weak.get_json()["code"] == "weak_password"
        wrong_email = client.post("/portal/v1/orgs/invite/accept",
                                  json={"invite_token": token, "password": "GoodPass123!", "email": "other@x.test"})
        assert wrong_email.status_code == 403

        ok = client.post("/portal/v1/orgs/invite/accept",
                         json={"invite_token": token, "password": "GoodPass123!", "email": " Fresh@Acme.test "})
        assert ok.status_code == 200, ok.get_json()
        # single use
        again = client.post("/portal/v1/orgs/invite/accept", json={"invite_token": token, "password": "GoodPass123!"})
        assert again.status_code == 404
        # portal login now works for the new member
        login = client.post("/portal/v1/auth/login", json={"email": "fresh@acme.test", "password": "GoodPass123!"})
        assert login.status_code == 200

    def test_invite_expires(self, client, db_session):
        owner = _portal_register(client, "Acme Old", "owner-o@acme.test")
        self._invite(client, owner["token"], "late@acme.test")
        member, token = self._db_token(owner["org_id"], "late@acme.test")
        member.invited_at = _dt.datetime.utcnow() - _dt.timedelta(days=15)
        db.session.commit()
        resp = client.post("/portal/v1/orgs/invite/accept", json={"invite_token": token, "password": "GoodPass123!"})
        assert resp.status_code == 410

    def test_register_refuses_to_claim_existing_no_password_user(self, client, db_session):
        """Audit: auth_register set a password on existing guest/Apple rows."""
        guest = _mk_user("guest-reg@example.com", None, apple_id="sub-guest")
        resp = client.post("/portal/v1/auth/register", json={
            "business_name": "Claim Co", "email": guest.email, "password": "Claimed123!",
        })
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "email_exists"
        assert db.session.get(User, guest.id).password_hash is None
        assert Org.query.filter_by(name="Claim Co").count() == 0


# ===========================================================================
# F19 — Phone auth persistence, OTP hygiene, password reset
# ===========================================================================
@pytest.fixture
def sms(monkeypatch):
    """Capture SMS sends; make sure the dev OTP echo is on."""
    import notifications
    sent = []
    monkeypatch.setattr(notifications, "send_verification_sms", lambda phone, code: sent.append((phone, code)))
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")
    return sent


class TestF19Phone:
    def test_phone_identity_persists_across_formats(self, client, db_session, sms):
        r1 = client.post("/api/auth/send-code", json={"phoneNumber": "(561) 555-0100"})
        assert r1.status_code == 200
        code = r1.get_json()["code"]
        assert sms[-1] == ("+15615550100", code)

        ch = OtpChallenge.query.filter_by(identity="+15615550100").first()
        assert ch is not None and ch.code_hash != code and code not in ch.code_hash

        v1 = client.post("/api/auth/verify-code", json={"phoneNumber": "561-555-0100", "code": code})
        assert v1.status_code == 200, v1.get_json()
        uid = v1.get_json()["user"]["id"]
        user = db.session.get(User, uid)
        assert user.phone == "+15615550100" and user.phone_verified_at is not None
        assert client.get("/api/auth/me", headers=_hdr(v1.get_json()["token"])).status_code == 200

        # A second login from another spelling resolves to the SAME persisted user.
        r2 = client.post("/api/auth/send-code", json={"phone": "5615550100"})
        v2 = client.post("/api/auth/verify-code", json={"phone": "+1 561 555 0100", "code": r2.get_json()["code"]})
        assert v2.status_code == 200 and v2.get_json()["user"]["id"] == uid
        assert User.query.filter(User.phone.like("%5615550100%")).count() == 1

    def test_code_is_single_use_and_wrong_code_locks(self, client, db_session, sms):
        code = client.post("/api/auth/send-code", json={"phone": "5615550101"}).get_json()["code"]
        for _ in range(auth_routes.OTP_MAX_ATTEMPTS):
            assert client.post("/api/auth/verify-code", json={"phone": "5615550101", "code": "000000"}).status_code == 401
        locked = client.post("/api/auth/verify-code", json={"phone": "5615550101", "code": code})
        assert locked.status_code in (400, 429)
        # fresh code works, then cannot be replayed
        code = client.post("/api/auth/send-code", json={"phone": "5615550101"}).get_json()["code"]
        assert client.post("/api/auth/verify-code", json={"phone": "5615550101", "code": code}).status_code == 200
        assert client.post("/api/auth/verify-code", json={"phone": "5615550101", "code": code}).status_code == 400

    def test_expired_code_rejected(self, client, db_session, sms):
        code = client.post("/api/auth/send-code", json={"phone": "5615550102"}).get_json()["code"]
        ch = OtpChallenge.query.filter_by(identity="+15615550102", consumed_at=None).first()
        ch.expires_at = _dt.datetime.utcnow() - _dt.timedelta(minutes=1)
        db.session.commit()
        assert client.post("/api/auth/verify-code", json={"phone": "5615550102", "code": code}).status_code == 401

    def test_per_identity_send_throttle(self, client, db_session, sms):
        for _ in range(auth_routes.OTP_SENDS_PER_HOUR):
            assert client.post("/api/auth/send-code", json={"phone": "5615550103"}).status_code == 200
        assert client.post("/api/auth/send-code", json={"phone": "5615550103"}).status_code == 429
        assert len(sms) == auth_routes.OTP_SENDS_PER_HOUR

    def test_invalid_phone_rejected(self, client, db_session, sms):
        assert client.post("/api/auth/send-code", json={"phone": "12345"}).status_code == 400

    def test_legacy_stored_phone_resolves_and_upgrades(self, client, db_session, sms):
        legacy = _mk_user("legacy@example.com", "LegacyPass123!", phone="5615550104")
        code = client.post("/api/auth/send-code", json={"phone": "(561) 555-0104"}).get_json()["code"]
        v = client.post("/api/auth/verify-code", json={"phone": "(561) 555-0104", "code": code})
        assert v.status_code == 200 and v.get_json()["user"]["id"] == legacy.id
        assert db.session.get(User, legacy.id).phone == "+15615550104"


class TestF19PasswordReset:
    @pytest.fixture
    def reset_mail(self, monkeypatch):
        import notifications
        sent = []
        monkeypatch.setattr(notifications, "send_password_reset_email",
                            lambda email, token, name=None: sent.append((email, token)))
        return sent

    def test_generic_response_no_enumeration(self, client, db_session, reset_mail):
        _signup(client, "known@example.com")
        known = client.post("/api/auth/forgot-password", json={"email": "known@example.com"})
        unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
        assert known.status_code == unknown.status_code == 200
        assert known.get_json() == unknown.get_json()
        assert len(reset_mail) == 1 and reset_mail[0][0] == "known@example.com"

    def test_reset_is_hashed_single_use_expiring_and_revokes_sessions(self, client, db_session, reset_mail):
        signup = _signup(client, "resetme@example.com", password="OldPass123!")
        old_token = signup["token"]
        client.post("/api/auth/forgot-password", json={"email": "ResetMe@example.com"})
        raw = reset_mail[-1][1]
        row = PasswordResetToken.query.first()
        assert row.token_hash != raw and raw not in row.token_hash
        assert row.used_at is None and row.expires_at > _dt.datetime.utcnow()

        weak = client.post("/api/auth/reset-password", json={"token": raw, "password": "short"})
        assert weak.status_code == 400
        bogus = client.post("/api/auth/reset-password", json={"token": "not-a-token", "password": "NewPass123!"})
        assert bogus.status_code == 400

        ok = client.post("/api/auth/reset-password", json={"token": raw, "password": "NewPass123!"})
        assert ok.status_code == 200, ok.get_json()
        # single use
        assert client.post("/api/auth/reset-password", json={"token": raw, "password": "NewPass456!"}).status_code == 400
        # old session revoked, new password works
        assert client.get("/api/auth/me", headers=_hdr(old_token)).status_code == 401
        login = client.post("/api/auth/login", json={"email": "resetme@example.com", "password": "NewPass123!"})
        assert login.status_code == 200
        assert client.post("/api/auth/login", json={"email": "resetme@example.com", "password": "OldPass123!"}).status_code == 401

    def test_expired_reset_token(self, client, db_session, reset_mail):
        _signup(client, "late@example.com")
        client.post("/api/auth/forgot-password", json={"email": "late@example.com"})
        row = PasswordResetToken.query.first()
        row.expires_at = _dt.datetime.utcnow() - _dt.timedelta(minutes=1)
        db.session.commit()
        resp = client.post("/api/auth/reset-password", json={"token": reset_mail[-1][1], "password": "NewPass123!"})
        assert resp.status_code == 400

    def test_driver_signup_password_policy(self, client, db_session):
        weak = client.post("/api/auth/driver-signup", json={"email": "d@example.com", "password": "short"})
        assert weak.status_code == 400
        ok = client.post("/api/auth/driver-signup", json={"email": "d@example.com", "password": "LongEnough1"})
        assert ok.status_code == 200, ok.get_json()


# ===========================================================================
# F20 — Revocation: status, token_version, membership re-check, secret
# ===========================================================================
class TestF20Revocation:
    def test_suspended_user_is_rejected_everywhere(self, client, db_session):
        signup = _signup(client, "susp@example.com")
        token = signup["token"]
        assert client.get("/api/auth/me", headers=_hdr(token)).status_code == 200
        user = db.session.get(User, signup["user"]["id"])
        user.status = "suspended"
        db.session.commit()
        assert client.get("/api/auth/me", headers=_hdr(token)).status_code == 401
        assert client.post("/api/auth/refresh", headers=_hdr(token)).status_code == 401
        assert client.post("/api/auth/validate", headers=_hdr(token)).status_code == 401
        login = client.post("/api/auth/login", json={"email": "susp@example.com", "password": "TestPassword123!"})
        assert login.status_code == 403

    def test_deleted_user_still_rejected(self, client, db_session):
        signup = _signup(client, "del@example.com")
        token = signup["token"]
        assert client.delete("/api/auth/me", headers=_hdr(token)).status_code == 200
        resp = client.get("/api/auth/me", headers=_hdr(token))
        assert resp.status_code == 401 and resp.get_json()["error"] == "Account deleted"

    def test_stale_token_version_rejected_and_legacy_claim_semantics(self, client, db_session):
        user = _mk_user("legacy-tok@example.com", "LegacyPass123!")
        assert user.token_version == 0
        # Pre-rollout token: no `tv` claim -> treated as version 0 -> accepted.
        legacy = jwt.encode(
            {"user_id": user.id, "exp": _dt.datetime.utcnow() + _dt.timedelta(days=1)},
            auth_routes.JWT_SECRET, algorithm="HS256")
        assert client.get("/api/auth/me", headers=_hdr(legacy)).status_code == 200
        # The next login sunsets it (0 -> 1) and mints a versioned token.
        login = client.post("/api/auth/login", json={"email": "legacy-tok@example.com", "password": "LegacyPass123!"})
        assert login.status_code == 200
        assert jwt.decode(login.get_json()["token"], auth_routes.JWT_SECRET, algorithms=["HS256"])["tv"] == 1
        assert client.get("/api/auth/me", headers=_hdr(legacy)).status_code == 401
        assert client.get("/api/auth/me", headers=_hdr(login.get_json()["token"])).status_code == 200
        # Explicit revocation bumps again and kills the new token too.
        db.session.get(User, user.id).revoke_sessions()
        db.session.commit()
        assert client.get("/api/auth/me", headers=_hdr(login.get_json()["token"])).status_code == 401
        assert client.post("/api/auth/refresh", headers=_hdr(login.get_json()["token"])).status_code == 401

    def test_password_change_revokes_other_sessions(self, client, db_session):
        signup = _signup(client, "chg@example.com")
        old = signup["token"]
        resp = client.put("/api/auth/change-password", headers=_hdr(old),
                          json={"current_password": "TestPassword123!", "new_password": "BrandNew123!"})
        assert resp.status_code == 200, resp.get_json()
        assert client.get("/api/auth/me", headers=_hdr(old)).status_code == 401
        assert client.get("/api/auth/me", headers=_hdr(resp.get_json()["token"])).status_code == 200

    def test_role_change_revokes_sessions(self, client, db_session):
        signup = _signup(client, "rolechg@example.com")
        user = db.session.get(User, signup["user"]["id"])
        user.role = "admin"
        db.session.commit()
        assert client.get("/api/auth/me", headers=_hdr(signup["token"])).status_code == 401

    def test_portal_token_is_not_a_base_token(self, client, db_session):
        owner = _portal_register(client, "Sep Co", "sep@example.com")
        assert client.get("/api/auth/me", headers=_hdr(owner["token"])).status_code == 401

    def test_membership_removal_revokes_access(self, client, db_session):
        owner = _portal_register(client, "Rm Co", "rm-owner@example.com")
        # bring in a member through the invite flow
        client.post("/portal/v1/orgs/me/members", json={"email": "rm-member@example.com", "role": "admin"},
                    headers=_hdr(owner["token"]))
        m_user = User.query.filter_by(email="rm-member@example.com").first()
        member = OrgMember.query.filter_by(user_id=m_user.id).first()
        acc = client.post("/portal/v1/orgs/invite/accept",
                          json={"invite_token": member.invite_token, "password": "MemberPass123!"})
        assert acc.status_code == 200
        m_tok = acc.get_json()["token"]
        base_tok = auth_routes.generate_token(m_user.id)
        assert client.get("/portal/v1/orgs/me", headers=_hdr(m_tok)).status_code == 200
        assert client.get("/api/auth/me", headers=_hdr(base_tok)).status_code == 200

        rm = client.delete("/portal/v1/orgs/me/members/{}".format(member.id), headers=_hdr(owner["token"]))
        assert rm.status_code == 200
        assert client.get("/portal/v1/orgs/me", headers=_hdr(m_tok)).status_code == 401
        assert client.get("/api/auth/me", headers=_hdr(base_tok)).status_code == 401

    def test_portal_role_comes_from_db_not_token(self, client, db_session):
        owner = _portal_register(client, "Role Co", "role-owner@example.com")
        member = OrgMember.query.filter_by(org_id=owner["org_id"]).first()
        member.role = "viewer"
        db.session.commit()
        resp = client.patch("/portal/v1/orgs/me", json={"name": "Renamed"}, headers=_hdr(owner["token"]))
        assert resp.status_code == 403

    def test_portal_suspended_user_rejected(self, client, db_session):
        owner = _portal_register(client, "Susp Co", "susp-owner@example.com")
        user = User.query.filter_by(email="susp-owner@example.com").first()
        user.status = "suspended"
        db.session.commit()
        assert client.get("/portal/v1/orgs/me", headers=_hdr(owner["token"])).status_code == 401

    def test_token_exchange_requires_usable_base_token(self, client, db_session):
        owner = _portal_register(client, "Xchg Co", "xchg@example.com")
        user = User.query.filter_by(email="xchg@example.com").first()
        base = auth_routes.generate_token(user.id)
        ok = client.post("/portal/v1/auth/token", json={"user_token": base, "org_id": owner["org_id"]})
        assert ok.status_code == 200
        user.revoke_sessions()
        db.session.commit()
        stale = client.post("/portal/v1/auth/token", json={"user_token": base, "org_id": owner["org_id"]})
        assert stale.status_code == 401

    def test_missing_jwt_secret_fails_closed_in_production(self, monkeypatch):
        from routes import portal as portal_mod
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.delenv("JWT_SECRET", raising=False)
        with pytest.raises(RuntimeError):
            auth_routes._load_jwt_secret()
        with pytest.raises(RuntimeError):
            portal_mod._load_portal_jwt_secret({})
        monkeypatch.setenv("FLASK_ENV", "development")
        assert portal_mod._load_portal_jwt_secret({}) == auth_routes.JWT_SECRET
        assert auth_routes._load_jwt_secret().startswith("dev-only-")
