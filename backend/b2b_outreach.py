"""
B2B customer-acquisition outreach.

Sibling of operator_outreach.py — same compliant machinery, opposite side of the
marketplace. Where operator_outreach recruits HAULERS, this drives COMMERCIAL
CUSTOMERS to portal.goumuve.com: property managers, restaurants, retail, offices,
and construction — businesses that generate junk on a recurring basis and want
one dashboard + one consolidated monthly invoice instead of calling a hauler
every time.

Pipeline (daily): Google Places sourcing across B2B verticals -> light website
email scrape -> qualify -> CAN-SPAM-compliant drip (3 touches: day 0/+3/+7,
daily cap, unsubscribe + postal address) -> permanent suppression on
unsubscribe/bounce. Leads in models.B2BLead. DRY RUN until configured.

Legal guardrails (do NOT weaken): email only, no cold SMS (TCPA). CAN-SPAM:
postal address + working unsubscribe in every send. Templated personalization
(no hallucinated claims).
"""

import datetime as dt
import logging
import os
import re
import secrets
import time

import requests
from flask import Blueprint, request

import places_search

logger = logging.getLogger(__name__)

_DRIP_DAYS = [0, 3, 7]

# B2B verticals to source — businesses with recurring junk/cleanout needs.
_PLACES_QUERIES = [
    "property management company",
    "apartment complex",
    "condo association management",
    "real estate office",
    "estate sale company",
    "self storage facility",
    "assisted living facility",
    "senior living community",
    "general contractor",
    "office building",
    "restaurant",
    "retail store",
]
# A lead qualifies if it reads like a real business (not a hauler/competitor —
# those belong to the operator funnel — and not an obvious non-prospect).
_QUALIFY_KEYWORDS = (
    "property", "management", "apartment", "realty", "real estate", "restaurant",
    "grill", "cafe", "kitchen", "retail", "store", "shop", "market", "office",
    "construction", "builder", "contractor", "storage", "hotel", "plaza", "center",
    "estate", "sale", "senior", "assisted", "living", "condo", "association", "hoa",
    "homes", "residences", "village", "manor", "gardens", "towers", "communities",
)
# Exclude actual haulers (they're recruited, not sold to) + non-prospects.
_EXCLUDE_KEYWORDS = ("junk removal", "hauling", "dumpster", "we buy", "1-800")
# Palm Beach, Broward and Miami-Dade — the 9/26 caller was in 33146 and no
# business within 20 miles of her had ever been sourced.
_DEFAULT_ZIPS = [
    "33401", "33409", "33411", "33418", "33410", "33458", "33463", "33467", "33444", "33434",  # Palm Beach
    "33060", "33064", "33301", "33304", "33442", "33308", "33324", "33326", "33071", "33021", "33024",  # Broward
    "33146", "33143", "33156", "33176", "33186", "33130", "33137", "33160", "33180", "33012", "33033",  # Miami-Dade
]
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_EMAIL_BLOCK = ("example.", "sentry.", "wixpress.", "godaddy.", "@2x", ".png", ".jpg")


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def _cfg():
    return {
        "places_key": os.environ.get("GOOGLE_PLACES_API_KEY", "").strip(),
        # Separate enable flag so B2B and hauler outreach go live independently.
        "send_enabled": os.environ.get("B2B_OUTREACH_SEND_ENABLED", "").lower() == "true",
        # Own sender identity (protect deliverability); falls back to the shared
        # recruiting sender, then nothing.
        "from": (os.environ.get("B2B_OUTREACH_FROM") or os.environ.get("OUTREACH_FROM") or "").strip(),
        "postal": os.environ.get("OUTREACH_POSTAL_ADDRESS", "").strip(),
        "daily_cap": _int_env("B2B_OUTREACH_DAILY_CAP", 25),
        "zips": [z.strip() for z in os.environ.get("B2B_OUTREACH_ZIPS", "").split(",") if z.strip()] or _DEFAULT_ZIPS,
        "report_to": os.environ.get("OUTREACH_REPORT_TO", "") or os.environ.get("ADMIN_EMAIL", ""),
        "base_url": (os.environ.get("PUBLIC_BASE_URL", "https://junkos-backend.onrender.com")).rstrip("/"),
        "signup_url": os.environ.get("B2B_SIGNUP_URL", "https://portal.goumuve.com/signup"),
    }


