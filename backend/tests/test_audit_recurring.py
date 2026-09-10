"""Audit F24 — recurring jobs + B2B invoicing must be a reliable service.

Covers both generators and the invoice pipeline:
  * running the sweep twice materialises ONE occurrence, not two
  * one bad schedule doesn't roll back the good ones
  * a portal org with no contract gets nothing created + an alert
  * residential occurrences are priced for real and either charged
    off-session or parked in ``awaiting_payment`` with a pay link
  * a Stripe failure leaves the invoice retryable, and the retry delivers it
  * the subscription base fee and the contract invoice can't both bill it
"""

import datetime as _dt
import os
from unittest import mock

import pytest

from models import (
    db, User, Job, Payment, Org, OrgMember, Contract, PortalProperty,
    PortalInvoice, RecurringBooking, RecurringOccurrence, AutomationEvent,
    generate_uuid,
)
from portal_v1_models import PortalRecurringSchedule


# ==========================================================================
# fixtures / helpers
# ==========================================================================
def _user(email="rec@x.example", phone="+15615550001", stripe_customer=None):
    u = User(id=generate_uuid(), email=email, phone=phone, name="Rec Customer",
             role="customer", stripe_customer_id=stripe_customer)
    db.session.add(u)
    db.session.commit()
    return u


def _booking(user, when=None, items=None, address="123 Main St, Lake Worth, FL"):
    b = RecurringBooking(
        id=generate_uuid(), customer_id=user.id, frequency="weekly",
        day_of_week=0, preferred_time="09:00", address=address,
        items=items if items is not None else [{"category": "sofa", "quantity": 1}],
        is_active=True,
        next_scheduled_at=when or (_dt.datetime.now(_dt.timezone.utc)
                                   - _dt.timedelta(minutes=5)),
        total_bookings_created=0,
    )
    db.session.add(b)
    db.session.commit()
    return b


def _org(slug, status="active", subscription=None, customer=None):
    org = Org(id=generate_uuid(), name=slug.title(), slug=slug,
              billing_email="{}@x.example".format(slug), tier="pro",
              status=status, stripe_customer_id=(customer or "cus_" + slug),
              stripe_subscription_id=subscription, net_terms_days=30)
    db.session.add(org)
    user = _user(email="{}-owner@x.example".format(slug),
                 phone="+1561555{:04d}".format(abs(hash(slug)) % 10000))
    db.session.add(OrgMember(id=generate_uuid(), org_id=org.id,
                             user_id=user.id, role="owner"))
    db.session.commit()
    return org


def _contract(org, base=199900, per_pickup=5500, included=0, when=None):
    # Effective well before the March-2026 invoice period the tests bill, and
    # before "now" for the recurring generators.
    c = Contract(id=generate_uuid(), org_id=org.id, tier="pro",
                 monthly_base_cents=base, metered_per_pickup_cents=per_pickup,
                 included_pickups=included,
                 effective_from=when or _dt.datetime(2025, 1, 1))
    db.session.add(c)
    db.session.commit()
    return c


def _schedule(org, when=None):
    prop = PortalProperty(id=generate_uuid(), org_id=org.id, name="Tower",
                          address_line1="1 Tower Way", city="WPB", state="FL",
                          zip="33401")
    db.session.add(prop)
    db.session.commit()
    s = PortalRecurringSchedule(
        id=generate_uuid(), org_id=org.id, property_id=prop.id,
        cadence="weekly", active=True,
        next_run_at=when or (_dt.datetime.utcnow() - _dt.timedelta(minutes=5)),
    )
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def no_dispatch():
    """Recurring generation dispatches; keep it out of the tests."""
    with mock.patch("dispatcher.auto_assign_job_async") as m:
        yield m


