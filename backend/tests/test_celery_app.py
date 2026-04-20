"""
Celery wiring smoke tests (spec 04 §9 — Celery Beat rollout).

These tests verify the static configuration of `celery_app.py`:
  * Both tasks are registered under their documented names.
  * Beat schedule has both entries with sane cadences.
  * `invoice_monthly()` defaults to the *previous* calendar month.
  * Running a task in-process dispatches to the underlying generator.

We deliberately do NOT start a real broker — these tests run inline.
"""

import datetime as _dt

import pytest


def test_celery_module_imports_cleanly():
    import celery_app

    assert celery_app.celery is not None
    assert celery_app.celery.main == "umuve_portal"


def test_tasks_are_registered():
    import celery_app

    names = set(celery_app.celery.tasks.keys())
    assert "portal.recurring_tick" in names
    assert "portal.invoice_monthly" in names


def test_beat_schedule_has_both_entries():
    import celery_app

    schedule = celery_app.celery.conf.beat_schedule
    assert "portal-recurring-tick-every-5min" in schedule
    assert "portal-invoice-monthly-at-02utc-day1" in schedule

    assert (
        schedule["portal-recurring-tick-every-5min"]["task"]
        == "portal.recurring_tick"
    )
    assert (
        schedule["portal-invoice-monthly-at-02utc-day1"]["task"]
        == "portal.invoice_monthly"
    )


def test_recurring_tick_delegates_to_generator(app, monkeypatch):
    import celery_app
    import portal_recurring

    captured = {}

    def _fake(now):
        captured["now"] = now
        return ["job-xyz"]

    monkeypatch.setattr(
        portal_recurring, "generate_jobs_for_due_schedules", _fake
    )

    result = celery_app.recurring_tick.run()
    assert result == ["job-xyz"]
    assert isinstance(captured["now"], _dt.datetime)


def test_invoice_monthly_defaults_to_previous_month(app, monkeypatch):
    import celery_app
    import portal_invoicing

    captured = {}

    def _fake(month, year):
        captured["month"] = month
        captured["year"] = year
        return []

    monkeypatch.setattr(
        portal_invoicing, "generate_monthly_invoices", _fake
    )

    celery_app.invoice_monthly.run()

    today = _dt.date.today()
    first_of_this_month = today.replace(day=1)
    last_of_prev = first_of_this_month - _dt.timedelta(days=1)
    assert captured["month"] == last_of_prev.month
    assert captured["year"] == last_of_prev.year


def test_invoice_monthly_accepts_explicit_args(app, monkeypatch):
    import celery_app
    import portal_invoicing

    captured = {}

    def _fake(month, year):
        captured["month"] = month
        captured["year"] = year
        return ["inv-1", "inv-2"]

    monkeypatch.setattr(
        portal_invoicing, "generate_monthly_invoices", _fake
    )

    result = celery_app.invoice_monthly.run(month=3, year=2026)
    assert result == ["inv-1", "inv-2"]
    assert captured == {"month": 3, "year": 2026}
