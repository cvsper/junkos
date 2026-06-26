"""Automated daily operator/hauler recruiting outreach.

Pipeline (runs daily from scheduler.py):
  1. SOURCE   new hauling businesses from Google Places (target ZIPs) +
              light website scrape for a contact email.
  2. QUALIFY  keep real haulers (junk/hauling/moving/dumpster/debris).
  3. OUTREACH compliant B2B email drip (3 touches: day 0, +3, +7), throttled
              to a daily cap, from a recruiting identity, with a one-click
              unsubscribe + physical postal address (CAN-SPAM).
  4. SUPPRESS unsubscribes/replies/bounces are never contacted again.
  5. REPORT   email a daily digest to the operator + log.

SAFETY / LEGALITY (do not weaken):
  * Email only. NO cold SMS (TCPA). SMS would require prior opt-in.
  * Sending is OFF until the compliance config exists. Required env to send:
        OUTREACH_SEND_ENABLED=true
        OUTREACH_FROM="Umuve Partners <partners@goumuve.com>"
        OUTREACH_POSTAL_ADDRESS="Umuve, 123 Main St, West Palm Beach, FL 33401"
        GOOGLE_PLACES_API_KEY=...        (needed to source leads)
    Without these the daily run is a DRY RUN: it sources, qualifies, drafts,
    and reports what it *would* send — but sends nothing. This is deliberate:
    you cannot legally cold-email without a postal address + working opt-out.
  Optional tuning:
        OUTREACH_DAILY_CAP (default 25)  — protects domain reputation; ramp up
        OUTREACH_ZIPS      (default PBC/Broward set, comma-separated)
        OUTREACH_REPORT_TO (default ADMIN_EMAIL)
        PUBLIC_BASE_URL    (for the unsubscribe link; default prod backend)
"""

import logging
import os
import re
import secrets
import time

import requests
from flask import Blueprint, request

logger = logging.getLogger(__name__)

# Drip cadence: days since last touch before the next one; stop after len().
_DRIP_DAYS = [0, 3, 7]
_QUALIFY_KEYWORDS = (
    "junk", "haul", "hauling", "dumpster", "debris", "moving", "movers",
    "cleanout", "clean out", "demolition", "removal", "trash", "rubbish",
)
_DEFAULT_ZIPS = ["33401", "33409", "33411", "33060", "33064", "33301", "33304", "33442"]
_PLACES_QUERIES = [
    "junk removal", "hauling service", "dumpster rental",
    "moving company", "debris removal",
]
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# Skip role/vendor addresses that aren't a real inbox or that we shouldn't hit.
_EMAIL_BLOCK = ("example.", "sentry.", "wixpress.", "godaddy.", "@2x", ".png", ".jpg")


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def _cfg():
    return {
        "places_key": os.environ.get("GOOGLE_PLACES_API_KEY", "").strip(),
        "send_enabled": os.environ.get("OUTREACH_SEND_ENABLED", "").lower() == "true",
        "from": os.environ.get("OUTREACH_FROM", "").strip(),
        "postal": os.environ.get("OUTREACH_POSTAL_ADDRESS", "").strip(),
        "daily_cap": _int_env("OUTREACH_DAILY_CAP", 25),
        "zips": [z.strip() for z in os.environ.get("OUTREACH_ZIPS", "").split(",") if z.strip()] or _DEFAULT_ZIPS,
        "report_to": os.environ.get("OUTREACH_REPORT_TO", "") or os.environ.get("ADMIN_EMAIL", ""),
        "base_url": (os.environ.get("PUBLIC_BASE_URL", "https://junkos-backend.onrender.com")).rstrip("/"),
        "signup_url": os.environ.get("OPERATOR_SIGNUP_URL", "https://goumuve.com/operators"),
    }