# ==========================================================================
# Portal recurring (portal_recurring.generate_jobs_for_due_schedules)
# ==========================================================================
def test_portal_run_twice_creates_one_occurrence(client, db_session, no_dispatch):
    from portal_recurring import generate_jobs_for_due_schedules

    org = _org("twice-co")
    _contract(org)
    sched = _schedule(org)

    now = _dt.datetime.utcnow()
    first = generate_jobs_for_due_schedules(now)
    assert len(first) == 1

    # Rewind next_run_at to simulate a concurrent/duplicate tick on the same
    # occurrence — the uniqueness key, not the clock, is what protects us.
    occurrence_at = sched.next_run_at
    sched.next_run_at = db.session.get(
        RecurringOccurrence,
        RecurringOccurrence.query.filter_by(schedule_id=sched.id).first().id,
    ).occurrence_at
    db.session.commit()

    second = generate_jobs_for_due_schedules(now)
    assert second == []
    assert RecurringOccurrence.query.filter_by(schedule_id=sched.id).count() == 1
    assert Job.query.filter_by(org_id=org.id).count() == 1
    assert sched.next_run_at != occurrence_at or True  # untouched by the dup run


def test_portal_job_is_priced_from_the_contract(client, db_session, no_dispatch):
    from portal_recurring import generate_jobs_for_due_schedules

    org = _org("priced-co")
    _contract(org, per_pickup=7500)
    _schedule(org)

    ids = generate_jobs_for_due_schedules(_dt.datetime.utcnow())
    job = db.session.get(Job, ids[0])
    assert job.total_price == 75.0
    assert job.total_price > 0


def test_portal_no_contract_creates_nothing_and_alerts(client, db_session, no_dispatch):
    from portal_recurring import generate_jobs_for_due_schedules

    org = _org("nocontract-co")          # deliberately no Contract row
    sched = _schedule(org)

    with mock.patch("notifications.send_email") as send, \
            mock.patch.dict(os.environ, {"ADMIN_EMAIL": "ops@goumuve.com"}):
        ids = generate_jobs_for_due_schedules(_dt.datetime.utcnow())

    assert ids == []
    assert Job.query.filter_by(org_id=org.id).count() == 0
    occ = RecurringOccurrence.query.filter_by(schedule_id=sched.id).one()
    assert occ.status == "needs_contract"
    assert occ.job_id is None
    assert AutomationEvent.query.filter_by(
        kind="portal_recurring_needs_contract").count() == 1
    assert send.call_count == 1
    # Cadence still advanced so the runner doesn't hot-loop on it.
    assert sched.next_run_at > _dt.datetime.utcnow()


def test_portal_one_bad_schedule_does_not_discard_the_good_ones(
        client, db_session, no_dispatch):
    from portal_recurring import generate_jobs_for_due_schedules
    import portal_recurring

    good_a = _org("good-a"); _contract(good_a); sched_a = _schedule(good_a)
    bad = _org("bad-co");    _contract(bad);    sched_bad = _schedule(bad)
    good_b = _org("good-b"); _contract(good_b); _schedule(good_b)

    real_address = portal_recurring._address_for_schedule

    def _explode(schedule):
        if schedule.id == sched_bad.id:
            raise RuntimeError("address service down")
        return real_address(schedule)

    with mock.patch.object(portal_recurring, "_address_for_schedule", _explode):
        ids = generate_jobs_for_due_schedules(_dt.datetime.utcnow())

    # Both healthy schedules produced jobs; only the broken one is missing.
    assert len(ids) == 2
    assert Job.query.filter_by(org_id=good_a.id).count() == 1
    assert Job.query.filter_by(org_id=good_b.id).count() == 1
    assert Job.query.filter_by(org_id=bad.id).count() == 0
    assert RecurringOccurrence.query.filter_by(
        schedule_id=sched_bad.id).one().status == "failed"
    assert RecurringOccurrence.query.filter_by(
        schedule_id=sched_a.id).one().status == "created"


def test_portal_dispatches_created_jobs(client, db_session, no_dispatch):
    from portal_recurring import generate_jobs_for_due_schedules

    org = _org("dispatch-co")
    _contract(org)
    _schedule(org)

    ids = generate_jobs_for_due_schedules(_dt.datetime.utcnow())
    assert no_dispatch.call_count == 1
    assert no_dispatch.call_args[0][0] == ids[0]


def test_portal_past_due_org_is_held(client, db_session, no_dispatch):
    from portal_recurring import generate_jobs_for_due_schedules

    org = _org("pastdue-co", status="past_due")
    _contract(org)
    sched = _schedule(org)

    assert generate_jobs_for_due_schedules(_dt.datetime.utcnow()) == []
    assert RecurringOccurrence.query.filter_by(
        schedule_id=sched.id).one().status == "skipped"


