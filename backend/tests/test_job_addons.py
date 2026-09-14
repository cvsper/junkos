"""Extra items found on site: priced by the engine, approved by the customer,
charged to the card they already used.

sevs, 14 Sep: "now do the on site addon billing". The rule underneath it is the
promise the customer was given — anything not in the original job is priced
before it goes on the truck, and only with their say-so.
"""
import os
from unittest import mock

import pytest

from models import db, Job, Payment, User, Contractor, generate_uuid
from models_addon import JobAddon
import job_addons


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code",
                                      "ADDON_MAX_OFF_SESSION": "250"}):
        yield
    JobAddon.query.delete(); Payment.query.delete(); Job.query.delete()
    Contractor.query.delete(); User.query.delete()
    db.session.commit()


def _job(total=265.44, items=None, status="started", with_card=True, phone="+15615550142"):
    cust = User(id=generate_uuid(), name="Dana Reyes", phone=phone,
                email="{}@t.local".format(generate_uuid()[:8]), role="customer",
                stripe_customer_id="cus_1" if with_card else None)
    db.session.add(cust); db.session.flush()
    j = Job(id=generate_uuid(), customer_id=cust.id, status=status, address="12 Palm Way",
            items=items if items is not None else [{"category": "sofa", "quantity": 1},
                                                    {"category": "mattress", "quantity": 1}],
            total_price=total, confirmation_code="AD1")
    db.session.add(j); db.session.flush()
    db.session.add(Payment(id=generate_uuid(), job_id=j.id, amount=total,
                           payment_status="succeeded",
                           stripe_payment_method_id="pm_1" if with_card else None,
                           stripe_customer_id="cus_1" if with_card else None))
    db.session.commit()
    return j


# --- pricing ---------------------------------------------------------------

def test_the_hauler_never_types_a_price_the_engine_does():
    job = _job()                                   # sofa + 1 mattress
    q = job_addons.quote(job, [{"category": "mattress", "quantity": 1}])
    assert q["amount"] > 0 and q["new_total"] > q["old_total"]
    assert q["items"][0]["category"] == "mattress" and q["items"][0]["quantity"] == 1
    # the WHOLE job is re-priced, so discounts and fees stay right — the add-on
    # is the difference, not a second little invoice
    from routes.booking import calculate_estimate
    whole = calculate_estimate([{"category": "sofa", "quantity": 1},
                                {"category": "mattress", "quantity": 2}])
    assert q["new_total"] == round(whole["total"], 2)


def test_items_that_dont_change_the_price_are_not_billed():
    job = _job(total=900.0)                      # already above what the items price to
    q = job_addons.quote(job, [{"category": "mattress", "quantity": 1}])
    assert q["amount"] == 0.0
    addon, err = job_addons.request(job, [{"category": "mattress", "quantity": 1}], "Hank")
    assert addon is None and "don't change the price" in err


def test_nothing_can_be_added_to_a_finished_job():
    job = _job(status="completed")
    addon, err = job_addons.request(job, [{"category": "mattress", "quantity": 1}], "Hank")
    assert addon is None and "already finished" in err


# --- asking ----------------------------------------------------------------

def test_the_customer_is_asked_once_and_told_nothing_moves_until_they_answer():
    job = _job()
    with mock.patch.object(job_addons, "_send", return_value=True) as send, \
         mock.patch.object(job_addons, "_alert"):
        addon, err = job_addons.request(job, [{"category": "mattress", "quantity": 1}], "Hank Hauler")
    assert err is None and addon.status == "pending" and addon.asked_at
    to, body = send.call_args[0]
    assert to == "5615550142"
    assert "Hank" in body and "mattress" in body.lower()
    assert "adds ${:.0f}".format(addon.amount) in body
    assert "new total ${:.0f}".format(addon.new_total) in body
    assert "Reply YES" in body and "Nothing goes on the truck until you answer" in body
    # and only one question at a time
    with mock.patch.object(job_addons, "_send"), mock.patch.object(job_addons, "_alert"):
        second, err2 = job_addons.request(job, [{"category": "tv_flatscreen", "quantity": 1}], "Hank")
    assert second is None and "already an add-on waiting" in err2


def test_reading_yes_and_no():
    for yes in ("YES", "yes", "Yes please", "yeah", "ok", "sure", "go ahead", "y"):
        assert job_addons.read_reply(yes) is True, yes
    for no in ("no", "NO", "nope", "Nah", "decline", "leave it", "no thanks"):
        assert job_addons.read_reply(no) is False, no
    for neither in ("what is it", "how much again?", "", "call me"):
        assert job_addons.read_reply(neither) is None, neither


def _pending(job):
    with mock.patch.object(job_addons, "_send"), mock.patch.object(job_addons, "_alert"):
        addon, err = job_addons.request(job, [{"category": "mattress", "quantity": 1}], "Hank")
    assert addon is not None, err
    return addon


# --- yes ------------------------------------------------------------------