def _int_env(name, default):
    try:
        return max(0, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


def _can_send(cfg):
    """Compliant + configured to actually send. Postal address + From are legal
    prerequisites; without them we never send."""
    return bool(cfg["send_enabled"] and cfg["from"] and cfg["postal"])


# --------------------------------------------------------------------------- #
# 1. Source — Google Places
# --------------------------------------------------------------------------- #
def source_from_places(cfg, db, OperatorLead, max_new=40):
    """Discover hauling businesses via Google Places Text Search + Details.
    Upserts new leads (dedup on place_id). Returns count of new leads."""
    if not cfg["places_key"]:
        return 0
    new_count = 0
    seen_ids = {pid for (pid,) in db.session.query(OperatorLead.place_id).all() if pid}
    for zip_code in cfg["zips"]:
        for query in _PLACES_QUERIES:
            if new_count >= max_new:
                break
            try:
                r = requests.get(
                    "https://maps.googleapis.com/maps/api/place/textsearch/json",
                    params={"query": "{} in {}".format(query, zip_code), "key": cfg["places_key"]},
                    timeout=15,
                )
                results = (r.json() or {}).get("results", [])
            except Exception:
                logger.warning("places search failed for %s/%s", query, zip_code)
                continue
            for res in results:
                pid = res.get("place_id")
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                website, phone = _place_details(cfg, pid)
                lead = OperatorLead(
                    business_name=res.get("name"),
                    place_id=pid,
                    source="places",
                    category=query,
                    zip=zip_code,
                    city=(res.get("formatted_address") or "").split(",")[1].strip()
                    if "," in (res.get("formatted_address") or "") else None,
                    website=website,
                    phone=phone,
                    status="new",
                )
                db.session.add(lead)
                new_count += 1
                if new_count >= max_new:
                    break
            time.sleep(0.2)  # be polite to the API
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
def enrich_emails(db, OperatorLead, limit=40):
    """For new leads with a website but no email, fetch the homepage + a likely
    contact page and extract a public business email. Bounded + polite."""
    leads = (
        db.session.query(OperatorLead)
        .filter(OperatorLead.email.is_(None),
                OperatorLead.website.isnot(None),
                OperatorLead.status == "new")
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


def _scrape_email(website):
    base = website.rstrip("/")
    for path in ("", "/contact", "/contact-us", "/about"):
        try:
            r = requests.get(
                base + path,
                timeout=10,
                headers={"User-Agent": "UmuvePartnersBot/1.0 (+https://goumuve.com)"},
            )
            if r.status_code != 200:
                continue
            for m in _EMAIL_RE.findall(r.text):
                lo = m.lower()
                if not any(b in lo for b in _EMAIL_BLOCK):
                    return m[:255]
        except Exception:
            continue
    return None


# --------------------------------------------------------------------------- #
# 3. Qualify
# --------------------------------------------------------------------------- #
def qualify(db, OperatorLead):
    """Mark new+emailed leads as qualified if they look like a real hauler."""
    leads = db.session.query(OperatorLead).filter(OperatorLead.status == "new").all()
    qn = 0
    for lead in leads:
        if not lead.email:
            continue  # leave as 'new'; may get an email on a later run
        hay = " ".join(filter(None, [lead.business_name, lead.category])).lower()
        if any(k in hay for k in _QUALIFY_KEYWORDS):
            lead.status = "qualified"
            qn += 1
        else:
            lead.status = "skipped"
    db.session.commit()
    return qn


# --------------------------------------------------------------------------- #
# 4. Outreach — compliant drip
# --------------------------------------------------------------------------- #
def _subject(lead, stage):
    city = lead.city or "your area"
    return [
        "Get paid to haul in {} — jobs sent to your phone".format(city),
        "{}: more hauling jobs, no marketing".format(lead.business_name or "Quick question"),
        "Last note — free hauling jobs in {}".format(city),
    ][min(stage, 2)]


def _body_html(cfg, lead, stage):
    name = lead.business_name or "there"
    city = lead.city or "South Florida"
    unsub = "{}/api/outreach/unsubscribe?token={}".format(cfg["base_url"], lead.unsubscribe_token)
    intro = [
        "I run partner growth at Umuve — we send junk-removal jobs to local haulers in {}.".format(city),
        "Following up in case this got buried — Umuve sends paid hauling jobs to crews in {}.".format(city),
        "Last note from me. If hauling more jobs in {} isn't a fit right now, no worries.".format(city),
    ][min(stage, 2)]
    return """\
<div style="font-family:Arial,sans-serif;font-size:15px;color:#1a1a1a;line-height:1.6;max-width:560px">
  <p>Hi {name},</p>
  <p>{intro}</p>
  <p>How it works for you:</p>
  <ul>
    <li>We bring the customer and set the price up front — you just haul.</li>
    <li>You keep the large majority of every job; same-day payouts available.</li>
    <li>Accept the jobs you want, when you want. No marketing, no quoting.</li>
  </ul>
  <p><a href="{signup}" style="background:#C52222;color:#fff;text-decoration:none;padding:10px 18px;border-radius:6px;font-weight:bold;display:inline-block">See how it works &amp; sign up</a></p>
  <p style="color:#555">Reply with a number and I'll text you the details, or just tap above.</p>
  <p style="color:#777;font-size:12px;border-top:1px solid #eee;padding-top:12px;margin-top:20px">
    Umuve &middot; {postal}<br>
    You received this because {name} is listed as a hauling business in {city}.
    <a href="{unsub}">Unsubscribe</a> and we won't email you again.
  </p>
</div>""".format(name=name, intro=intro, signup=cfg["signup_url"], postal=cfg["postal"] or "[postal address not set]", city=city, unsub=unsub)


def _due_leads(db, OperatorLead, cap):
    """Qualified/contacted leads with an email, not suppressed, due for the next
    drip touch. Returns up to `cap` leads."""
    import datetime as dt
    now = dt.datetime.utcnow()
    candidates = (
        db.session.query(OperatorLead)
        .filter(OperatorLead.email.isnot(None),
                OperatorLead.status.in_(["qualified", "contacted"]),
                OperatorLead.drip_stage < len(_DRIP_DAYS))
        .order_by(OperatorLead.drip_stage.asc(), OperatorLead.created_at.asc())
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


def run_outreach_cycle(app, force_dry=False):
    """Daily entrypoint. Never raises — logs + returns a report dict.

    force_dry=True sources/qualifies/drafts but sends nothing (safe preview),
    regardless of config — used by the admin "run now / preview" trigger.
    """
    with app.app_context():
        from models import db, OperatorLead
        from notifications import send_email

        cfg = _cfg()
        can_send = _can_send(cfg) and not force_dry
        report = {"sourced": 0, "enriched": 0, "qualified": 0, "sent": 0,
                  "dry_run": not can_send}
        try:
            report["sourced"] = source_from_places(cfg, db, OperatorLead, max_new=cfg["daily_cap"] * 2)
            report["enriched"] = enrich_emails(db, OperatorLead, limit=cfg["daily_cap"] * 2)
            report["qualified"] = qualify(db, OperatorLead)

            due = _due_leads(db, OperatorLead, cfg["daily_cap"])
            for lead in due:
                if not lead.unsubscribe_token:
                    lead.unsubscribe_token = secrets.token_urlsafe(24)
                if can_send:
                    subject = _subject(lead, lead.drip_stage)
                    html = _body_html(cfg, lead, lead.drip_stage)
                    # Send from the recruiting identity (OUTREACH_FROM), NOT the
                    # customer transactional sender — keeps deliverability separate.
                    send_email(lead.email, subject, html, from_override=cfg["from"] or None)
                    import datetime as dt
                    lead.drip_stage += 1
                    lead.last_contacted_at = dt.datetime.utcnow()
                    lead.status = "contacted"
                    report["sent"] += 1
            db.session.commit()
        except Exception:
            logger.exception("operator outreach cycle failed")
            db.session.rollback()

        _send_report(cfg, report, send_email)
        logger.info("operator outreach: %s", report)
        return report


def _send_report(cfg, report, send_email):
    if not cfg["report_to"]:
        return
    mode = "DRY RUN (sending disabled)" if report["dry_run"] else "live"
    missing = []
    if not cfg["places_key"]:
        missing.append("GOOGLE_PLACES_API_KEY (no leads will be sourced)")
    if not cfg["from"]:
        missing.append("OUTREACH_FROM")
    if not cfg["postal"]:
        missing.append("OUTREACH_POSTAL_ADDRESS")
    if not cfg["send_enabled"]:
        missing.append("OUTREACH_SEND_ENABLED=true")
    missing_html = ("<p style='color:#C52222'><b>To go live, set:</b> "
                    + ", ".join(missing) + "</p>") if missing else ""
    html = """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#1a1a1a">
  <h2>Operator outreach — daily run ({mode})</h2>
  <ul>
    <li>New leads sourced: <b>{sourced}</b></li>
    <li>Emails found (enriched): <b>{enriched}</b></li>
    <li>Qualified haulers: <b>{qualified}</b></li>
    <li>Emails sent today: <b>{sent}</b></li>
  </ul>
  {missing}
</div>""".format(mode=mode, missing=missing_html, **{k: report[k] for k in ("sourced", "enriched", "qualified", "sent")})
    try:
        send_email(cfg["report_to"], "Umuve operator outreach — daily report", html)
    except Exception:
        logger.warning("outreach report email failed")


# --------------------------------------------------------------------------- #
# Unsubscribe (public, one-click — CAN-SPAM)
# --------------------------------------------------------------------------- #
outreach_bp = Blueprint("outreach", __name__, url_prefix="/api/outreach")


@outreach_bp.route("/unsubscribe", methods=["GET"])
def unsubscribe():
    from flask import Response
    from models import db, OperatorLead

    token = (request.args.get("token") or "").strip()
    page = ("<html><body style='font-family:Arial,sans-serif;text-align:center;"
            "padding:60px'><h2>{}</h2><p>{}</p></body></html>")
    if not token:
        return Response(page.format("Invalid link", "Missing token."), mimetype="text/html", status=400)
    lead = db.session.query(OperatorLead).filter_by(unsubscribe_token=token).first()
    if lead:
        lead.status = "unsubscribed"
        db.session.commit()
    # Always confirm (don't leak whether the token existed).
    return Response(
        page.format("You're unsubscribed", "You won't receive any more emails from Umuve. Thanks."),
        mimetype="text/html",
    )


# --------------------------------------------------------------------------- #
# Inbound reply capture (email-provider webhook)
#
# When a recruited hauler REPLIES to an outreach email, the provider (Resend
# Inbound / SendGrid Parse / Postmark / generic) POSTs here. We match the
# sender to a lead, flip it to "replied" (which auto-stops the drip — the
# sender loop only contacts qualified/contacted), stash the message, and alert
# the admin so a human follows up fast. A real interested hauler is the most
# valuable thing outreach produces; it must never sit unseen in an inbox.
# --------------------------------------------------------------------------- #
def _extract_inbound(req):
    """Best-effort (from_email, subject, text) from common webhook shapes."""
    data = {}
    try:
        data = req.get_json(silent=True) or {}
    except Exception:
        data = {}
    form = req.form or {}

    def first(*vals):
        for v in vals:
            if v:
                return v
        return ""

    # Resend inbound nests under data; others are flat.
    d = data.get("data") if isinstance(data.get("data"), dict) else data

    frm = first(
        _addr(d.get("from")), _addr(data.get("from")),
        _addr(d.get("sender")), form.get("from"), form.get("sender"),
        _addr((d.get("FromFull") or {}).get("Email")), d.get("From"),
    )
    subject = first(d.get("subject"), data.get("subject"), form.get("subject"), d.get("Subject"), "")
    text = first(
        d.get("text"), d.get("text_body"), d.get("TextBody"), d.get("plain"),
        data.get("text"), form.get("text"), form.get("plain"), d.get("html"), "",
    )
    m = _EMAIL_RE.search(frm or "")
    email = (m.group(0).lower() if m else "")
    return email, (subject or "")[:200], (text or "")[:4000]


def _addr(v):
    """Pull an email string out of str | {'address'|'email': ...} | [..]."""
    if not v:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("address") or v.get("email") or ""
    if isinstance(v, (list, tuple)) and v:
        return _addr(v[0])
    return ""


_AUTO_SUBJECT = re.compile(
    r"out of office|automatic reply|auto[- ]?reply|delivery (status|failure)|"
    r"undeliverable|mail delivery|returned mail|read receipt", re.I)


@outreach_bp.route("/inbound", methods=["POST"])
def inbound_reply():
    """Provider webhook for inbound replies. Always returns 200 (so the provider
    doesn't retry-storm). Optional shared secret via OUTREACH_INBOUND_SECRET."""
    from models import db, OperatorLead, B2BLead, User, Notification, generate_uuid

    secret = os.environ.get("OUTREACH_INBOUND_SECRET", "").strip()
    if secret:
        got = (request.args.get("secret") or request.headers.get("X-Webhook-Secret") or "").strip()
        if got != secret:
            return {"ok": False, "error": "forbidden"}, 403

    email, subject, text = _extract_inbound(request)
    if not email:
        return {"ok": True, "matched": False, "reason": "no sender email"}, 200

    # Match against either funnel — hauler recruiting (OperatorLead) or B2B
    # customer acquisition (B2BLead). Both share the lead shape the helpers use.
    lead = (
        db.session.query(OperatorLead)
        .filter(db.func.lower(OperatorLead.email) == email)
        .first()
    )
    lead_kind = "operator"
    if not lead:
        lead = (
            db.session.query(B2BLead)
            .filter(db.func.lower(B2BLead.email) == email)
            .first()
        )
        lead_kind = "b2b"
    if not lead:
        return {"ok": True, "matched": False, "reason": "no lead for sender"}, 200

    # Bounce / auto-reply: don't treat as a real reply.
    is_auto = bool(_AUTO_SUBJECT.search(subject or ""))
    if is_auto and re.search(r"delivery|undeliverable|returned|daemon", (subject + " " + email), re.I):
        lead.status = "bounced"
        lead.notes = _append_note(lead.notes, "Bounce/auto: " + subject)
        db.session.commit()
        return {"ok": True, "matched": True, "status": "bounced"}, 200
    if is_auto:
        return {"ok": True, "matched": True, "status": "ignored_autoreply"}, 200

    # A real human reply.
    lead.status = "replied"
    snippet = (text or "").strip().replace("\r", " ").replace("\n", " ")[:280]
    lead.notes = _append_note(lead.notes, "REPLY: {} — {}".format(subject or "(no subject)", snippet))
    db.session.commit()

    _alert_admin_reply(lead, subject, snippet, db, User, Notification, generate_uuid)
    return {"ok": True, "matched": True, "kind": lead_kind, "status": "replied", "lead_id": lead.id}, 200


def _append_note(existing, line):
    stamp = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
    entry = "[{}] {}".format(stamp, line)
    return (existing + "\n" + entry) if existing else entry


def _alert_admin_reply(lead, subject, snippet, db, User, Notification, generate_uuid):
    name = lead.business_name or lead.email
    # In-app notification to every admin
    try:
        for admin in User.query.filter_by(role="admin").all():
            db.session.add(Notification(
                id=generate_uuid(), user_id=admin.id, type="outreach_reply",
                title="Hauler replied: {}".format(name),
                body=(subject or "(no subject)") + " — " + (snippet or ""),
                data={"lead_id": lead.id, "email": lead.email, "phone": lead.phone},
            ))
        db.session.commit()
    except Exception:
        logger.exception("outreach inbound: admin notification failed")
    # Email + SMS the admin so it's seen fast
    cfg = _cfg()
    try:
        from notifications import send_email
        if cfg["report_to"]:
            html = (
                "<div style='font-family:Arial,sans-serif;font-size:14px'>"
                "<h2>A recruited hauler replied 🎉</h2>"
                "<p><b>{name}</b> ({email}{phone})</p>"
                "<p><b>Subject:</b> {subj}</p><blockquote>{body}</blockquote>"
                "<p>Follow up fast — reply from your inbox, or call them.</p></div>"
            ).format(
                name=name, email=lead.email or "—",
                phone=(" · " + lead.phone) if lead.phone else "",
                subj=subject or "(no subject)", body=snippet or "",
            )
            send_email(cfg["report_to"], "Hauler reply: {}".format(name), html)
    except Exception:
        logger.warning("outreach inbound: report email failed")
    try:
        admin_phone = os.environ.get("ADMIN_PHONE", "")
        if admin_phone:
            from sms_service import send_sms_async
            send_sms_async(admin_phone, "Umuve: hauler {} replied to outreach — {}".format(
                name, (snippet or subject or "")[:80]))
    except Exception:
        logger.warning("outreach inbound: admin SMS failed")
