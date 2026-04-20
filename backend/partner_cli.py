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


# ---------------------------------------------------------------------------
# Spec 07 §9 v1 commands — multi-source scrapers + pipeline driver.
# ---------------------------------------------------------------------------
@partner_cli.command("scrape-all")
@click.option("--city", default="Miami", show_default=True)
@click.option("--limit", default=25, show_default=True, type=int,
              help="Max listings per source.")
def scrape_all_cmd(city, limit):
    """Run every configured scraper (craigslist, fb_marketplace, thumbtack,
    nextdoor DEFERRED, indeed) and print per-source counts. Does NOT ingest —
    pair with `partner scrape` for Craigslist, or extend this command to
    POST into the ingest endpoint once the new scrapers mature."""
    from partner_scrapers import run_all_scrapers

    rows = run_all_scrapers(city=city, limit_per_source=limit)
    counts = {}
    for r in rows:
        counts[r.get("source", "?")] = counts.get(r.get("source", "?"), 0) + 1
    click.echo("Found {} total listings across sources:".format(len(rows)))
    for src in ("craigslist", "fb_marketplace", "thumbtack", "nextdoor", "indeed"):
        click.echo("  {:<18} {}".format(src, counts.get(src, 0)))


@partner_cli.command("pipeline-tick")
@click.option("--lead-id", required=True)
def pipeline_tick_cmd(lead_id):
    """Advance one lead by one step of the LangGraph pipeline."""
    from partner_langgraph import run_lead_pipeline
    import json as _json

    result = run_lead_pipeline(lead_id)
    click.echo(_json.dumps(result, default=str, indent=2))


@partner_cli.command("pipeline-tick-all")
def pipeline_tick_all_cmd():
    """Advance every eligible lead once."""
    from partner_langgraph import run_lead_pipeline_all
    counters = run_lead_pipeline_all()
    click.echo("advanced={advanced} skipped={skipped} errors={errors}".format(**counters))
