"""
B2B Commercial Portal — monthly invoice generator (Spec 04 §9.3).

For every org that either has an active Contract for the month or completed
at least one Job in it, create ONE `portal_invoices` row (status='open',
due_at = +30 days) and deliver it to Stripe.

Reliability rules (audit F24):
  * Idempotent per (org_id, period_start): an existing invoice is never
    re-created.
  * Per-org savepoint (``db.session.begin_nested()``): one org's failure is
    rolled back alone; the others still commit.
  * Delivery is a separate, retryable operation. An invoice that exists
    locally but was never finalized in Stripe (``sent_at IS NULL`` with a
    non-zero total) is retried on EVERY run — first thing, before new
    invoices are generated — instead of being skipped forever.
  * Base fee is billed by exactly one owner (see billing_portal docstring):
    ``billing_portal.base_fee_owner`` decides, ``claim_base_fee`` locks
    (org, period) so it can't be billed twice.

Exposed:
  * generate_monthly_invoices(month, year)  -> list[invoice_id]  (created)
  * retry_undelivered_invoices()            -> list[invoice_id]  (delivered)
  * deliver_invoice(invoice, org=None)      -> bool
  * register_cli(app)                        — `flask invoice-monthly`
"""

import calendar as _cal
import datetime as _dt
import logging
import secrets

from sqlalchemy import and_

from models import (
    db, Job, Org, Contract, PortalInvoice, PortalInvoiceLineItem,
    active_contract_for_org,
)

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
# Delivery — retryable
# ---------------------------------------------------------------------------
def deliver_invoice(invoice, org=None):
    """Push one local invoice to Stripe. Returns True once it is finalized in
    Stripe (``sent_at`` stamped). Never raises; the failure reason lands on
    ``invoice.delivery_error`` so the next run retries. Does not commit."""
    from billing_portal import push_portal_invoice_to_stripe

    if org is None:
        org = db.session.get(Org, invoice.org_id)
    if (invoice.total_cents or 0) <= 0:
        # Nothing to collect — an informational invoice counts as delivered.
        invoice.sent_at = invoice.sent_at or _dt.datetime.utcnow()
        return True
    try:
        sid = push_portal_invoice_to_stripe(org, invoice, list(invoice.line_items or []))
    except Exception as exc:  # pragma: no cover — push never raises by contract
        logger.exception("deliver_invoice: unexpected error for %s", invoice.id)
        invoice.delivery_error = str(exc)[:500]
        sid = None
    if sid:
        invoice.stripe_invoice_id = sid
    return bool(sid) and invoice.sent_at is not None


def retry_undelivered_invoices(limit=200):
    """Retry Stripe delivery for every open invoice that is not yet finalized
    in Stripe. Each invoice runs in its own savepoint. Returns the ids that
    were delivered this pass. Commits."""
    pending = (
        db.session.query(PortalInvoice)
        .filter(
            PortalInvoice.status == "open",
            PortalInvoice.sent_at.is_(None),
            PortalInvoice.total_cents > 0,
        )
        .order_by(PortalInvoice.created_at.asc())
        .limit(limit)
        .all()
    )
    delivered = []
    for inv in pending:
        try:
            with db.session.begin_nested():
                if deliver_invoice(inv):
                    delivered.append(inv.id)
        except Exception:  # pragma: no cover
            logger.exception("invoice delivery retry failed for %s", inv.id)
    if pending:
        db.session.commit()
    if delivered:
        logger.info("invoice delivery: %d retried invoice(s) now in Stripe", len(delivered))
    return delivered


