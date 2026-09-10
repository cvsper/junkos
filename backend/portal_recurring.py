"""
B2B Commercial Portal — recurring schedule runner (Spec 04 §9.2).

Walks `portal_recurring_schedules` for rows whose `next_run_at <= now` and
`active=True`, materialises one priced Job per due occurrence, dispatches it,
then advances `next_run_at` by the cadence.

Reliability rules (audit F24):
  * **Uniqueness key** — every occurrence claims a
    ``recurring_occurrences`` row on (schedule_id, occurrence_at) before any
    work happens. The unique constraint means a concurrent or repeated run
    produces one job, not two, without needing a row lock.
  * **Per-occurrence transactions** — each schedule runs inside its own
    ``db.session.begin_nested()`` savepoint, so one bad schedule rolls back
    alone instead of discarding every job created earlier in the sweep.
  * **No $0 jobs** — an org with no active Contract gets NOTHING created.
    The occurrence is recorded ``needs_contract`` and an alert fires
    (AutomationEvent + admin email) so somebody puts a rate card on file.
  * **Dispatch runs** — created jobs go through ``dispatcher.auto_assign_job_async``
    after the commit, the same entry point the residential booking flow uses.
    A Job nobody was ever offered is not a service.

Called by ``scheduler._portal_recurring_tick`` (every 5 min), the Celery
``portal.recurring_tick`` task, or ``flask recurring-run``.
"""

import datetime as _dt
import logging
import os

from sqlalchemy import and_

from models import (
    db, Job, Org, OrgMember, PortalProperty, RecurringOccurrence,
    AutomationEvent, active_contract_for_org,
)
from portal_v1_models import PortalRecurringSchedule, PortalUnit

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cadence advancement
# ---------------------------------------------------------------------------
def _advance_next_run(schedule, after):
    """Return the next `next_run_at` after `after` for this cadence."""
    if schedule.cadence == "weekly":
        return after + _dt.timedelta(days=7)
    if schedule.cadence == "biweekly":
        return after + _dt.timedelta(days=14)
    if schedule.cadence == "monthly":
        # Naive month bump — add ~30d is wrong at month boundaries.
        # Use the day_of_month if set, else replicate the current day.
        year = after.year
        month = after.month + 1
        if month > 12:
            month = 1
            year += 1
        day = schedule.day_of_month or after.day
        # Clamp to the month's length (simple: 28 is always safe).
        day = min(day, 28)
        try:
            return after.replace(year=year, month=month, day=day)
        except ValueError:  # pragma: no cover
            return after.replace(year=year, month=month, day=28)
    # Unknown cadence — push out a week so we don't tight-loop.
    return after + _dt.timedelta(days=7)


# ---------------------------------------------------------------------------
# Job creation helper
# ---------------------------------------------------------------------------
def _resolve_customer_for_org(org_id):
    """Pick a user to attribute the generated Job to.

    Jobs.customer_id is NOT NULL, so we need a user.  Prefer the org's
    owner; fall back to any member.  Returns user_id or None.
    """
    owner = (
        db.session.query(OrgMember)
        .filter_by(org_id=org_id, role="owner")
        .first()
    )
    if owner:
        return owner.user_id
    any_member = (
        db.session.query(OrgMember).filter_by(org_id=org_id).first()
    )
    return any_member.user_id if any_member else None


def _address_for_schedule(schedule):
    """Compose a best-effort address string for the generated Job."""
    prop = db.session.get(PortalProperty, schedule.property_id)
    if not prop:
        return "Property removed"
    parts = [prop.address_line1 or prop.name]
    if schedule.unit_id:
        unit = db.session.get(PortalUnit, schedule.unit_id)
        if unit:
            parts.append("Unit {}".format(unit.unit_number))
    if prop.city:
        parts.append(prop.city)
    if prop.state:
        parts.append(prop.state)
    if prop.zip:
        parts.append(prop.zip)
    return ", ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Occurrence bookkeeping + alerting
# ---------------------------------------------------------------------------
def _claim_occurrence(schedule, occurrence_at):
    """Insert the (schedule_id, occurrence_at) uniqueness row.

    Returns the RecurringOccurrence when THIS run owns the occurrence, or
    None when another run already claimed it (duplicate — do no work).
    """
    from sqlalchemy.exc import IntegrityError

    occ = RecurringOccurrence(
        kind="portal", schedule_id=schedule.id, occurrence_at=occurrence_at,
        status="created",
    )
    try:
        with db.session.begin_nested():
            db.session.add(occ)
            db.session.flush()
        return occ
    except IntegrityError:
        logger.info(
            "recurring: occurrence already claimed schedule=%s at=%s — skipping",
            schedule.id, occurrence_at,
        )
        return None


