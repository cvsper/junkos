"""VA pay statement: hours (unpaid + auto-close cap), hauler sign-ups, bookings."""
import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from models import (db, generate_uuid, CallAttempt, CallProspect, Contractor, DeskSetting, Job,
                    User, VaDispatchAction, VaShift)
from va_pay import booking_bonus, pay_statement, pay_rules


def _frozen_utc():
    from timeutils import to_local, local_naive_to_utc
    d = to_local(datetime.now(timezone.utc)).date()
    return local_naive_to_utc(datetime.combine(d, datetime.min.time()).replace(hour=20))


def _now():
    return _frozen_utc().astimezone(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def env(app):
    with mock.patch.dict(os.environ, {"TRIXIE_ASSISTANT_PASSCODE": "test-code",
                                      "VA_PAY_PERIOD_ANCHOR": "2026-08-06",
                                      "VA_AUTO_CLOSE_PAY_HOURS": "8"}), \
         mock.patch("va_time._now_utc", return_value=_frozen_utc()), \
         mock.patch("va_pay._now_utc", return_value=_frozen_utc()):
        DeskSetting.put("va_rate:tracy", "1.25")
        yield
    db.session.rollback()
    VaDispatchAction.query.delete(); CallAttempt.query.delete(); CallProspect.query.delete()
    VaShift.query.delete(); DeskSetting.query.delete()
    Contractor.query.delete(); Job.query.delete(); User.query.delete(); db.session.commit()


def _period_start():
    from va_time import period_bounds
    return period_bounds(now_utc=_frozen_utc())[0]


def _shift(hours, day_offset=0, unpaid=False, auto=False):
    start = _period_start() + timedelta(days=day_offset, hours=14)
    sh = VaShift(va_name="Tracy", started_at=start, ended_at=start + timedelta(hours=hours),
                 unpaid=unpaid, unpaid_reason="internet outage" if unpaid else None, auto_closed=auto)
    db.session.add(sh); db.session.commit(); return sh


def _prospect(company, digits, outcome="converted", va="Tracy", at=None):
    p = CallProspect(company=company, phone="({}) {}-{}".format(digits[:3], digits[3:6], digits[6:]),
                     phone_digits=digits, tier=1, status="converted")
    db.session.add(p); db.session.flush()
    db.session.add(CallAttempt(prospect_id=p.id, outcome=outcome, va_name=va,
                               created_at=at or _period_start() + timedelta(hours=15)))
    db.session.commit(); return p


def _hauler(digits, at=None):
    u = User(id=generate_uuid(), email="h{}@x.com".format(digits), name="Hauler " + digits,
             phone="+1" + digits, role="driver")
    db.session.add(u); db.session.flush()
    c = Contractor(id=generate_uuid(), user_id=u.id, approval_status="approved",
                   created_at=at or _period_start() + timedelta(days=1))
    db.session.add(c); db.session.commit(); return c


def _job(total, status="pending", at=None):
    u = User(id=generate_uuid(), email=generate_uuid()[:8] + "@c.com", name="Cust", role="customer")
    db.session.add(u); db.session.flush()
    j = Job(id=generate_uuid(), customer_id=u.id, status=status, address="1 Lake Ave",
            total_price=total, confirmation_code="PX" + generate_uuid()[:6].upper(),
            created_at=at or _period_start() + timedelta(days=1),
            completed_at=(_period_start() + timedelta(days=2)) if status == "completed" else None)
    db.session.add(j); db.session.commit(); return j


def test_hours_skip_unpaid_and_cap_auto_closed():
    _shift(7.5, 0)
    _shift(8.8, 1, unpaid=True)
    _shift(12, 2, auto=True)
    st = pay_statement("Tracy")
    assert st["hours"] == 15.5                      # 7.5 + 8 (capped), outage day excluded
    assert st["hours_pay"] == round(15.5 * 1.25, 2)
    assert st["unpaid_hours"] == 8.8 and st["capped_hours"] == 4.0


def test_signup_counts_only_haulers_she_called():
    _prospect("Code 3 Junk", "7542464700"); _hauler("7542464700")
    _prospect("Voicemail Co", "5610000000", outcome="voicemail"); _hauler("5610000000")
    _prospect("Other VA Co", "5612222222", va="Damian"); _hauler("5612222222")
    _hauler("5619999999")                               # signed up with no call from her
    st = pay_statement("Tracy")
    assert st["signup_count"] == 2 and st["signup_pay"] == 2.0
    assert sorted(x["company"] for x in st["signups"]) == ["Code 3 Junk", "Voicemail Co"]


def test_signup_before_her_first_call_does_not_count():
    _hauler("9540001111", at=_period_start() + timedelta(hours=1))
    _prospect("Already In", "9540001111", at=_period_start() + timedelta(days=3))
    assert pay_statement("Tracy")["signup_count"] == 0


def test_booking_bonus_is_ten_percent_between_5_and_50():
    assert booking_bonus(30) == 5.0
    assert booking_bonus(249) == 24.9
    assert booking_bonus(900) == 50.0


def test_booking_pays_only_when_completed():
    done = _job(249, "completed"); pend = _job(119, "confirmed"); dead = _job(599, "cancelled")
    for j in (done, pend, dead):
        db.session.add(VaDispatchAction(job_id=j.id, action="log_job", va_name="Tracy"))
    db.session.commit()
    st = pay_statement("Tracy")
    assert st["booking_pay"] == 24.9
    assert st["booking_pending"] == 11.9
    assert st["booking_count"] == 2
    states = sorted(b["state"] for b in st["bookings"])
    assert states == ["cancelled", "payable", "pending"]


def test_total_adds_the_three_lines():
    _shift(8, 0)
    _prospect("A", "7860000001"); _hauler("7860000001")
    j = _job(300, "completed"); db.session.add(VaDispatchAction(job_id=j.id, action="log_job", va_name="Tracy")); db.session.commit()
    st = pay_statement("Tracy")
    assert st["total"] == round(8 * 1.25 + 1 + 30, 2)


def test_va_sees_own_pay_not_someone_elses(client):
    r = client.post("/api/va/time/pay", json={"code": "test-code", "va_name": "Tracy"})
    assert r.status_code == 200 and r.get_json()["va_name"] == "Tracy"
    r = client.post("/api/va/time/pay", json={"code": "test-code", "va_name": "Tracy", "va": "Damian"})
    assert r.status_code == 403


def test_rules_default_and_reading(client):
    r = client.post("/api/va/time/pay-rules", json={"code": "test-code", "va_name": "Tracy"})
    assert r.status_code == 200
    assert r.get_json()["rules"] == {"signup_bonus": 1.0, "booking_pct": 0.1, "booking_min": 5.0, "booking_max": 50.0}
    r = client.post("/api/va/time/pay-rules", json={"code": "test-code", "va_name": "Tracy", "signup_bonus": 5})
    assert r.status_code == 403


def test_team_pay_lists_every_va_for_the_period(client):
    _shift(8, 0)
    sh = VaShift(va_name="Damian", started_at=_period_start() + timedelta(days=1, hours=14),
                 ended_at=_period_start() + timedelta(days=1, hours=18))
    db.session.add(sh); db.session.commit()
    DeskSetting.put("va_rate:damian", "2")
    r = client.post("/api/va/time/team-pay", json={"code": "test-code", "va_name": "Tracy"})
    assert r.status_code == 200
    body = r.get_json()
    by = {v["va_name"]: v["total"] for v in body["vas"]}
    assert by == {"Damian": 8.0, "Tracy": 10.0} and body["total"] == 18.0
