"""Same-day hauler pay: instant payout after the transfer, owed-today ledger,
text-based Stripe onboarding, balance guard, and the copy that promises it."""
import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import db, User, Contractor, Job, Payment, DeskSetting, generate_uuid
import sameday_pay


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code", "STRIPE_SECRET_KEY": "sk_test_x"}):
        yield
    DeskSetting.query.delete()
    for j in Job.query.filter(Job.address.like("e2e-pay%")).all():
        Payment.query.filter_by(job_id=j.id).delete()
        db.session.delete(j)
    for c in Contractor.query.all():
        db.session.delete(c)
    User.query.filter(User.email.like("%@pay.test")).delete(synchronize_session=False)
    db.session.commit()


def _hauler(name, phone, connect=None):
    u = User(email=name.lower().replace(" ", "") + "@pay.test", name=name, phone=phone, role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(user_id=u.id, is_online=True, approval_status="approved", stripe_connect_id=connect)
    db.session.add(c); db.session.commit()
    return c


def _customer():
    u = User.query.filter_by(email="cx@pay.test").first()
    if not u:
        u = User(email="cx@pay.test", name="Pay Cx", phone="+15619990001", role="customer")
        db.session.add(u); db.session.commit()
    return u


def _done_job(contractor, payout=150.0, done=None, payout_status="pending", code=None):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    j = Job(customer_id=_customer().id, driver_id=contractor.id, address="e2e-pay 9 Palm Ave, West Palm Beach FL",
            status="completed", completed_at=done or now, scheduled_at=now - timedelta(hours=2), total_price=200.0)
    if code:
        j.confirmation_code = code
    db.session.add(j); db.session.flush()
    p = Payment(id=generate_uuid(), job_id=j.id, amount=200.0, driver_payout_amount=payout,
                payment_status="succeeded", payout_status=payout_status)
    db.session.add(p); db.session.commit()
    return j, p


def _manager(client):
    from desk_auth import create_desk_user
    if not User.query.filter_by(email="payboss@goumuve.com").first():
        create_desk_user("payboss@goumuve.com", "Boss", "manager", "pw-payboss")
    tok = client.post("/api/desk/login", json={"email": "payboss@goumuve.com", "password": "pw-payboss"}).get_json()["token"]
    return {"Authorization": "Bearer " + tok}


def _fake_stripe(instant_ok=True, available_cents=15000, platform_available_cents=90000):
    s = mock.MagicMock()
    def balance(stripe_account=None, **kw):
        cents = available_cents if stripe_account else platform_available_cents
        return mock.MagicMock(available=[mock.MagicMock(amount=cents, currency="usd")])
    s.Balance.retrieve.side_effect = balance
    if instant_ok:
        s.Payout.create.return_value = mock.MagicMock(id="po_123", arrival_date=int(datetime.now(timezone.utc).timestamp()))
    else:
        s.Payout.create.side_effect = RuntimeError("This account is not eligible for instant payouts: no external debit card")
    s.Transfer.create.return_value = mock.MagicMock(id="tr_1")
    s.Account.create.return_value = mock.MagicMock(id="acct_new1")
    s.AccountLink.create.return_value = mock.MagicMock(url="https://connect.stripe.com/setup/abc")
    return s


# ---------------------------------------------------------------------------
def test_instant_payout_after_transfer_and_fee_cover():
    c = _hauler("Rob Hauls", "+15615550301", connect="acct_real1")
    j, p = _done_job(c)
    s = _fake_stripe()
    with mock.patch("routes.payments._get_stripe", return_value=s), mock.patch("sameday_pay._sms") as sms:
        from routes.payments import attempt_payout
        r = attempt_payout(j.id)
    assert r["ok"] and r["status"] == "paid" and r["instant"]["method"] == "instant"
    db.session.refresh(p)
    assert p.payout_status == "paid" and p.payout_method == "instant" and p.instant_payout_id == "po_123"
    assert p.payout_arrival_at is not None and p.payout_fee_cover == 2.25          # 1.5% of $150
    # completion transfer, then instant payout on the connected account, then the fee-cover transfer
    assert s.Transfer.create.call_count == 2
    po = s.Payout.create.call_args.kwargs
    assert po["method"] == "instant" and po["amount"] == 15000 and po["stripe_account"] == "acct_real1"
    assert po["idempotency_key"] == "instant_" + j.id
    fee = s.Transfer.create.call_args_list[1].kwargs
    assert fee["amount"] == 225 and fee["destination"] == "acct_real1" and fee["idempotency_key"] == "instantfee_" + j.id
    assert "debit card right now" in sms.call_args[0][1]
    # re-running is idempotent: already paid, no second payout
    with mock.patch("routes.payments._get_stripe", return_value=s):
        from routes.payments import attempt_payout
        assert attempt_payout(j.id)["status"] == "already_paid"
    assert s.Payout.create.call_count == 1


def test_no_debit_card_falls_back_to_standard_with_text():
    c = _hauler("Sam Trucks", "+15615550302", connect="acct_real2")
    j, p = _done_job(c, payout=90.0)
    s = _fake_stripe(instant_ok=False)
    with mock.patch("routes.payments._get_stripe", return_value=s), mock.patch("sameday_pay._sms") as sms:
        from routes.payments import attempt_payout
        r = attempt_payout(j.id)
    assert r["status"] == "paid" and r["instant"] == {"method": "standard", "reason": "no debit card set up for instant payouts"}
    db.session.refresh(p)
    assert p.payout_status == "paid" and p.payout_method == "standard" and p.instant_payout_id is None
    assert s.Transfer.create.call_count == 1                                       # no fee cover
    assert "2 business days" in sms.call_args[0][1] and "debit card" in sms.call_args[0][1]


def test_flag_off_or_optout_keeps_standard():
    c = _hauler("Opt Out", "+15615550303", connect="acct_real3")
    j, p = _done_job(c)
    DeskSetting.put("instant_optout:" + c.id, "1")
    s = _fake_stripe()
    with mock.patch("routes.payments._get_stripe", return_value=s):
        from routes.payments import attempt_payout
        assert attempt_payout(j.id)["instant"]["reason"] == "hauler opted out"
    assert s.Payout.create.call_count == 0
    DeskSetting.put("instant_optout:" + c.id, "")
    j2, p2 = _done_job(c, code="FLAGOFF1")
    with mock.patch("routes.payments._get_stripe", return_value=s), mock.patch.dict(os.environ, {"FEATURE_AUTO_INSTANT_PAYOUT": "false"}):
        from routes.payments import attempt_payout
        assert attempt_payout(j2.id)["instant"]["reason"] == "instant payouts off"
    assert s.Payout.create.call_count == 0


def test_dev_account_mocks_instant():
    c = _hauler("Dev Acct", "+15615550304", connect="acct_dev_1")
    j, p = _done_job(c)
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), mock.patch("routes.payments._get_stripe", return_value=_fake_stripe()):
        from routes.payments import attempt_payout
        r = attempt_payout(j.id)
    assert r["instant"]["method"] == "instant" and r["instant"]["payout_id"] == "po_mock"