def _alert_needs_contract(org, schedule, occurrence_at):
    """Tell an admin an org's recurring pickup could not be priced.

    Exactly once per (schedule, occurrence) via AutomationEvent. Never raises
    — a failed alert must not abort the sweep.
    """
    from sqlalchemy.exc import IntegrityError

    subject = "{}:{}".format(schedule.id, occurrence_at.strftime("%Y-%m-%dT%H:%M"))
    try:
        with db.session.begin_nested():
            db.session.add(AutomationEvent(
                kind="portal_recurring_needs_contract",
                subject_type="recurring_schedule",
                subject_id=subject,
                detail="org={} property={}".format(schedule.org_id, schedule.property_id),
            ))
    except IntegrityError:
        return  # already alerted for this occurrence

    logger.warning(
        "recurring: org=%s schedule=%s has NO active contract — no job created "
        "(needs_contract)", schedule.org_id, schedule.id,
    )
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if not admin_email:
        return
    try:
        from notifications import send_email
        send_email(
            admin_email,
            "Umuve: recurring pickup blocked — no contract on file",
            "<p>{} has a recurring pickup due ({}) but no active contract, so "
            "no job was created.</p><p>Put a rate card on file "
            "(POST /portal/v1/billing/contracts) and the next run will "
            "generate it.</p><p>schedule={} property={}</p>".format(
                (org.name if org else schedule.org_id),
                occurrence_at.isoformat(), schedule.id, schedule.property_id,
            ),
        )
    except Exception:
        logger.exception("needs_contract alert email failed for org=%s", schedule.org_id)


def _pickup_price(contract):
    """Per-pickup price (dollars) for a contract, or None when the contract
    cannot price a pickup at all (no base, no included pickups, no rate)."""
    if contract is None:
        return None
    per_pickup_cents = contract.metered_per_pickup_cents or 0
    base_cents = contract.monthly_base_cents or 0
    included = contract.included_pickups or 0
    if per_pickup_cents <= 0 and base_cents <= 0 and included <= 0:
        # An empty contract prices nothing — same as having none.
        return None
    # Included pickups are paid for by the monthly base; the marginal rate is
    # what this job is worth. Zero here is legitimate (covered by the base).
    return per_pickup_cents / 100.0