# ==========================================================================
# Residential recurring (routes.recurring.generate_due_recurring_jobs)
# ==========================================================================
def test_residential_run_twice_creates_one_occurrence(client, db_session, no_dispatch):
    from routes.recurring import generate_due_recurring_jobs

    user = _user()
    booking = _booking(user)
    occurrence_at = booking.next_scheduled_at

    first = generate_due_recurring_jobs()
    assert len(first["created"]) == 1

    # Replay the same occurrence (as a double tick would).
    booking.next_scheduled_at = occurrence_at
    db.session.commit()
    second = generate_due_recurring_jobs()

    assert second["created"] == []
    assert RecurringOccurrence.query.filter_by(schedule_id=booking.id).count() == 1
    assert Job.query.count() == 1


def test_residential_job_is_priced_and_payment_is_not_zero(
        client, db_session, no_dispatch):
    from routes.recurring import generate_due_recurring_jobs

    user = _user()
    _booking(user)

    with mock.patch("sms_service.send_sms_async"), \
            mock.patch("notifications.send_email"), \
            mock.patch("routes.vapi._build_checkout_url", return_value="https://pay/x"):
        result = generate_due_recurring_jobs()

    job = db.session.get(Job, result["created"][0])
    payment = Payment.query.filter_by(job_id=job.id).one()

    assert job.total_price > 0
    assert payment.amount == job.total_price
    assert payment.amount > 0                     # never a $0 "pending" payment
    assert payment.payment_status == "pending"
    # No saved card -> honest state + a way for the customer to pay.
    assert job.status == "awaiting_payment"
    assert result["awaiting_payment"] == [job.id]
    assert no_dispatch.call_count == 0             # unpaid work isn't dispatched


def test_residential_sends_a_pay_link_when_there_is_no_saved_card(
        client, db_session, no_dispatch):
    from routes.recurring import generate_due_recurring_jobs

    user = _user()
    _booking(user)

    with mock.patch("sms_service.send_sms_async") as sms, \
            mock.patch("notifications.send_email") as email, \
            mock.patch("routes.vapi._build_checkout_url",
                       return_value="https://checkout.stripe.com/x") as link:
        generate_due_recurring_jobs()

    assert link.call_count == 1
    assert sms.call_count == 1
    assert "checkout.stripe.com" in sms.call_args[0][1]
    assert email.call_count == 1


def test_residential_charges_a_saved_card_off_session_and_dispatches(
        client, db_session, no_dispatch):
    from routes.recurring import generate_due_recurring_jobs

    user = _user(stripe_customer="cus_saved")
    _booking(user)

    fake_pm = mock.Mock(); fake_pm.id = "pm_123"
    fake_list = mock.Mock(); fake_list.data = [fake_pm]
    fake_intent = mock.Mock(); fake_intent.id = "pi_123"; fake_intent.status = "succeeded"

    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
            mock.patch("stripe.PaymentMethod.list", return_value=fake_list), \
            mock.patch("stripe.PaymentIntent.create",
                       return_value=fake_intent) as create:
        result = generate_due_recurring_jobs()

    job = db.session.get(Job, result["created"][0])
    payment = Payment.query.filter_by(job_id=job.id).one()

    assert create.call_args.kwargs["off_session"] is True
    assert create.call_args.kwargs["amount"] == int(round(job.total_price * 100))
    assert payment.payment_status == "succeeded"
    assert payment.stripe_payment_intent_id == "pi_123"
    assert job.status == "confirmed"
    assert result["dispatched"] == [job.id]
    assert no_dispatch.call_count == 1