def test_yes_charges_the_card_they_already_used_and_moves_the_job():
    job = _job()
    addon = _pending(job)
    before = job.total_price
    intent = mock.Mock(id="pi_addon_1", status="succeeded")
    stripe = mock.Mock(); stripe.PaymentIntent.create.return_value = intent
    with mock.patch("routes.payments._stripe_key", return_value="sk_test"), \
         mock.patch("routes.payments._get_stripe", return_value=stripe), \
         mock.patch.object(job_addons, "_send") as send, \
         mock.patch.object(job_addons, "_tell_hauler") as tell, \
         mock.patch.object(job_addons, "_alert"):
        out = job_addons.handle_reply("+15615550142", "YES")
    assert out.status == "charged" and out.intent_id == "pi_addon_1" and out.charged_at
    kw = stripe.PaymentIntent.create.call_args.kwargs
    assert kw["customer"] == "cus_1" and kw["payment_method"] == "pm_1"
    assert kw["off_session"] is True and kw["confirm"] is True
    assert kw["amount"] == int(round(addon.amount * 100))
    assert kw["metadata"]["addon_id"] == addon.id and kw["idempotency_key"] == "addon_" + addon.id
    db.session.refresh(job)
    assert job.total_price == round(before + addon.amount, 2)       # payout follows the real job
    assert any(i.get("added_on_site") for i in job.items)
    assert "charged to the card on file" in send.call_args[0][1]
    assert tell.called


def test_no_charges_nothing_and_tells_the_hauler():
    job = _job()
    addon = _pending(job)
    before = job.total_price
    with mock.patch.object(job_addons, "_send") as send, \
         mock.patch.object(job_addons, "_tell_hauler") as tell, \
         mock.patch.object(job_addons, "_alert"):
        out = job_addons.handle_reply("+15615550142", "no thanks")
    assert out.status == "declined" and out.intent_id is None
    db.session.refresh(job); assert job.total_price == before
    assert "take only what was quoted" in tell.call_args[0][2]


def test_a_question_is_not_an_answer():
    job = _job()
    _pending(job)
    assert job_addons.handle_reply("+15615550142", "wait how much is that?") is None
    assert JobAddon.query.one().status == "pending"


def test_silence_is_not_a_yes():
    job = _job()
    addon = _pending(job)
    addon.asked_at = job_addons._now() - job_addons.timedelta(hours=20)
    db.session.commit()
    assert job_addons.expire_stale() == 1
    db.session.refresh(addon)
    assert addon.status == "expired" and addon.charged_at is None


# --- the guardrails -------------------------------------------------------

def test_a_big_addon_gets_a_link_not_a_quiet_charge():
    job = _job(total=120.0)                       # cap = half of 120 = $60
    with mock.patch.object(job_addons, "_send"), mock.patch.object(job_addons, "_alert"):
        addon, _ = job_addons.request(job, [{"category": "hot_tub", "quantity": 1}], "Hank")
    assert addon.amount > job_addons._off_session_cap(job)
    stripe = mock.Mock()
    with mock.patch("routes.payments._stripe_key", return_value="sk_test"), \
         mock.patch("routes.payments._get_stripe", return_value=stripe), \
         mock.patch.object(job_addons, "_pay_link", return_value="https://pay/x"), \
         mock.patch.object(job_addons, "_send") as send, \
         mock.patch.object(job_addons, "_tell_hauler"), mock.patch.object(job_addons, "_alert"):
        out = job_addons.handle_reply("+15615550142", "yes")
    assert stripe.PaymentIntent.create.call_count == 0        # never charged quietly
    assert out.status == "approved" and out.pay_url == "https://pay/x"
    assert "one tap to add it" in send.call_args[0][1]


def test_no_saved_card_means_a_link():
    job = _job(with_card=False)
    _pending(job)
    with mock.patch("routes.payments._stripe_key", return_value="sk_test"), \
         mock.patch.object(job_addons, "_pay_link", return_value="https://pay/y"), \
         mock.patch.object(job_addons, "_send"), mock.patch.object(job_addons, "_tell_hauler"), \
         mock.patch.object(job_addons, "_alert"):
        out = job_addons.handle_reply("+15615550142", "yes")
    assert out.status == "approved" and out.pay_url == "https://pay/y" and "no saved card" in out.last_error


def test_a_bank_that_wants_the_customer_gets_a_link_never_a_failure_in_silence():
    job = _job()
    _pending(job)
    stripe = mock.Mock()
    stripe.PaymentIntent.create.side_effect = Exception("authentication_required")
    with mock.patch("routes.payments._stripe_key", return_value="sk_test"), \
         mock.patch("routes.payments._get_stripe", return_value=stripe), \
         mock.patch.object(job_addons, "_pay_link", return_value="https://pay/z"), \
         mock.patch.object(job_addons, "_send") as send, \
         mock.patch.object(job_addons, "_tell_hauler") as tell, \
         mock.patch.object(job_addons, "_alert"):
        out = job_addons.handle_reply("+15615550142", "yes")
    assert out.status == "failed" and out.pay_url == "https://pay/z"
    assert "bank wants you to confirm" in send.call_args[0][1]
    assert "link sent, load it" in tell.call_args[0][2]
    # and paying the link settles it
    with mock.patch.object(job_addons, "_tell_hauler"):
        done = job_addons.mark_paid_by_link(job.id, "pi_link_1")
    assert done.status == "charged" and done.charged_at


# --- the ways in ----------------------------------------------------------

def test_a_hauler_can_only_add_to_their_own_job(client):
    job = _job()
    assert client.post("/api/drivers/jobs/{}/addons".format(job.id), json={}).status_code == 401


def test_the_desk_route_needs_the_desk(client):
    job = _job()
    assert client.post("/api/va/dispatch/job/addon", json={"job_id": job.id}).status_code == 401


def test_the_desk_can_preview_before_asking(client):
    job = _job()
    r = client.post("/api/va/dispatch/job/addon",
                    json={"code": "test-code", "va_name": "Tracy", "job_id": job.id,
                          "preview": True, "items": [{"category": "mattress", "quantity": 1}]})
    assert r.status_code == 200
    body = r.get_json()
    assert body["amount"] > 0 and body["new_total"] > body["old_total"]
    assert JobAddon.query.count() == 0            # a preview asks nobody anything