# ---------------------------------------------------------------------------
# Public API — called by Celery Beat / cron / CLI.
# ---------------------------------------------------------------------------
def generate_jobs_for_due_schedules(now=None):
    """Create + dispatch Jobs for every active schedule whose
    ``next_run_at <= now``.

    Returns a list of created Job ids. Safe to run concurrently: each
    occurrence is claimed on (schedule_id, occurrence_at) first, so the
    second runner creates nothing. Safe to run repeatedly: the same
    occurrence is never materialised twice.

    Signature is intentionally a stable entry point so a Celery Beat task can
    wrap it:

        @celery.task
        def recurring_tick():
            return generate_jobs_for_due_schedules()
    """
    if now is None:
        now = _dt.datetime.utcnow()

    due = (
        db.session.query(PortalRecurringSchedule)
        .filter(
            and_(
                PortalRecurringSchedule.active == True,  # noqa: E712
                PortalRecurringSchedule.paused_at == None,  # noqa: E711
                PortalRecurringSchedule.next_run_at <= now,
            )
        )
        .all()
    )

    created_job_ids = []
    needs_contract = []
    for schedule in due:
        occurrence_at = schedule.next_run_at
        occ = _claim_occurrence(schedule, occurrence_at)
        if occ is None:
            # Another run owns this occurrence; leave next_run_at to it.
            continue
        try:
            # Each occurrence is its own transaction: a failure here rolls
            # back THIS schedule only — jobs created earlier in the sweep and
            # the occurrence claim above both survive.
            with db.session.begin_nested():
                # Stage 5 hold: don't generate pickups for orgs that aren't
                # paying. Advance the schedule so cadence stays put (no
                # backlog); generation resumes automatically once active.
                org = db.session.get(Org, schedule.org_id)
                if org and org.status in ("past_due", "paused", "churned"):
                    logger.info(
                        "recurring: org=%s status=%s — holding job generation",
                        schedule.org_id, org.status,
                    )
                    occ.status = "skipped"
                    occ.detail = "org_status={}".format(org.status)
                    schedule.next_run_at = _advance_next_run(schedule, now)
                    continue

                customer_id = _resolve_customer_for_org(schedule.org_id)
                if not customer_id:
                    logger.warning(
                        "recurring: no customer for org=%s schedule=%s — skipping",
                        schedule.org_id, schedule.id,
                    )
                    occ.status = "skipped"
                    occ.detail = "no_org_member"
                    schedule.next_run_at = _advance_next_run(schedule, now)
                    continue

                # A pickup we cannot price is not a pickup we book. Creating a
                # $0 "pending" job here is what made recurring B2B revenue
                # vanish into invoices that summed to nothing.
                contract = active_contract_for_org(schedule.org_id, now)
                per_pickup = _pickup_price(contract)
                if per_pickup is None:
                    occ.status = "needs_contract"
                    occ.detail = "no active contract for org {}".format(schedule.org_id)
                    schedule.next_run_at = _advance_next_run(schedule, now)
                    needs_contract.append((org, schedule, occurrence_at))
                    continue

                job = Job(
                    customer_id=customer_id,
                    org_id=schedule.org_id,
                    status="pending",
                    address=_address_for_schedule(schedule),
                    scheduled_at=occurrence_at,
                    total_price=per_pickup,
                    base_price=per_pickup,
                    item_total=per_pickup,
                )
                # unit_id is a v1 column added via migration on the existing
                # jobs table — set via __dict__ to bypass mapper lag in tests
                # where db.create_all() ran before the column was added.
                if schedule.unit_id:
                    try:
                        job.unit_id = schedule.unit_id  # if mapper has it
                    except Exception:
                        pass
                db.session.add(job)
                db.session.flush()

                # If the mapper didn't carry unit_id, set it via raw UPDATE so
                # the audit trail still reflects the unit.
                if schedule.unit_id:
                    try:
                        from sqlalchemy import text
                        db.session.execute(
                            text("UPDATE jobs SET unit_id = :u WHERE id = :j"),
                            {"u": schedule.unit_id, "j": job.id},
                        )
                    except Exception as exc:  # pragma: no cover
                        logger.warning("recurring: unit_id stamp failed: %s", exc)

                occ.job_id = job.id
                occ.status = "created"
                schedule.next_run_at = _advance_next_run(schedule, occurrence_at)
                created_job_ids.append(job.id)
        except Exception as exc:
            # The savepoint already rolled this schedule's work back; the
            # occurrence claim survives so we don't retry a poisoned row
            # forever. Other schedules in `due` are untouched.
            logger.exception("recurring: failed schedule=%s: %s", schedule.id, exc)
            try:
                occ.status = "failed"
                occ.detail = str(exc)[:500]
                schedule.next_run_at = _advance_next_run(schedule, now)
            except Exception:  # pragma: no cover
                logger.exception("recurring: could not mark occurrence failed")

    db.session.commit()

    # Alerts + dispatch happen after the commit so the rows exist.
    for org, schedule, occurrence_at in needs_contract:
        try:
            _alert_needs_contract(org, schedule, occurrence_at)
        except Exception:  # pragma: no cover
            logger.exception("needs_contract alert failed for schedule=%s", schedule.id)
    if needs_contract:
        db.session.commit()

    _dispatch_created_jobs(created_job_ids)
    return created_job_ids


def _dispatch_created_jobs(job_ids):
    """Hand every materialised job to the dispatcher (respects DISPATCH_MODE).

    Without this a recurring Job sat in ``pending`` forever with no hauler
    ever notified. Never raises — the Jobs are already persisted.
    """
    if not job_ids:
        return
    try:
        from flask import current_app
        from dispatcher import auto_assign_job_async
        app_obj = current_app._get_current_object()
    except Exception:
        logger.exception("Could not import dispatcher for portal recurring jobs")
        return
    for job_id in job_ids:
        try:
            auto_assign_job_async(job_id, app_obj)
        except Exception:
            logger.exception("Portal recurring dispatch failed for job %s", job_id)


# ---------------------------------------------------------------------------
# CLI: `flask recurring-run`
# ---------------------------------------------------------------------------
def register_cli(app):
    """Register the Flask CLI command.  Safe to call multiple times."""
    import click

    @app.cli.command("recurring-run")
    @click.option(
        "--dry-run",
        is_flag=True,
        help="Print what would run without creating Jobs.",
    )
    def recurring_run(dry_run):
        """Generate Jobs for any recurring schedules that are due."""
        now = _dt.datetime.utcnow()
        if dry_run:
            due = (
                db.session.query(PortalRecurringSchedule)
                .filter(
                    PortalRecurringSchedule.active == True,  # noqa: E712
                    PortalRecurringSchedule.next_run_at <= now,
                )
                .all()
            )
            for s in due:
                click.echo(
                    "DUE schedule={} org={} property={} unit={} cadence={}".format(
                        s.id, s.org_id, s.property_id, s.unit_id, s.cadence,
                    )
                )
            click.echo("Would create {} job(s).".format(len(due)))
            return

        ids = generate_jobs_for_due_schedules(now)
        click.echo("Created {} job(s): {}".format(len(ids), ",".join(ids)))