# ---------------------------------------------------------------------------
def test_owed_ledger_groups_phone_only_haulers_and_marks_paid(client):
    phone_only = _hauler("Zelle Guy", "+15615550305")            # no Stripe → pending_connect
    app_guy = _hauler("App Guy", "+15615550306", connect="acct_real4")
    j1, p1 = _done_job(phone_only, payout=120.0, payout_status="pending_connect", code="OWED0001")
    j2, p2 = _done_job(phone_only, payout=80.0, payout_status="pending_connect",
                       done=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2), code="OWED0002")
    j3, p3 = _done_job(app_guy, payout=100.0, payout_status="failed", code="OWED0003")
    _done_job(app_guy, payout=100.0, payout_status="paid", code="OWED0004")       # settled → not listed
    h = _manager(client)
    assert client.post("/api/va/pay/owed", json={"code": "test-code", "va_name": "Tracy"}).status_code == 403   # VA can't see pay
    rep = client.post("/api/va/pay/owed", json={}, headers=h).get_json()
    assert rep["count"] == 3 and rep["total"] == 300.0 and rep["today_count"] == 2 and rep["today_total"] == 220.0
    zg = next(x for x in rep["haulers"] if x["hauler"] == "Zelle Guy")
    assert zg["total"] == 200.0 and zg["today_total"] == 120.0 and zg["has_stripe"] is False and zg["phone"] == "+15615550305"
    memo = next(r for r in zg["jobs"] if r["job_code"] == "OWED0001")["memo"]
    assert memo == "Umuve OWED0001 · e2e-pay 9 Palm Ave · $120.00"
    ag = next(x for x in rep["haulers"] if x["hauler"] == "App Guy")
    assert ag["has_stripe"] and ag["jobs"][0]["status"] == "failed"
    # mark paid → paid_manual, text goes out, ledger shrinks
    with mock.patch("sameday_pay._sms") as sms:
        r = client.post("/api/va/pay/mark-paid", json={"payment_id": p1.id, "method": "zelle", "ref": "Z-77"}, headers=h).get_json()
    assert r["ok"] and r["amount"] == 120.0 and r["owed"]["count"] == 2
    db.session.refresh(p1)
    assert p1.payout_status == "paid_manual" and p1.payout_method == "manual" and p1.payout_arrival_at is not None
    assert "$120.00" in sms.call_args[0][1] and "zelle" in sms.call_args[0][1] and "Z-77" in sms.call_args[0][1]
    assert client.post("/api/va/pay/mark-paid", json={"payment_id": p1.id}, headers=h).status_code == 409
    assert client.post("/api/va/pay/mark-paid", json={"payment_id": p3.id, "method": "wire"}, headers=h).status_code == 400
    assert client.post("/api/va/pay/mark-paid", json={"payment_id": "nope"}, headers=h).status_code == 404


