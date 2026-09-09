"""Call Desk Phase 5 — Growth.

Everything that feeds the desk and keeps a VA on it when she's away from it:

  Sourcing → queue     new OperatorLead (supply, tier 2) and B2BLead (demand,
                       tier 1) rows become call prospects every day at 15:30
                       UTC, once each (IngestLog). Flag `auto_ingest`.
  Maya pre-qual        prequal.py — routes live here. Flag `maya_prequal`.
  Installable desk     web manifest + service worker (served from /va/ so it
                       can control /va/calls) + Web Push (VAPID) so a reply
                       reaches the VA's phone. Flag `push_notifications`.
  Calendar feed        /va/calendar/<token>.ics — a VA's callbacks as events.
  HubSpot-ready export /api/admin/growth/export/prospects.csv

Routes (desk identity: Bearer JWT or {code, va_name}):
  POST /api/admin/growth/ingest-run             manager  run ingest now
  POST /api/admin/growth/prequal-run {dry_run}  manager  who would be / was called
  GET  /api/admin/growth/prequal-stats          manager
  GET  /api/admin/growth/export/prospects.csv   manager
  POST /api/growth/prequal/result               Vapi (X-Vapi-Secret)
  POST /api/va/growth/prequal {prospect_id}     latest Maya result for the card
  POST /api/va/growth/card-lookup {company, phone}
  GET  /api/va/growth/push/public-key
  POST /api/va/growth/push/subscribe {subscription}
  POST /api/va/growth/push/unsubscribe {endpoint}
  POST /api/va/growth/calendar-link             → this VA's .ics URL
  GET  /va/calendar/<token>.ics
  GET  /va/desk-sw.js                           service worker (Service-Worker-Allowed: /va/)
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, jsonify, request

from desk_auth import desk_identity, desk_va_name, audit, require_desk, MANAGER_ROLES
from models import db, CallAttempt, CallProspect, OperatorLead, B2BLead, User
from models_growth import IngestLog, PrequalCall, PushSubscription

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)

growth_bp = Blueprint("growth", __name__)

_ratelimit = (limiter.limit("240 per hour; 30 per minute") if limiter is not None else (lambda f: f))

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _now():
    return datetime.now(timezone.utc)


def _flag(name, default=True):
    try:
        from flags import flag
        return bool(flag(name))
    except Exception:
        return default


def _digits(phone):
    d = re.sub(r"\D", "", phone or "")
    return d[-10:] if len(d) >= 10 else d


# ---------------------------------------------------------------------------
# 1. Sourcing → queue (auto-ingest)
# ---------------------------------------------------------------------------

SUPPLY_ANGLE = ("Paid junk-removal jobs in your area, paid same day, no app needed. "
                "Ask what trucks they run and how many jobs a week they'd take.")
DEMAND_ANGLE = ("One number for every cleanout: photo quote up front, unit rentable in "
                "about 24 hours, one monthly invoice. Ask who handles haul-away today.")

_SKIP_LEAD_STATUSES = ("unsubscribed", "skipped", "converted")

_B2B_CATEGORY_WORDS = {
    "property_mgmt": "property management", "property_management": "property management",
    "restaurant": "restaurant", "retail": "retail", "construction": "construction / contractor",
    "office": "office", "hoa": "HOA", "storage": "self storage", "hotel": "hotel",
    "real_estate": "real estate", "senior": "senior living", "apartment": "apartment community",
}


def _lead_category(lead, side):
    raw = (lead.category or "").strip()
    if side == "demand":
        return _B2B_CATEGORY_WORDS.get(raw.lower(), raw.replace("_", " ")) or "commercial"
    return raw.replace("_", " ") or "junk removal"


def _lead_row(lead, side):
    snippet = (lead.notes or "").replace("\n", " ").strip()[:160]
    why = "Sourced by {} outreach".format(lead.source or "places")
    if lead.website:
        why += " · " + lead.website[:120]
    if snippet:
        why += " — " + snippet
    return {
        "tier": 1 if side == "demand" else 2,
        "category": _lead_category(lead, side),
        "company": (lead.business_name or "").strip(),
        "phone": (lead.phone or "").strip(),
        "city": (lead.city or "").strip(),
        "email": (lead.email or "").strip(),
        "why": why,
        "angle": DEMAND_ANGLE if side == "demand" else SUPPLY_ANGLE,
        "_kind": "b2b" if side == "demand" else "operator",
        "_lead_id": lead.id,
    }


def _new_leads(model, kind):
    seen = {r.lead_id for r in IngestLog.query.filter_by(lead_kind=kind).with_entities(IngestLog.lead_id).all()}
    q = (model.query.filter(model.phone.isnot(None), model.phone != "",
                            ~model.status.in_(_SKIP_LEAD_STATUSES))
         .order_by(model.created_at.asc()))
    return [l for l in q.all() if l.id not in seen]


def ingest_leads(force=False):
    """Turn un-ingested sourcing rows into prospects. Returns counts.

    `force` bypasses the auto_ingest flag (the manual admin run)."""
    from va_calls import merge_rows

    if not force and not _flag("auto_ingest", True):
        return {"skipped": True, "reason": "flag auto_ingest off", "added": 0, "merged": 0,
                "invalid": 0, "filtered": 0, "seen": 0}

    rows = [_lead_row(l, "supply") for l in _new_leads(OperatorLead, "operator")]
    rows += [_lead_row(l, "demand") for l in _new_leads(B2BLead, "b2b")]
    seen = len(rows)
    if not rows:
        return {"added": 0, "merged": 0, "invalid": 0, "filtered": 0, "seen": 0}

    kept = rows
    try:  # optional compliance layer (DNC / consent) built by another phase
        import compliance  # noqa: F401
        kept = list(compliance.filter_rows(rows)) or []
    except ImportError:
        kept = rows
    except Exception:
        logger.exception("compliance.filter_rows failed — ingesting unfiltered rows")
        kept = rows
    kept_ids = {(r.get("_kind"), r.get("_lead_id")) for r in kept}
    filtered = [r for r in rows if (r.get("_kind"), r.get("_lead_id")) not in kept_ids]

    # Rows merge_rows can accept (it dedups on phone digits; existing prospects keep history).
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in kept]
    added, skipped, invalid = merge_rows(clean)

    results = {"added": 0, "merged": 0, "invalid": 0, "filtered": 0}
    for r in kept:
        digits = _digits(r["phone"])
        prospect = CallProspect.query.filter_by(phone_digits=digits).first() if len(digits) == 10 else None
        if prospect is None:
            outcome = "invalid"
        elif prospect.why == r["why"] and prospect.created_at and prospect.created_at >= (_now() - timedelta(minutes=5)).replace(tzinfo=None):
            outcome = "added"
        else:
            outcome = "merged"
        results[outcome] += 1
        db.session.add(IngestLog(lead_kind=r["_kind"], lead_id=r["_lead_id"],
                                 prospect_id=prospect.id if prospect else None, result=outcome))
    for r in filtered:
        results["filtered"] += 1
        db.session.add(IngestLog(lead_kind=r["_kind"], lead_id=r["_lead_id"], result="filtered"))
    db.session.commit()
    results["seen"] = seen
    results["added"] = added          # merge_rows is the source of truth for inserts
    results["merged"] = skipped
    results["invalid"] = invalid
    logger.info("Growth ingest: %s", results)
    return results


def run_auto_ingest(app=None):
    """Scheduler entry (daily 15:30 UTC). Never raises."""
    def _do():
        res = ingest_leads(force=False)
        if not res.get("skipped"):
            audit("growth.ingest", "job", None, res, via="system", actor={})
        return res
    try:
        if app is not None:
            with app.app_context():
                return _do()
        return _do()
    except Exception:
        logger.exception("auto-ingest job failed")
        return {"added": 0, "reason": "error"}


@growth_bp.route("/api/admin/growth/ingest-run", methods=["POST"])
@require_desk(MANAGER_ROLES)
def ingest_run(ident):
    res = ingest_leads(force=True)
    audit("growth.ingest_run", "job", None, res)
    return jsonify(dict(res, ok=True)), 200


# ---------------------------------------------------------------------------
# 2. Maya pre-qualification — routes
# ---------------------------------------------------------------------------

_vapi_secret_warned = False


def _verify_vapi_secret():
    """Same gate as routes/vapi.py: X-Vapi-Secret must match VAPI_SERVER_SECRET
    (constant-time). Fail-open only while the env var is unset, warning once."""
    global _vapi_secret_warned
    expected = os.environ.get("VAPI_SERVER_SECRET", "")
    if not expected:
        if not _vapi_secret_warned:
            logger.warning("VAPI_SERVER_SECRET is not set — /api/growth/prequal/result is UNAUTHENTICATED.")
            _vapi_secret_warned = True
        return True
    provided = request.headers.get("X-Vapi-Secret", "")
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


@growth_bp.route("/api/growth/prequal/result", methods=["POST"])
def prequal_result():
    if not _verify_vapi_secret():
        return jsonify({"error": "Unauthorized"}), 401
    import prequal
    data = request.get_json(silent=True) or {}
    ok, info = prequal.handle_result(data)
    if not ok:
        # A Vapi report for some other call (or a malformed one) is not our problem to 4xx.
        status = 400 if data.get("prospect_id") or not data.get("message") else 200
        return jsonify(dict(info, ok=False)), status
    audit("growth.prequal_result", "prospect", info["prospect_id"],
          {"disposition": info["disposition"]}, via="vapi", actor={"name": "Maya", "role": "system"})
    return jsonify(dict(info, ok=True)), 200


@growth_bp.route("/api/admin/growth/prequal-run", methods=["POST"])
@require_desk(MANAGER_ROLES)
def prequal_run(ident):
    import prequal
    data = request.get_json(silent=True) or {}
    dry = bool(data.get("dry_run", True))
    res = prequal.run_prequal(dry_run=dry)
    if not dry:
        audit("growth.prequal_run", "job", None, {"called": len(res.get("called", [])), "reason": res.get("reason")})
    return jsonify(dict(res, dry_run=dry)), 200


@growth_bp.route("/api/admin/growth/prequal-stats", methods=["GET", "POST"])
@require_desk(MANAGER_ROLES)
def prequal_stats(ident):
    import prequal
    return jsonify(prequal.stats()), 200


@growth_bp.route("/api/va/growth/prequal", methods=["POST"])
@_ratelimit
def va_prequal():
    import prequal
    data = request.get_json(silent=True) or {}
    if not desk_identity(data):
        return jsonify({"error": "Sign in to the desk first."}), 401
    pid = str(data.get("prospect_id") or "")
    if not pid or db.session.get(CallProspect, pid) is None:
        return jsonify({"error": "Prospect not found."}), 404
    row = prequal.latest_for(pid)
    if row and row.get("disposition") in ("pending", "failed"):
        row = None
    return jsonify({"prequal": row}), 200


@growth_bp.route("/api/va/growth/card-lookup", methods=["POST"])
@_ratelimit
def card_lookup():
    """The desk DOM has no prospect id — find the card by company + phone text."""
    data = request.get_json(silent=True) or {}
    if not desk_identity(data):
        return jsonify({"error": "Sign in to the desk first."}), 401
    digits = _digits(data.get("phone"))
    company = (data.get("company") or "").strip()
    p = None
    if len(digits) == 10:
        p = CallProspect.query.filter_by(phone_digits=digits).first()
    if p is None and company:
        p = CallProspect.query.filter(CallProspect.company == company).order_by(CallProspect.updated_at.desc()).first()
    if p is None:
        return jsonify({"found": False}), 404
    try:
        from call_kit import detect_side
        side = detect_side(p)
    except Exception:
        side = None
    return jsonify({"found": True, "prospect_id": p.id, "company": p.company, "side": side}), 200


# ---------------------------------------------------------------------------
# 3. Installable desk + Web Push
# ---------------------------------------------------------------------------

def vapid_public_key():
    return (os.environ.get("VAPID_PUBLIC_KEY") or "").strip()


def push_configured():
    return bool(vapid_public_key() and os.environ.get("VAPID_PRIVATE_KEY"))


def push_enabled():
    return _flag("push_notifications", True) and push_configured()


@growth_bp.route("/va/desk-sw.js", methods=["GET"])
def desk_sw():
    """The service worker must be served under /va/ to control /va/calls."""
    path = os.path.join(_STATIC_DIR, "desk-sw.js")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            body = fh.read()
    except OSError:
        return Response("// desk-sw missing", status=404, mimetype="application/javascript")
    resp = Response(body, mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/va/"
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


@growth_bp.route("/api/va/growth/push/public-key", methods=["GET", "POST"])
def push_public_key():
    return jsonify({"key": vapid_public_key() if push_enabled() else "",
                    "enabled": push_enabled(), "configured": push_configured()}), 200


@growth_bp.route("/api/va/growth/push/subscribe", methods=["POST"])
@_ratelimit
def push_subscribe():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    if not push_enabled():
        return jsonify({"error": "Push notifications are off."}), 409
    sub = data.get("subscription") or {}
    endpoint = (sub.get("endpoint") or "").strip()
    keys = sub.get("keys") or {}
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        return jsonify({"error": "That subscription didn't look right."}), 400
    row = PushSubscription.query.filter_by(endpoint=endpoint[:600]).first()
    if row is None:
        row = PushSubscription(endpoint=endpoint[:600])
        db.session.add(row)
    row.va_name = (ident.get("name") or "")[:80] or None
    row.keys = {"p256dh": str(keys["p256dh"]), "auth": str(keys["auth"])}
    row.failures = 0
    db.session.commit()
    audit("growth.push_subscribe", "push", row.id, {"endpoint_host": endpoint.split("/")[2] if "//" in endpoint else ""})
    return jsonify({"ok": True, "id": row.id, "count": PushSubscription.query.count()}), 200


@growth_bp.route("/api/va/growth/push/unsubscribe", methods=["POST"])
@_ratelimit
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    endpoint = ((data.get("subscription") or {}).get("endpoint") or data.get("endpoint") or "").strip()
    removed = 0
    if endpoint:
        removed = PushSubscription.query.filter_by(endpoint=endpoint[:600]).delete()
        db.session.commit()
    audit("growth.push_unsubscribe", "push", None, {"removed": removed})
    return jsonify({"ok": True, "removed": removed}), 200


def _vapid_claims():
    subject = (os.environ.get("VAPID_SUBJECT") or "mailto:ops@goumuve.com").strip()
    if not subject.startswith(("mailto:", "https://")):
        subject = "mailto:" + subject
    return {"sub": subject}


def send_push(title, body, url="/va/calls", tag=None):
    """Push to every subscription; prune the ones the push service says are gone.
    Returns {"sent", "pruned", "failed"}. Never raises."""
    out = {"sent": 0, "pruned": 0, "failed": 0}
    if not push_enabled():
        return out
    try:
        import pywebpush
    except ImportError:  # pragma: no cover
        logger.warning("pywebpush not installed — push skipped")
        return out
    payload = json.dumps({"title": title, "body": body, "tag": tag or "desk-reply", "data": {"url": url}})
    private_key = os.environ.get("VAPID_PRIVATE_KEY", "")
    subs = PushSubscription.query.all()
    for s in subs:
        try:
            pywebpush.webpush(subscription_info=s.subscription_info(), data=payload,
                              vapid_private_key=private_key, vapid_claims=_vapid_claims(), ttl=3600)
            s.last_used_at = _now().replace(tzinfo=None)
            s.failures = 0
            out["sent"] += 1
        except Exception as exc:  # WebPushException or transport error
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                db.session.delete(s)
                out["pruned"] += 1
            else:
                s.failures = (s.failures or 0) + 1
                out["failed"] += 1
                logger.warning("push failed (%s): %s", status, exc)
    try:
        db.session.commit()
    except Exception:
        logger.exception("push bookkeeping commit failed")
        db.session.rollback()
    return out


def notify_reply(prospect, preview):
    """Called from desk_line when a prospect texts or leaves a voicemail."""
    try:
        who = (prospect.company if prospect is not None else None) or "A prospect"
        body = (preview or "").replace("\n", " ").strip()[:140] or "Open the desk to read it."
        return send_push("{} replied".format(who), body, url="/va/calls",
                         tag="reply-" + (prospect.id if prospect is not None else "unknown"))
    except Exception:
        logger.exception("notify_reply failed")
        return {"sent": 0, "pruned": 0, "failed": 0}


# ---------------------------------------------------------------------------
# 4. Calendar feed
# ---------------------------------------------------------------------------

def _calendar_secret():
    return (os.environ.get("SECRET_KEY") or os.environ.get("TRIXIE_ASSISTANT_PASSCODE") or "umuve-desk").encode("utf-8")


def calendar_token(va_name):
    name = (va_name or "").strip()
    return hmac.new(_calendar_secret(), name.encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def _known_va_names():
    names = set()
    try:
        for (n,) in db.session.query(CallAttempt.va_name).filter(CallAttempt.va_name.isnot(None)).distinct().all():
            names.add(n)
    except Exception:
        pass
    try:
        from desk_auth import _display_name, DESK_ROLES
        for u in User.query.filter(User.role.in_(DESK_ROLES)).all():
            names.add(_display_name(u))
    except Exception:
        pass
    try:
        from models import VaShift
        for (n,) in db.session.query(VaShift.va_name).distinct().all():
            names.add(n)
    except Exception:
        pass
    return {n for n in names if n}


def remember_token(va_name):
    """Pin token → name so the feed resolves even for a VA with no history yet."""
    try:
        from models import DeskSetting
        DeskSetting.put("calendar:" + calendar_token(va_name), (va_name or "").strip()[:80])
    except Exception:
        logger.exception("could not remember calendar token")
        db.session.rollback()


def va_for_token(token):
    token = (token or "").strip().lower()
    if len(token) != 24:
        return None
    try:
        from models import DeskSetting
        pinned = DeskSetting.get("calendar:" + token)
        if pinned and hmac.compare_digest(calendar_token(pinned), token):
            return pinned
    except Exception:
        pass
    for name in _known_va_names():
        if hmac.compare_digest(calendar_token(name), token):
            return name
    return None


def _ics_escape(s):
    return (str(s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line):
    """RFC 5545 line folding at 75 octets."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b
        else:
            cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def callbacks_for(va_name):
    """Future callbacks whose latest CallAttempt is by this VA; if the VA has
    logged nothing yet, every future callback."""
    now_naive = _now().replace(tzinfo=None)
    rows = (CallProspect.query
            .filter(CallProspect.next_followup_at.isnot(None), CallProspect.next_followup_at > now_naive,
                    CallProspect.status.in_(("queued", "interested", "vendor_listed")))
            .order_by(CallProspect.next_followup_at.asc()).all())
    has_any = CallAttempt.query.filter(CallAttempt.va_name == va_name).first() is not None
    if not has_any:
        return rows
    mine = []
    for p in rows:
        last = (CallAttempt.query.filter_by(prospect_id=p.id)
                .order_by(CallAttempt.created_at.desc()).first())
        if last is not None and (last.va_name or "") == va_name:
            mine.append(p)
    return mine