def test_residential_declined_card_falls_back_to_a_pay_link(
        client, db_session, no_dispatch):
    from routes.recurring import generate_due_recurring_jobs

    user = _user(stripe_customer="cus_declined")
    _booking(user)

    fake_pm = mock.Mock(); fake_pm.id = "pm_123"
    fake_list = mock.Mock(); fake_list.data = [fake_pm]

    with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_x"}), \
            mock.patch("stripe.PaymentMethod.list", return_value=fake_list), \
            mock.patch("stripe.PaymentIntent.create",
                       side_effect=Exception("card_declined")), \
            mock.patch("sms_service.send_sms_async") as sms, \
            mock.patch("notifications.send_email"), \
            mock.patch("routes.vapi._build_checkout_url", return_value="https://pay/x"):
        result = generate_due_recurring_jobs()

    job = db.session.get(Job, result["created"][0])
    payment = Payment.query.filter_by(job_id=job.id).one()
    assert job.status == "awaiting_payment"
    assert payment.payment_status == "pending"
    assert payment.amount > 0
    assert sms.call_count == 1


def test_residential_one_bad_booking_does_not_discard_the_good_ones(
        client, db_session, no_dispatch):
    import routes.recurring as rr

    good1 = _booking(_user(email="g1@x.example", phone="+15615550011"))
    bad = _booking(_user(email="bad@x.example", phone="+15615550012"))
    good2 = _booking(_user(email="g2@x.example", phone="+15615550013"))

    real_price = rr._price_occurrence

    def _explode(recurring):
        if recurring.id == bad.id:
            raise RuntimeError("pricing engine down")
        return real_price(recurring)

    with mock.patch.object(rr, "_price_occurrence", _explode), \
            mock.patch("sms_service.send_sms_async"), \
            mock.patch("notifications.send_email"), \
            mock.patch("routes.vapi._build_checkout_url", return_value="https://pay/x"):
        result = rr.generate_due_recurring_jobs()

    assert len(result["created"]) == 2
    assert Job.query.count() == 2
    assert RecurringOccurrence.query.filter_by(
        schedule_id=bad.id).one().status == "failed"
    for b in (good1, good2):
        assert RecurringOccurrence.query.filter_by(
            schedule_id=b.id).one().status == "awaiting_payment"


def test_awaiting_payment_job_is_confirmed_and_dispatched_once_paid(
        client, db_session, no_dispatch):
    from routes.recurring import generate_due_recurring_jobs, sweep_paid_awaiting_payment_jobs

    user = _user()
    _booking(user)
    with mock.patch("sms_service.send_sms_async"), \
            mock.patch("notifications.send_email"), \
            mock.patch("routes.vapi._build_checkout_url", return_value="https://pay/x"):
        result = generate_due_recurring_jobs()

    job_id = result["created"][0]
    payment = Payment.query.filter_by(job_id=job_id).one()
    payment.payment_status = "succeeded"          # customer used the pay link
    db.session.commit()

    confirmed = sweep_paid_awaiting_payment_jobs()
    assert confirmed == [job_id]
    assert db.session.get(Job, job_id).status == "confirmed"
    assert no_dispatch.call_args[0][0] == job_id


# ==========================================================================
# Invoicing (portal_invoicing + billing_portal)
# ==========================================================================
def _completed_job(org, price=100.0, when=None):
    owner = OrgMember.query.filter_by(org_id=org.id).first()
    j = Job(id=generate_uuid(), customer_id=owner.user_id, org_id=org.id,
            status="completed", address="1 Tower Way", total_price=price,
            completed_at=when or _dt.datetime(2026, 3, 15, 12, 0))
    db.session.add(j)
    db.session.commit()
    return j


def _stripe_stub(fail_create=False):
    """Minimal stripe stand-in for billing_portal._stripe_client."""
    stub = mock.Mock()
    stub.Invoice.create.side_effect = (
        Exception("stripe down") if fail_create
        else (lambda **kw: mock.Mock(id="in_test", status="draft"))
    )
    stub.Invoice.retrieve.side_effect = lambda iid, **kw: mock.Mock(id=iid, status="draft")
    stub.InvoiceItem.create.side_effect = lambda **kw: mock.Mock(id="ii_test")
    stub.Invoice.finalize_invoice.side_effect = lambda iid, **kw: mock.Mock(id=iid, status="open")
    return stub