def test_owed_alert_only_when_something_is_unpaid_today(app):
    with mock.patch("desk_health._send_alert") as alert:
        assert sameday_pay.owed_alert(app)["today_count"] == 0
    assert alert.call_count == 0
    c = _hauler("Late Pay", "+15615550307")
    _done_job(c, payout=65.0, payout_status="pending_connect", code="ALERT001")
    with mock.patch("desk_health._send_alert") as alert:
        summary = sameday_pay.owed_alert(app)
    assert summary["today_count"] == 1 and summary["today_total"] == 65.0
    subject, body = alert.call_args[0]
    assert subject == "Haulers owed today: $65.00" and "Late Pay" in body and "Zelle" in body and "/va/manager" in body
    assert json.loads(DeskSetting.get("owed:last"))["today_total"] == 65.0


# ---------------------------------------------------------------------------
def test_onboarding_text_creates_express_account_and_link(client):
    c = _hauler("New Stripe", "+15615550308")
    h = _manager(client)
    s = _fake_stripe()
    with mock.patch("routes.payments._get_stripe", return_value=s), mock.patch("sameday_pay._sms") as sms:
        r = client.post("/api/va/pay/onboard-link", json={"contractor_id": c.id}, headers=h).get_json()
    assert r["ok"] and r["sent"] and r["url"].startswith("https://connect.stripe.com/")
    db.session.refresh(c)
    assert c.stripe_connect_id == "acct_new1"
    assert s.Account.create.call_args.kwargs["type"] == "express"
    assert s.AccountLink.create.call_args.kwargs["account"] == "acct_new1"
    assert "same-day payouts" in sms.call_args[0][1] and r["url"] in sms.call_args[0][1]
    # existing account → no new Account.create
    with mock.patch("routes.payments._get_stripe", return_value=s), mock.patch("sameday_pay._sms"):
        client.post("/api/va/pay/onboard-link", json={"contractor_id": c.id, "send": False}, headers=h)
    assert s.Account.create.call_count == 1
    assert client.post("/api/va/pay/onboard-link", json={"contractor_id": "nope"}, headers=h).status_code == 404


# ---------------------------------------------------------------------------
def test_balance_guard_states_and_health_check(client):
    c = _hauler("Due Soon", "+15615550309", connect="acct_real5")
    j = Job(customer_id=_customer().id, driver_id=c.id, address="e2e-pay 1 Due St, Lake Worth FL", status="confirmed",
            scheduled_at=(datetime.now(timezone.utc) + timedelta(hours=5)).replace(tzinfo=None), total_price=300.0)
    db.session.add(j); db.session.flush()
    db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=300.0, driver_payout_amount=225.0,
                           payment_status="succeeded", payout_status="pending"))
    db.session.commit()
    assert sameday_pay.expected_payouts() == 225.0
    with mock.patch("routes.payments._get_stripe", return_value=_fake_stripe(platform_available_cents=10000)):
        b = sameday_pay.balance_check()
    assert b["state"] == "fail" and b["available"] == 100.0 and "transfers will fail" in b["reason"]
    with mock.patch("routes.payments._get_stripe", return_value=_fake_stripe(platform_available_cents=30000)):
        assert sameday_pay.balance_check()["state"] == "warn"                    # above due, below $500 floor
    with mock.patch("routes.payments._get_stripe", return_value=_fake_stripe(platform_available_cents=90000)):
        assert sameday_pay.balance_check()["state"] == "ok"
    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}):
        assert sameday_pay.balance_check()["state"] == "warn"
    # surfaces in the desk health report
    with mock.patch("routes.payments._get_stripe", return_value=_fake_stripe(platform_available_cents=10000)):
        from desk_health import check_desk_health
        rep = check_desk_health()
    assert rep["checks"]["stripe_balance"]["state"] == "fail" and "stripe_balance" in rep["fails"]
    # manager status endpoint
    h = _manager(client)
    with mock.patch("routes.payments._get_stripe", return_value=_fake_stripe()):
        st = client.post("/api/va/pay/status", json={}, headers=h).get_json()
    assert st["auto_instant"] is True and st["balance"]["state"] == "ok" and set(st["today"]) == {"instant", "standard", "manual"}


def test_copy_promises_same_day_everywhere(client):
    from call_kit import _SUPPLY_ANSWERS, _SUPPLY_OBJECTIONS
    assert any("same day" in a.lower() for _, a in _SUPPLY_ANSWERS)
    assert any("same day" in a.lower() and "debit card" in a.lower() for _, a in _SUPPLY_OBJECTIONS)
    assert not any("small fee" in a for _, a in _SUPPLY_ANSWERS + _SUPPLY_OBJECTIONS)
    import rate_card, inspect
    assert "same day the job is marked complete" in inspect.getsource(rate_card)
    html = open(os.path.join(os.path.dirname(__file__), "..", "..", "landing-page-premium", "operators.html")).read()
    assert "same day the job is marked complete" in html and "small fee" not in html
    page = client.get("/va/manager").get_data(as_text=True)
    assert "Haulers owed today" in page and "manager-pay.js" in page