def build_ics(va_name, prospects):
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Umuve//Call Desk//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             _fold("X-WR-CALNAME:Umuve callbacks — " + (va_name or "desk"))]
    for p in prospects:
        start = p.next_followup_at.replace(tzinfo=None)
        end = start + timedelta(minutes=15)
        desc = "Phone: {}".format(p.phone)
        if p.contact_name:
            desc += "\nAsk for: {}".format(p.contact_name)
        if p.last_note:
            desc += "\nLast note: {}".format(p.last_note.strip()[:600])
        desc += "\nOpen the desk: /va/calls"
        lines += ["BEGIN:VEVENT",
                  _fold("UID:callback-{}-{}@goumuve.com".format(p.id, start.strftime("%Y%m%dT%H%M"))),
                  "DTSTAMP:" + stamp,
                  "DTSTART:" + start.strftime("%Y%m%dT%H%M%SZ"),
                  "DTEND:" + end.strftime("%Y%m%dT%H%M%SZ"),
                  _fold("SUMMARY:" + _ics_escape("Call back " + p.company)),
                  _fold("DESCRIPTION:" + _ics_escape(desc)),
                  _fold("LOCATION:" + _ics_escape(p.city or "")),
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


@growth_bp.route("/va/calendar/<token>.ics", methods=["GET"])
def calendar_feed(token):
    va = va_for_token(token)
    if va is None:
        return Response("Not found", status=404, mimetype="text/plain")
    body = build_ics(va, callbacks_for(va))
    resp = Response(body, mimetype="text/calendar")
    resp.headers["Content-Disposition"] = 'inline; filename="umuve-callbacks.ics"'
    resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


@growth_bp.route("/api/va/growth/calendar-link", methods=["POST"])
@_ratelimit
def calendar_link():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    va = desk_va_name(data)
    if not va:
        return jsonify({"error": "Save your name on the desk first."}), 400
    base = (os.environ.get("BACKEND_URL") or request.url_root).rstrip("/")
    path = "/va/calendar/{}.ics".format(calendar_token(va))
    remember_token(va)
    audit("growth.calendar_link", "va", va)
    return jsonify({"url": base + path, "path": path,
                    "webcal": "webcal://" + base.split("://", 1)[-1] + path}), 200


# ---------------------------------------------------------------------------
# 5. HubSpot-ready export
# ---------------------------------------------------------------------------

EXPORT_HEADER = ["Company name", "Phone number", "City", "Contact", "Email", "Lifecycle stage", "Notes"]

_LIFECYCLE = {"queued": "lead", "interested": "opportunity", "vendor_listed": "opportunity",
              "converted": "customer", "dead": "other"}


def lifecycle_stage(status):
    return _LIFECYCLE.get((status or "").lower(), "other")


def export_rows():
    for p in CallProspect.query.order_by(CallProspect.tier.asc(), CallProspect.company.asc()).all():
        notes = " | ".join(x for x in [
            ("Tier {}".format(p.tier) if p.tier else ""),
            (p.category or ""),
            ("Why: " + p.why) if p.why else "",
            ("Last: " + p.last_note.strip()) if p.last_note else "",
        ] if x)
        yield [p.company, p.phone, p.city or "", p.contact_name or "", p.email or "",
               lifecycle_stage(p.status), notes]


@growth_bp.route("/api/admin/growth/export/prospects.csv", methods=["GET", "POST"])
@require_desk(MANAGER_ROLES)
def export_prospects(ident):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(EXPORT_HEADER)
    n = 0
    for row in export_rows():
        w.writerow(row)
        n += 1
    audit("growth.export", "prospects", None, {"rows": n})
    resp = Response(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = 'attachment; filename="umuve-prospects-{}.csv"'.format(_now().strftime("%Y%m%d"))
    return resp