def _int_env(name, default):
    try:
        return max(0, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


def _can_send(cfg):
    return bool(cfg["send_enabled"] and cfg["from"] and cfg["postal"])


# --------------------------------------------------------------------------- #
# 1. Source — Google Places
# --------------------------------------------------------------------------- #
def source_from_places(cfg, db, B2BLead, max_new=40):
    if not cfg["places_key"]:
        return 0
    new_count = 0
    seen_ids = {pid for (pid,) in db.session.query(B2BLead.place_id).all() if pid}
    diag = {}
    for zip_code in cfg["zips"]:
        for query in _PLACES_QUERIES:
            if new_count >= max_new:
                break
            places = places_search.text_search(
                cfg["places_key"], "{} in {}".format(query, zip_code), diag=diag
            )
            if diag.get("status") or diag.get("new_api_status"):
                cfg["_places_status"] = diag.get("status") or diag.get("new_api_status")
                cfg["_places_error"] = diag.get("error") or diag.get("new_api_error")
            for res in places:
                pid = res["place_id"]
                if not pid or pid in seen_ids:
                    continue
                name_lo = (res["name"] or "").lower()
                if any(x in name_lo for x in _EXCLUDE_KEYWORDS):
                    continue  # a hauler/competitor — not a customer
                seen_ids.add(pid)
                website, phone = res["website"], res["phone"]
                if res.get("_needs_details"):
                    website, phone = _place_details(cfg, pid)
                addr = res["address"]
                db.session.add(B2BLead(
                    business_name=res["name"],
                    place_id=pid,
                    source="places",
                    category=query.replace(" ", "_"),
                    zip=zip_code,
                    city=addr.split(",")[1].strip() if "," in addr else None,
                    website=website,
                    phone=phone,
                    status="new",
                ))
                new_count += 1
                if new_count >= max_new:
                    break
            time.sleep(0.2)
    db.session.commit()
    return new_count


def _place_details(cfg, place_id):
    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id, "fields": "website,formatted_phone_number", "key": cfg["places_key"]},
            timeout=15,
        )
        d = (r.json() or {}).get("result", {})
        return d.get("website"), d.get("formatted_phone_number")
    except Exception:
        return None, None


# --------------------------------------------------------------------------- #
# 2. Enrich — scrape a contact email from the business website
# --------------------------------------------------------------------------- #
def enrich_emails(db, B2BLead, limit=40):
    leads = (
        db.session.query(B2BLead)
        .filter(B2BLead.email.is_(None), B2BLead.website.isnot(None), B2BLead.status == "new")
        .limit(limit)
        .all()
    )
    for lead in leads:
        email = _scrape_email(lead.website)
        if email:
            lead.email = email
        time.sleep(0.3)
    db.session.commit()
    return sum(1 for l in leads if l.email)


_OBFUSCATED_RE = re.compile(r"([a-zA-Z0-9._%+\-]+)\s*[\[(]\s*at\s*[\])]\s*([a-zA-Z0-9.\-]+)\s*[\[(]\s*dot\s*[\])]\s*([a-zA-Z]{2,})", re.I)
_PREFER = ("info@", "office@", "hello@", "contact@", "leasing@", "manager@", "management@", "admin@")


def _scrape_email(website):
    """A contact address from the business's own site.

    Looks at the pages that actually carry one (contact, about, team), reads
    mailto: links and "name [at] domain [dot] com" as well as plain text, and
    prefers a role address (info@, leasing@) over the webmaster's.
    """
    base = website.rstrip("/")
    found = []
    for path in ("", "/contact", "/contact-us", "/contact-us/", "/contact.html", "/about", "/about-us",
                 "/team", "/our-team", "/leadership", "/management"):
        try:
            r = requests.get(base + path, timeout=10, allow_redirects=True,
                             headers={"User-Agent": "UmuveBusinessBot/1.0 (+https://goumuve.com)"})
            if r.status_code != 200 or "text/html" not in (r.headers.get("content-type") or ""):
                continue
            text = r.text
            for m in re.findall(r"mailto:([^\"'?>\s]+)", text, re.I):
                found.append(m)
            found.extend(_EMAIL_RE.findall(text))
            for user, dom, tld in _OBFUSCATED_RE.findall(text):
                found.append("{}@{}.{}".format(user, dom, tld))
        except Exception:
            continue
        if found:
            break
    clean = []
    for m in found:
        lo = m.strip().strip(".").lower()
        if any(b in lo for b in _EMAIL_BLOCK) or lo.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
            continue
        if lo.split("@")[0] in ("noreply", "no-reply", "donotreply", "privacy", "abuse", "webmaster", "postmaster"):
            continue
        if lo not in clean:
            clean.append(lo)
    if not clean:
        return None
    for pref in _PREFER:
        for e in clean:
            if e.startswith(pref):
                return e[:255]
    return clean[0][:255]


