"""
B2B Commercial Portal — monthly invoice generator (Spec 04 §9.3).

Finds every org with at least one completed Job in the target month,
sums the totals, and creates a `portal_invoices` row (status='open',
due_at = +30 days).  Idempotent per (org_id, period_start) — if an
invoice already exists for that org+period, we skip it.

Exposed:
  * generate_monthly_invoices(month, year)  -> list[invoice_id]
  * register_cli(app)                        — `flask invoice-monthly`
"""

import calendar as _cal
import datetime as _dt
import logging
import secrets

from sqlalchemy import and_

from models import db, Job, Org, PortalInvoice, PortalInvoiceLineItem, active_contract_for_org

logger = logging.getLogger(__name__)


def _month_range(month, year):
    """Return (period_start, period_end) UTC for the given month/year."""
    start = _dt.datetime(year, month, 1)
    last_day = _cal.monthrange(year, month)[1]
    end = _dt.datetime(year, month, last_day, 23, 59, 59)
    return start, end


def _next_invoice_number(org, period_start):
    """Generate a deterministic-ish invoice number."""
    suffix = secrets.token_hex(3).upper()
    return "INV-{}-{:04d}{:02d}-{}".format(
        (org.slug or org.id[:6])[:12].upper(),
        period_start.year,
        period_start.month,
        suffix,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_monthly_invoices(month, year):
    """Create one invoice per org with completed jobs in the month.

    Returns: list of created PortalInvoice ids.

    Math:
      subtotal_cents = sum(round(job.total_price * 100))
      tax_cents      = 0 (spec §9.3 keeps tax for v2)
      total_cents    = subtotal_cents

    Line items: one per Job.
    """
    period_start, period_end = _month_range(month, year)
    now = _dt.datetime.utcnow()

    # Pull all completed jobs in the period that carry an org_id.
    jobs = (
        db.session.query(Job)
        .filter(
            and_(
                Job.org_id.isnot(None),
                Job.status == "completed",
                Job.completed_at != None,  # noqa: E711
                Job.completed_at >= period_start,
                Job.completed_at <= period_end,
            )
        )
        .all()
    )

    # Group by org
    by_org = {}
    for j in jobs:
        by_org.setdefault(j.org_id, []).append(j)

    created_ids = []
    for org_id, org_jobs in by_org.items():
        org = db.session.get(Org, org_id)
        if org is None:
            continue

        # Idempotency: skip if we've already invoiced this org for this period.
        existing = (
            db.session.query(PortalInvoice)
            .filter(
                PortalInvoice.org_id == org_id,
                PortalInvoice.period_start == period_start,
            )
            .first()
        )
        if existing is not None:
            continue

        line_items = []
        contract = active_contract_for_org(org_id, period_end)

        if contract:
            # Contract billing: monthly base + per-pickup overage beyond the
            # included allowance. Included pickups are covered by the base.
            n = len(org_jobs)
            included = contract.included_pickups or 0
            per_pickup = contract.metered_per_pickup_cents or 0
            overage = max(0, n - included)
            base_cents = contract.monthly_base_cents or 0
            overage_cents = overage * per_pickup
            subtotal_cents = base_cents + overage_cents

            line_items.append(
                PortalInvoiceLineItem(
                    description="Monthly base — {} plan".format(contract.tier.title()),
                    quantity=1.0,
                    unit_cents=base_cents,
                    amount_cents=base_cents,
                )
            )
            if overage > 0:
                line_items.append(
                    PortalInvoiceLineItem(
                        description="Pickups: {} ({} included, {} billed)".format(
                            n, included, overage
                        ),
                        quantity=float(overage),
                        unit_cents=per_pickup,
                        amount_cents=overage_cents,
                    )
                )
            elif n > 0:
                # Informational $0 line so the invoice shows usage within plan.
                line_items.append(
                    PortalInvoiceLineItem(
                        description="Pickups: {} (all {} within plan)".format(n, included),
                        quantity=float(n),
                        unit_cents=0,
                        amount_cents=0,
                    )
                )
        else:
            # No contract on file: fall back to summing each job's own price.
            subtotal_cents = 0
            for j in org_jobs:
                amount_cents = int(round((j.total_price or 0.0) * 100))
                subtotal_cents += amount_cents
                line_items.append(
                    PortalInvoiceLineItem(
                        job_id=j.id,
                        description="Pickup {}".format(
                            (j.completed_at or now).date().isoformat()
                        ),
                        quantity=1.0,
                        unit_cents=amount_cents,
                        amount_cents=amount_cents,
                    )
                )

        invoice = PortalInvoice(
            org_id=org_id,
            number=_next_invoice_number(org, period_start),
            period_start=period_start,
            period_end=period_end,
            subtotal_cents=subtotal_cents,
            tax_cents=0,
            total_cents=subtotal_cents,
            status="open",
            due_at=now + _dt.timedelta(days=30),
            sent_at=now,
        )
        invoice.line_items = line_items
        db.session.add(invoice)
        db.session.flush()
        created_ids.append(invoice.id)

    db.session.commit()
    return created_ids


# ---------------------------------------------------------------------------
# CLI: `flask invoice-monthly --month N --year YYYY`
# ---------------------------------------------------------------------------
def register_cli(app):
    """Register `flask invoice-monthly`.  Safe to call multiple times."""
    import click

    @app.cli.command("invoice-monthly")
    @click.option("--month", type=int, required=True, help="1-12")
    @click.option("--year", type=int, required=True, help="e.g. 2026")
    def invoice_monthly(month, year):
        """Generate monthly invoices for all orgs with completed jobs."""
        if not (1 <= month <= 12):
            raise click.UsageError("--month must be 1..12")
        ids = generate_monthly_invoices(month, year)
        click.echo("Created {} invoice(s): {}".format(len(ids), ",".join(ids)))