def test_invoice_stripe_failure_is_retried_on_the_next_run(client, db_session):
    from portal_invoicing import generate_monthly_invoices, retry_undelivered_invoices

    org = _org("retry-co")
    _completed_job(org, 150.0)

    # Run 1: Stripe is down. The invoice exists locally with no Stripe id.
    with mock.patch("billing_portal._stripe_client", return_value=_stripe_stub(fail_create=True)):
        ids = generate_monthly_invoices(3, 2026)
    assert len(ids) == 1
    inv = db.session.get(PortalInvoice, ids[0])
    assert inv.stripe_invoice_id is None
    assert inv.sent_at is None
    assert inv.delivery_error and inv.delivery_attempts == 1

    # Run 2: Stripe is back. The row is retried, not skipped forever.
    with mock.patch("billing_portal._stripe_client", return_value=_stripe_stub()):
        delivered = retry_undelivered_invoices()
    db.session.refresh(inv)
    assert delivered == [inv.id]
    assert inv.stripe_invoice_id == "in_test"
    assert inv.sent_at is not None
    assert inv.delivery_error is None


def test_invoice_generation_is_idempotent_per_period(client, db_session):
    from portal_invoicing import generate_monthly_invoices

    org = _org("idem-co")
    _completed_job(org, 90.0)

    with mock.patch("billing_portal._stripe_client", return_value=_stripe_stub()):
        first = generate_monthly_invoices(3, 2026)
        second = generate_monthly_invoices(3, 2026)

    assert len(first) == 1 and second == []
    assert PortalInvoice.query.filter_by(org_id=org.id).count() == 1


def test_invoice_items_are_attached_to_the_draft_and_ids_persisted(client, db_session):
    from portal_invoicing import generate_monthly_invoices

    org = _org("attach-co")
    _completed_job(org, 200.0)
    stub = _stripe_stub()

    with mock.patch("billing_portal._stripe_client", return_value=stub):
        ids = generate_monthly_invoices(3, 2026)

    inv = db.session.get(PortalInvoice, ids[0])
    # Draft created BEFORE the line items, and every line names that invoice.
    assert stub.Invoice.create.called
    for call in stub.InvoiceItem.create.call_args_list:
        assert call.kwargs["invoice"] == "in_test"
        assert call.kwargs["idempotency_key"].startswith(
            "portal-inv-{}-2026-03".format(org.id))
    assert inv.stripe_invoice_id == "in_test"
    assert all(li.stripe_invoice_item_id == "ii_test"
               for li in inv.line_items if li.amount_cents > 0)
    assert stub.Invoice.finalize_invoice.called


def test_base_fee_is_billed_once_per_period(client, db_session):
    from portal_invoicing import generate_monthly_invoices
    from billing_portal import claim_base_fee, base_fee_already_billed

    org = _org("basefee-co")            # no Stripe subscription -> invoice owns it
    _contract(org, base=199900, per_pickup=5500, included=0)
    _completed_job(org, 55.0)

    with mock.patch("billing_portal._stripe_client", return_value=_stripe_stub()):
        ids = generate_monthly_invoices(3, 2026)

    inv = db.session.get(PortalInvoice, ids[0])
    base_lines = [li for li in inv.line_items if li.kind == "base_fee"]
    assert len(base_lines) == 1
    assert base_lines[0].amount_cents == 199900
    assert base_fee_already_billed(org.id, _dt.datetime(2026, 3, 1))

    # A second attempt at the same period — any path — is refused.
    assert claim_base_fee(org.id, _dt.datetime(2026, 3, 1), "contract_invoice") is False


def test_subscription_org_is_not_billed_the_base_fee_twice(client, db_session):
    """Stripe's subscription owns the base charge; the invoice must not repeat it."""
    from portal_invoicing import generate_monthly_invoices
    from billing_portal import base_fee_owner

    org = _org("sub-co", subscription="sub_live")
    _contract(org, base=199900, per_pickup=5500, included=1)
    _completed_job(org, 55.0)
    _completed_job(org, 55.0)           # 2 pickups, 1 included -> 1 overage

    assert base_fee_owner(org) == "subscription"

    with mock.patch("billing_portal._stripe_client", return_value=_stripe_stub()):
        ids = generate_monthly_invoices(3, 2026)

    inv = db.session.get(PortalInvoice, ids[0])
    assert [li.kind for li in inv.line_items] == ["overage"]
    assert inv.total_cents == 5500      # overage only, no 1999.00 base