# --------------------------------------------------------------------------- #
# 3. Qualify
# --------------------------------------------------------------------------- #
def qualify(db, B2BLead):
    leads = db.session.query(B2BLead).filter(B2BLead.status == "new").all()
    qn = 0
    for lead in leads:
        if not lead.email:
            continue
        hay = " ".join(filter(None, [lead.business_name, lead.category])).lower()
        if any(x in hay for x in _EXCLUDE_KEYWORDS):
            lead.status = "skipped"
        elif any(k in hay for k in _QUALIFY_KEYWORDS):
            lead.status = "qualified"
            qn += 1
        else:
            lead.status = "skipped"
    db.session.commit()
    return qn


# --------------------------------------------------------------------------- #
# 4. Outreach — compliant drip
# --------------------------------------------------------------------------- #
# What each kind of business actually pays a hauler for. The pitch leads with
# that instead of a generic "consolidated billing".
_ANGLES = {
    "property_management_company": ("unit turnovers, evictions and left-behinds",
                                    "a turnover cleared the same day or next day, so the unit is back on the market"),
    "apartment_complex": ("move-outs, evictions and bulk items left by the dumpster",
                          "a move-out cleared the same day or next day, and no more bulk pile by the compactor"),
    "condo_association_management": ("bulk-item violations and move-out debris",
                                     "a violation cleared before the next board meeting"),
    "real_estate_office": ("pre-listing cleanouts and estate clearouts",
                           "a house emptied and broom-clean before the photographer shows up"),
    "estate_sale_company": ("post-sale clearouts",
                            "everything that didn't sell gone the day after the sale, donated first where we can"),
    "self_storage_facility": ("abandoned-unit and auction cleanouts",
                              "a unit emptied and re-rentable the same day"),
    "assisted_living_facility": ("move-out and downsizing cleanouts",
                                 "a resident's room cleared carefully and quickly, family items set aside"),
    "senior_living_community": ("move-out and downsizing cleanouts",
                                "a residence cleared carefully and quickly, family items set aside"),
    "general_contractor": ("debris between phases and final cleans",
                           "debris gone between phases without tying up your crew or renting a dumpster"),
}
_DEFAULT_ANGLE = ("junk removal and cleanouts", "a pickup booked in a minute and cleared the same or next day")


def _angle(lead):
    return _ANGLES.get((lead.category or "").lower(), _DEFAULT_ANGLE)


def _subject(lead, stage):
    name = lead.business_name or "your business"
    need, _ = _angle(lead)
    return [
        "{} for {} — priced up front".format(need.split(",")[0].capitalize(), name),
        "{}: next-day pickups, one monthly invoice".format(name),
        "Last note — {} for {}".format(need.split(",")[0], name),
    ][min(stage, 2)]


def _body_html(cfg, lead, stage):
    name = lead.business_name or "there"
    unsub = "{}/api/b2b-outreach/unsubscribe?token={}".format(cfg["base_url"], lead.unsubscribe_token)
    need, outcome = _angle(lead)
    intro = [
        "I run business accounts at Umuve, a junk removal service across Palm Beach, Broward "
        "and Miami-Dade. We handle {} for companies like {}: {}. Every job is priced before "
        "anyone shows up, and you get one invoice a month instead of receipts.".format(need, name, outcome),
        "Following up in case it got buried. For {}, Umuve means {}, priced up front, "
        "one monthly invoice.".format(name, outcome),
        "Last note from me. If {} isn't a headache for {} right now, no worries at all — "
        "keep this for the day it is.".format(need, name),
    ][min(stage, 2)]
    return """\
<div style="font-family:Arial,sans-serif;font-size:15px;color:#1a1a1a;line-height:1.6;max-width:560px">
  <p>Hi {name},</p>
  <p>{intro}</p>
  <ul>
    <li><b>Priced before we arrive</b> — by the item or the truckload, no on-site surprises.</li>
    <li><b>Same-day or next-day</b> pickups, seven days a week.</li>
    <li><b>One invoice a month</b> across every property, or pay per job.</li>
    <li>Insured crews; we donate and recycle first.</li>
  </ul>
  <p><a href="{signup}" style="background:#C52222;color:#fff;text-decoration:none;padding:10px 18px;border-radius:6px;font-weight:bold;display:inline-block">Set up your account</a></p>
  <p style="color:#555">Reply with a property and what needs to go and I'll send a price today, or call the desk at (561) 782-4350.</p>
  <p style="color:#777;font-size:12px;border-top:1px solid #eee;padding-top:12px;margin-top:20px">
    Umuve &middot; {postal}<br>
    You received this because {name} is listed as a business in our service area.
    <a href="{unsub}">Unsubscribe</a> and we won't email you again.
  </p>
</div>""".format(name=name, intro=intro, signup=cfg["signup_url"],
                 postal=cfg["postal"] or "[postal address not set]", unsub=unsub)


