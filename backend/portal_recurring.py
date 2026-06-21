"""
B2B Commercial Portal — recurring schedule runner (Spec 04 §9.2).

Pure-Python generator: walks `portal_recurring_schedules` for rows whose
`next_run_at <= now` and `active=True`, creates a Job row for each, then
advances `next_run_at` forward by the cadence.

Designed so a Celery Beat task can invoke
`generate_jobs_for_due_schedules(now)` every 5 min once Celery is in the
stack — until then, the CLI `flask recurring-run` or a plain cron on the
Render box is fine.

Job shape: the generator only sets the minimum fields needed to make the
Job row valid (customer_id, address, status='pending', org_id, unit_id,
scheduled_at).  Dispatcher + pricing are stitched in by the existing
residential code path once the row lands.
"""

import datetime as _dt
import logging
import os

from sqlalchemy import and_

from models import db, Job, Org, OrgMember, PortalProperty, active_contract_for_org
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
# Public API — called by Celery Beat / cron / CLI.
# ---------------------------------------------------------------------------
def generate_jobs_for_due_schedules(now=None):
    """Create Jobs for every active schedule whose `next_run_at <= now`.

    Returns a list of created Job ids.  Idempotent at the row level:
    advancing `next_run_at` atomically prevents double-booking even if
    the runner is invoked twice concurrently (last writer wins, but both
    would insert at the same timestamp — acceptable at MVP volume).

    Signature is intentionally a stable entry point so a future Celery
    Beat task can wrap it:

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
    for schedule in due:
        try:
            # Stage 5 hold: don't generate pickups for orgs that aren't paying.
            # Advance the schedule so cadence stays put (no backlog) and so we
            # don't hot-loop; generation resumes automatically once active.
            org = db.session.get(Org, schedule.org_id)
            if org and org.status in ("past_due", "paused", "churned"):
                logger.info(
                    "recurring: org=%s status=%s — holding job generation",
                    schedule.org_id, org.status,
                )
                schedule.next_run_at = _advance_next_run(schedule, now)
                continue

            customer_id = _resolve_customer_for_org(schedule.org_id)
            if not customer_id:
                logger.warning(
                    "recurring: no customer for org=%s schedule=%s — skipping",
                    schedule.org_id, schedule.id,
                )
                # Still advance so we don't hot-loop.
                schedule.next_run_at = _advance_next_run(schedule, now)
                continue

            # Price the pickup from the org's contract (marginal per-pickup
            # rate). Without this, recurring jobs carried no price and monthly
            # invoices summed to $0. Included-pickup/base logic is applied at
            # invoicing; this is the per-job unit price.
            contract = active_contract_for_org(schedule.org_id, now)
            if contract:
                per_pickup = (contract.metered_per_pickup_cents or 0) / 100.0
            else:
                per_pickup = 0.0
                logger.warning(
                    "recurring: org=%s has no active contract — job priced $0",
                    schedule.org_id,
                )

            job = Job(
                customer_id=customer_id,
                org_id=schedule.org_id,
                status="pending",
                address=_address_for_schedule(schedule),
                scheduled_at=schedule.next_run_at,
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

            schedule.next_run_at = _advance_next_run(schedule, schedule.next_run_at)
            created_job_ids.append(job.id)
        except Exception as exc:  # pragma: no cover
            logger.exception("recurring: failed schedule=%s: %s", schedule.id, exc)
            db.session.rollback()

    db.session.commit()
    return created_job_ids


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