# ---------------------------------------------------------------------------
# Line building
# ---------------------------------------------------------------------------
def _contract_lines(org, contract, org_jobs, period_start):
    """Lines for a contracted org. The base fee is added only when this
    invoice is the billing owner AND the (org, period) lock is acquired."""
    from billing_portal import base_fee_owner, claim_base_fee

    lines = []
    n = len(org_jobs)
    included = contract.included_pickups or 0
    per_pickup = contract.metered_per_pickup_cents or 0
    overage = max(0, n - included)
    base_cents = contract.monthly_base_cents or 0

    if base_cents > 0 and base_fee_owner(org) == "contract_invoice":
        if claim_base_fee(org.id, period_start, "contract_invoice"):
            lines.append(PortalInvoiceLineItem(
                kind="base_fee",
                description="Monthly base — {} plan".format(contract.tier.title()),
                quantity=1.0, unit_cents=base_cents, amount_cents=base_cents,
            ))
        else:
            logger.info("invoice: base fee for org=%s %s already billed — skipped",
                        org.id, period_start.strftime("%Y-%m"))

    if overage > 0:
        lines.append(PortalInvoiceLineItem(
            kind="overage",
            description="Pickups: {} ({} included, {} billed)".format(n, included, overage),
            quantity=float(overage), unit_cents=per_pickup,
            amount_cents=overage * per_pickup,
        ))
    elif n > 0:
        # Informational $0 line so the invoice shows usage within plan.
        lines.append(PortalInvoiceLineItem(
            kind="usage",
            description="Pickups: {} (all {} within plan)".format(n, included),
            quantity=float(n), unit_cents=0, amount_cents=0,
        ))
    return lines


def _job_lines(org_jobs, now):
    """No contract on file: one line per completed job at its own price."""
    lines = []
    for j in org_jobs:
        amount_cents = int(round((j.total_price or 0.0) * 100))
        lines.append(PortalInvoiceLineItem(
            kind="job", job_id=j.id,
            description="Pickup {}".format((j.completed_at or now).date().isoformat()),
            quantity=1.0, unit_cents=amount_cents, amount_cents=amount_cents,
        ))
    return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_monthly_invoices(month, year):
    """Create one invoice per org for the month and deliver it to Stripe.

    Returns: list of PortalInvoice ids CREATED this run (delivery retries of
    older invoices are logged, not returned).

    Math:
      subtotal_cents = contract base (if owned here) + overage, or the sum of
                       job prices when there is no contract
      tax_cents      = 0 (spec §9.3 keeps tax for v2)
      total_cents    = subtotal_cents
    """
    period_start, period_end = _month_range(month, year)
    now = _dt.datetime.utcnow()

    # 1. Deliver anything still owed to Stripe from earlier runs.
    retry_undelivered_invoices()

    # 2. Completed jobs in the period, grouped by org.
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
    by_org = {}
    for j in jobs:
        by_org.setdefault(j.org_id, []).append(j)

    # Orgs with a contract in force at period end owe the base fee even with
    # zero pickups.
    contracted_org_ids = {
        row[0] for row in
        db.session.query(Contract.org_id)
        .filter(Contract.effective_from <= period_end)
        .filter((Contract.effective_to.is_(None)) | (Contract.effective_to >= period_end))
        .all()
    }
    org_ids = list(dict.fromkeys(list(by_org.keys()) + sorted(contracted_org_ids)))

    created_ids = []
    for org_id in org_ids:
        org_jobs = by_org.get(org_id, [])
        try:
            with db.session.begin_nested():
                org = db.session.get(Org, org_id)
                if org is None:
                    continue

                # Idempotency: one invoice per (org, period).
                existing = (
                    db.session.query(PortalInvoice)
                    .filter(PortalInvoice.org_id == org_id,
                            PortalInvoice.period_start == period_start)
                    .first()
                )
                if existing is not None:
                    continue

                contract = active_contract_for_org(org_id, period_end)
                if contract:
                    line_items = _contract_lines(org, contract, org_jobs, period_start)
                else:
                    line_items = _job_lines(org_jobs, now)
                if not line_items:
                    continue  # nothing to bill this period

                subtotal_cents = sum(int(li.amount_cents or 0) for li in line_items)
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
                    sent_at=None,
                )
                invoice.line_items = line_items
                db.session.add(invoice)
                db.session.flush()

                # 3. Deliver now; on failure the row stays with sent_at NULL
                # and retry_undelivered_invoices() picks it up next run.
                if not deliver_invoice(invoice, org):
                    logger.warning(
                        "invoice %s for org=%s created but not delivered to Stripe yet (%s)",
                        invoice.number, org_id, invoice.delivery_error or "no Stripe customer/key",
                    )
                created_ids.append(invoice.id)
        except Exception:
            logger.exception("invoice generation failed for org %s — rolled back that org only", org_id)

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
