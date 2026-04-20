"""
Partner Acquisition Agent — Flask CLI commands (spec 07 §9 MVP).

Exposes a click.Group named `partner_cli` that the orchestrator will bolt
onto `server.py` under `@app.cli.group("partner")` after the parallel-agent
merge. Example usage once wired:

    flask partner scrape miami
    flask partner list-leads --state=NEW
    flask partner outreach <lead_id>
"""

import logging

import click

logger = logging.getLogger(__name__)


@click.group(name="partner")
def partner_cli():
    """Partner (driver) acquisition agent — MVP ops commands."""


@partner_cli.command("scrape")
@click.argument("metro", default="miami")
@click.option("--subdomain", default="miami", help="Craigslist subdomain (e.g. miami, southflorida, tampa)")
@click.option("--max-per-query", default=20, show_default=True, type=int)
def scrape_cmd(metro, subdomain, max_per_query):
    """Run Craigslist scraper for METRO (default: miami)."""
    from partner_scraper import scrape_craigslist

    summary = scrape_craigslist(
        metro=metro,
        subdomain=subdomain,
        max_listings_per_query=max_per_query,
    )
    click.echo(
        "found={listings_found} ingested={ingested} deduped={deduped} errors={errors}".format(**summary)
    )


@partner_cli.command("list-leads")
@click.option("--state", default=None)
@click.option("--metro", default=None)
@click.option("--limit", default=25, show_default=True, type=int)
def list_leads_cmd(state, metro, limit):
    """Print recent driver leads in a compact table."""
    # Flask's CLI provides app-context; import locally so this module stays
    # importable outside the app context (e.g., in tests).
    from models import db
    from partner_models import DriverLead

    q = db.session.query(DriverLead)
    if state:
        q = q.filter(DriverLead.state == state)
    if metro:
        q = q.filter(DriverLead.metro == metro.lower())
    rows = q.order_by(DriverLead.created_at.desc()).limit(limit).all()

    click.echo("{:<10} {:<10} {:<20} {:<16} {}".format("STATE", "METRO", "PHONE", "NAME", "ID"))
    click.echo("-" * 90)
    for r in rows:
        click.echo("{:<10} {:<10} {:<20} {:<16} {}".format(
            r.state[:10],
            (r.metro or "-")[:10],
            (r.phone_e164 or "-")[:20],
            (r.name_guess or "-")[:16],
            r.id,
        ))
    click.echo("\n{} leads".format(len(rows)))


@partner_cli.command("outreach")
@click.argument("lead_id")
def outreach_cmd(lead_id):
    """Trigger an outreach SMS for LEAD_ID via the local route."""
    import os
    import requests

    base = os.environ.get("PARTNER_BASE_URL", "http://localhost:5000")
    token = os.environ.get("PARTNER_SERVICE_TOKEN", "")
    if not token:
        click.echo("PARTNER_SERVICE_TOKEN not set", err=True)
        raise click.Abort()

    url = "{}/partner/v1/internal/leads/{}/outreach".format(base, lead_id)
    resp = requests.post(url, headers={"X-Service-Token": token}, timeout=10)
    click.echo("{} {}".format(resp.status_code, resp.text))