def _due_leads(db, B2BLead, cap):
    now = dt.datetime.utcnow()
    candidates = (
        db.session.query(B2BLead)
        .filter(B2BLead.email.isnot(None),
                B2BLead.status.in_(["qualified", "contacted"]),
                B2BLead.drip_stage < len(_DRIP_DAYS))
        .order_by(B2BLead.drip_stage.asc(), B2BLead.created_at.asc())
        .all()
    )
    due = []
    for lead in candidates:
        if lead.drip_stage == 0:
            due.append(lead)
        else:
            gap_needed = _DRIP_DAYS[lead.drip_stage]
            last = lead.last_contacted_at or lead.created_at
            if last and (now - last).days >= gap_needed:
                due.append(lead)
        if len(due) >= cap:
            break
    return due


def run_b2b_outreach_cycle(app, force_dry=False):
    """Daily entrypoint. Never raises — logs + returns a report dict.
    force_dry=True sources/qualifies/drafts but sends nothing (safe preview)."""
    with app.app_context():
        from models import db, B2BLead
        from notifications import send_email

        cfg = _cfg()
        can_send = _can_send(cfg) and not force_dry
        report = {"sourced": 0, "enriched": 0, "qualified": 0, "sent": 0, "dry_run": not can_send}
        try:
            report["sourced"] = source_from_places(cfg, db, B2BLead, max_new=cfg["daily_cap"] * 2)
            report["enriched"] = enrich_emails(db, B2BLead, limit=cfg["daily_cap"] * 2)
            report["qualified"] = qualify(db, B2BLead)

            for lead in _due_leads(db, B2BLead, cfg["daily_cap"]):
                if not lead.unsubscribe_token:
                    lead.unsubscribe_token = secrets.token_urlsafe(24)
                if can_send:
                    send_email(lead.email, _subject(lead, lead.drip_stage),
                               _body_html(cfg, lead, lead.drip_stage),
                               from_override=cfg["from"] or None)
                    lead.drip_stage += 1
                    lead.last_contacted_at = dt.datetime.utcnow()
                    lead.status = "contacted"
                    report["sent"] += 1
            db.session.commit()
        except Exception:
            logger.exception("b2b outreach cycle failed")
            db.session.rollback()

        _send_report(cfg, report, send_email)
        logger.info("b2b outreach: %s", report)
        return report


def _send_report(cfg, report, send_email):
    if not cfg["report_to"]:
        return
    mode = "DRY RUN (sending disabled)" if report["dry_run"] else "live"
    missing = []
    if not cfg["places_key"]:
        missing.append("GOOGLE_PLACES_API_KEY")
    if not cfg["from"]:
        missing.append("B2B_OUTREACH_FROM (or OUTREACH_FROM)")
    if not cfg["postal"]:
        missing.append("OUTREACH_POSTAL_ADDRESS")
    if not cfg["send_enabled"]:
        missing.append("B2B_OUTREACH_SEND_ENABLED=true")
    missing_html = ("<p style='color:#C52222'><b>To go live, set:</b> " + ", ".join(missing) + "</p>") if missing else ""
    html = """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#1a1a1a">
  <h2>B2B customer outreach — daily run ({mode})</h2>
  <ul>
    <li>New businesses sourced: <b>{sourced}</b></li>
    <li>Emails found: <b>{enriched}</b></li>
    <li>Qualified: <b>{qualified}</b></li>
    <li>Emails sent today: <b>{sent}</b></li>
  </ul>
  {missing}
</div>""".format(mode=mode, missing=missing_html, **{k: report[k] for k in ("sourced", "enriched", "qualified", "sent")})
    try:
        send_email(cfg["report_to"], "Umuve B2B outreach — daily report", html)
    except Exception:
        logger.warning("b2b outreach report email failed")


# --------------------------------------------------------------------------- #
# Unsubscribe (public, one-click — CAN-SPAM)
# --------------------------------------------------------------------------- #
b2b_outreach_bp = Blueprint("b2b_outreach", __name__, url_prefix="/api/b2b-outreach")


@b2b_outreach_bp.route("/unsubscribe", methods=["GET"])
def unsubscribe():
    from flask import Response
    from models import db, B2BLead

    token = (request.args.get("token") or "").strip()
    page = ("<html><body style='font-family:Arial,sans-serif;text-align:center;"
            "padding:60px'><h2>{}</h2><p>{}</p></body></html>")
    if not token:
        return Response(page.format("Invalid link", "Missing token."), mimetype="text/html", status=400)
    lead = db.session.query(B2BLead).filter_by(unsubscribe_token=token).first()
    if lead:
        lead.status = "unsubscribed"
        db.session.commit()
    return Response(
        page.format("You're unsubscribed", "You won't receive any more emails from Umuve. Thanks."),
        mimetype="text/html",
    )
