"""Call Desk CRM depth (Phase 3): pipeline stages, tags, card claiming, note
history, light accounts, win alerts, end-of-shift reports.

Hooks into the desk at three points (see va_calls / va_time):
  crm_card_fields(p)         merged into every card payload
  on_outcome(p, outcome, …)  end of apply_outcome → stage + win alert
  end_of_shift_report(va, sh) after clock-out → numbers to the owner

VA-facing (JWT or passcode):
  POST /api/va/crm/pipeline       counts per stage, aging buckets, oldest engaged
  POST /api/va/crm/stage          {prospect_id, stage}           manual move
  POST /api/va/crm/tags           {prospect_id, add: [], remove: []}
  POST /api/va/crm/tag-suggest    {q}
  POST /api/va/crm/claim          {prospect_id}  claim/renew, 409 if someone else holds it
  POST /api/va/crm/release        {prospect_id}
  POST /api/va/crm/claim-status   {prospect_id}
  POST /api/va/crm/account        {prospect_id, account_id? | name?}  create-or-link
  POST /api/va/crm/shift-report   {shift_id}
Manager:
  GET  /api/admin/crm/accounts    accounts with a stage rollup
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from desk_auth import require_desk, audit, is_manager, MANAGER_ROLES
from models import db, CallAttempt, CallProspect, DeskActivity, DeskSetting, VaShift
from models_crm import (ProspectStage, ProspectTag, ProspectClaim, Account, AccountContact,
                        STAGES, STAGE_RANK, ACCOUNT_KINDS, normalize_account_name)

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)
crm_bp = Blueprint("crm", __name__)
_ratelimit = (limiter.limit("600 per hour; 60 per minute") if limiter is not None
              else (lambda f: f))

CLAIM_MINUTES = 20
HISTORY_LIMIT = 10
ACTIVE_STAGES = ("new", "contacted", "engaged", "qualified", "nurture")
CONNECT_OUTCOMES = ("interested", "sent_link", "vendor_listed", "not_interested", "converted", "callback")
INTERESTED_OUTCOMES = ("interested", "sent_link")
WIN_OUTCOMES = ("converted", "vendor_listed")

# outcome → stage. None = keep (callback creates "contacted" when still new).
OUTCOME_STAGE = {
    "voicemail": "contacted", "no_answer": "contacted",
    "interested": "engaged", "sent_link": "engaged",
    "vendor_listed": "nurture", "converted": "won",
    "not_interested": "lost", "bad_number": "lost", "opted_out": "lost",
    "callback": None,
}


def _now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt):
    return dt.isoformat() if dt else None


def _age_days(dt):
    if not dt:
        return 0
    return max(0, int((_now_naive() - dt).total_seconds() // 86400))


def _bucket(days):
    if days <= 2:
        return "0-2d"
    if days <= 7:
        return "3-7d"
    if days <= 30:
        return "8-30d"
    return "30d+"


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def current_stage_row(prospect_id):
    return (ProspectStage.query.filter_by(prospect_id=prospect_id)
            .order_by(ProspectStage.entered_at.desc(), ProspectStage.id.desc()).first())


def current_stage(prospect_id):
    row = current_stage_row(prospect_id)
    return row.stage if row else "new"


def set_stage(prospect, stage, by=None, force=False):
    """Move the prospect. Forward-only among new→contacted→engaged→qualified
    unless force=True; won/lost/nurture always apply. Returns the new stage
    or None when nothing changed."""
    if stage not in STAGES:
        raise ValueError("unknown stage: " + str(stage))
    cur = current_stage(prospect.id)
    if cur == stage:
        return None
    if not force and stage in STAGE_RANK and cur in STAGE_RANK and STAGE_RANK[stage] < STAGE_RANK[cur]:
        return None
    db.session.add(ProspectStage(prospect_id=prospect.id, stage=stage, by=(by or None),
                                 entered_at=_now_naive()))
    return stage


def on_outcome(prospect, outcome, note, va_name):
    """Called at the end of apply_outcome (and schedule_callback). Never raises."""
    try:
        if outcome == "skip":
            return
        target = OUTCOME_STAGE.get(outcome, None)
        if outcome == "callback" and current_stage(prospect.id) == "new":
            target = "contacted"
        moved = set_stage(prospect, target, by=va_name) if target else None
        if moved:
            audit("stage", "prospect", prospect.id, {"stage": moved, "outcome": outcome})
        _maybe_win_alert(prospect, outcome, note, va_name)
    except Exception:
        logger.exception("crm.on_outcome failed for %s/%s", getattr(prospect, "id", "?"), outcome)


def _alert_on_interested():
    return (os.environ.get("CRM_ALERT_ON_INTERESTED") or "").strip().lower() in ("on", "1", "true", "yes")


def _maybe_win_alert(prospect, outcome, note, va_name):
    if outcome in WIN_OUTCOMES:
        label = "WIN" if outcome == "converted" else "VENDOR LISTED"
    elif outcome in INTERESTED_OUTCOMES and _alert_on_interested():
        label = "INTERESTED"
    else:
        return
    try:
        import desk_health
        stage = current_stage(prospect.id)
        subject = "Call Desk {}: {}".format(label, prospect.company)
        body = "\n".join([
            "Company:  {}".format(prospect.company),
            "Contact:  {}".format(prospect.contact_name or "—"),
            "Phone:    {}".format(prospect.direct_phone or prospect.phone or "—"),
            "City:     {}".format(prospect.city or "—"),
            "Outcome:  {}".format(outcome),
            "Stage:    {}".format(stage),
            "VA:       {}".format(va_name or "—"),
            "Note:     {}".format(note or prospect.last_note or "—"),
        ])
        desk_health._send_alert(subject, body)
    except Exception:
        logger.exception("crm win alert failed")


# ---------------------------------------------------------------------------
# Card fields
# ---------------------------------------------------------------------------

def _history(prospect_id, limit=HISTORY_LIMIT):
    rows = (CallAttempt.query.filter_by(prospect_id=prospect_id)
            .order_by(CallAttempt.created_at.desc(), CallAttempt.id.desc()).limit(limit).all())
    return [{"id": a.id, "outcome": a.outcome, "note": a.note, "va_name": a.va_name,
             "created_at": _iso(a.created_at)} for a in rows]


def _tags(prospect_id):
    return [t.tag for t in ProspectTag.query.filter_by(prospect_id=prospect_id)
            .order_by(ProspectTag.created_at.asc(), ProspectTag.tag.asc()).all()]


def _live_claim(prospect_id):
    c = ProspectClaim.query.filter_by(prospect_id=prospect_id).first()
    if c and c.expires_at > _now_naive():
        return c
    return None


def _account_for(prospect_id):
    ct = AccountContact.query.filter_by(prospect_id=prospect_id).first()
    if not ct or not ct.account:
        return None
    return {"id": ct.account.id, "name": ct.account.name}


def crm_card_fields(p):
    row = current_stage_row(p.id)
    entered = row.entered_at if row else p.created_at
    claim = _live_claim(p.id)
    return {
        "stage": row.stage if row else "new",
        "stage_entered_at": _iso(entered),
        "stage_age_days": _age_days(entered),
        "tags": _tags(p.id),
        "claimed_by": claim.va_name if claim else None,
        "claimed_until": _iso(claim.expires_at) if claim else None,
        "history": _history(p.id),
        "account": _account_for(p.id),
    }


# ---------------------------------------------------------------------------
# Claims + queue
# ---------------------------------------------------------------------------

def claim(prospect_id, va_name):
    """→ (claim_row, None) or (None, holder_row) when another VA holds it."""
    now = _now_naive()
    c = ProspectClaim.query.filter_by(prospect_id=prospect_id).first()
    if c and c.va_name != va_name and c.expires_at > now:
        return None, c
    if c is None:
        c = ProspectClaim(prospect_id=prospect_id, va_name=va_name, claimed_at=now)
        db.session.add(c)
    elif c.va_name != va_name:
        c.va_name, c.claimed_at = va_name, now
    c.expires_at = now + timedelta(minutes=CLAIM_MINUTES)
    db.session.commit()
    return c, None


def release(prospect_id, va_name, force=False):
    c = ProspectClaim.query.filter_by(prospect_id=prospect_id).first()
    if not c:
        return False
    if c.va_name != va_name and not force and c.expires_at > _now_naive():
        return False
    db.session.delete(c)
    db.session.commit()
    return True


def _claimed_by_others(va_name):
    now = _now_naive()
    q = ProspectClaim.query.filter(ProspectClaim.expires_at > now)
    if va_name:
        q = q.filter(ProspectClaim.va_name != va_name)
    return [c.prospect_id for c in q.all()]


def next_unclaimed(va_name):
    """Same ordering as va_calls.next_card, minus cards another VA holds."""
    from va_calls import WORKABLE_STATUSES, _category_rank_sql
    now = _now_naive()
    taken = _claimed_by_others(va_name)
    workable = CallProspect.status.in_(WORKABLE_STATUSES)
    free = CallProspect.id.notin_(taken) if taken else True
    due = (CallProspect.query
           .filter(workable, free,
                   CallProspect.next_followup_at.isnot(None),
                   CallProspect.next_followup_at <= now)
           .order_by(CallProspect.next_followup_at.asc())
           .first())
    if due:
        return due
    return (CallProspect.query
            .filter(workable, free, CallProspect.next_followup_at.is_(None))
            .order_by(CallProspect.tier.asc(), _category_rank_sql().asc(),
                      CallProspect.category.asc(), CallProspect.created_at.asc())
            .first())


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

_TAG_CLEAN = re.compile(r"[^a-z0-9 _\-+/&.]")


def _norm_tag(raw):
    s = _TAG_CLEAN.sub("", str(raw or "").strip().lower())
    return " ".join(s.split())[:40]


def set_tags(prospect_id, add=(), remove=(), by=None):
    adds = list(dict.fromkeys(t for t in (_norm_tag(x) for x in add or []) if t))   # input order, deduped
    rems = {t for t in (_norm_tag(x) for x in remove or []) if t}
    have = set(_tags(prospect_id))
    now = _now_naive()
    for i, t in enumerate(a for a in adds if a not in have):
        db.session.add(ProspectTag(prospect_id=prospect_id, tag=t, by=by or None,
                                   created_at=now + timedelta(microseconds=i)))
    adds = set(adds)
    if rems:
        ProspectTag.query.filter(ProspectTag.prospect_id == prospect_id,
                                 ProspectTag.tag.in_(list(rems))).delete(synchronize_session=False)
    db.session.commit()
    return _tags(prospect_id), sorted(adds - have), sorted(rems & have)


def suggest_tags(q, limit=10):
    q = _norm_tag(q)
    query = db.session.query(ProspectTag.tag, func.count(ProspectTag.id).label("n"))
    if q:
        query = query.filter(ProspectTag.tag.like(q + "%"))
    rows = query.group_by(ProspectTag.tag).order_by(func.count(ProspectTag.id).desc(),
                                                    ProspectTag.tag.asc()).limit(limit).all()
    return [{"tag": t, "count": n} for t, n in rows]


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def _guess_kind(category):
    c = (category or "").lower()
    if "property" in c or "hoa" in c or "apartment" in c:
        return "property_mgmt"
    if "storage" in c:
        return "storage"
    if "estate sale" in c or "estate" in c and "real" not in c:
        return "estate"
    if "real estate" in c or "realtor" in c or "broker" in c:
        return "realtor"
    if "junk" in c or "haul" in c or "mover" in c or "moving" in c:
        return "hauler"
    return "other"


def find_account(name):
    norm = normalize_account_name(name)
    if not norm:
        return None
    return Account.query.filter_by(norm_name=norm).order_by(Account.created_at.asc()).first()


def link_account(prospect, account_id=None, name=None, kind=None, city=None, by=None):
    """Create-or-link. → (account, contact, created: bool)."""
    created = False
    acct = None
    if account_id:
        acct = db.session.get(Account, account_id)
        if not acct:
            raise LookupError("account not found")
    else:
        label = (name or prospect.company or "").strip()[:200]
        if not label:
            raise ValueError("name required")
        acct = find_account(label)
        if acct is None:
            acct = Account(name=label, norm_name=normalize_account_name(label),
                           city=(city or prospect.city or None),
                           kind=(kind if kind in ACCOUNT_KINDS else _guess_kind(prospect.category)))
            db.session.add(acct)
            db.session.flush()
            created = True
    ct = AccountContact.query.filter_by(prospect_id=prospect.id).first()
    if ct is None:
        ct = AccountContact(account_id=acct.id, prospect_id=prospect.id)
        db.session.add(ct)
    ct.account_id = acct.id
    ct.name = ct.name or prospect.contact_name
    ct.phone_digits = ct.phone_digits or prospect.phone_digits
    ct.email = ct.email or prospect.email
    db.session.commit()
    return acct, ct, created


def account_rollup(q=None, limit=200):
    query = Account.query
    if q:
        query = query.filter(Account.norm_name.like("%" + normalize_account_name(q) + "%"))
    accounts = query.order_by(Account.created_at.desc()).limit(limit).all()
    out = []
    for a in accounts:
        d = a.to_dict()
        contacts = [c.to_dict() for c in a.contacts]
        pids = [c.prospect_id for c in a.contacts if c.prospect_id]
        stages = {}
        last_touch = None
        for pid in pids:
            st = current_stage(pid)
            stages[st] = stages.get(st, 0) + 1
            p = db.session.get(CallProspect, pid)
            if p and p.last_called_at and (last_touch is None or p.last_called_at > last_touch):
                last_touch = p.last_called_at
        d.update({"contacts": contacts, "prospects": len(pids), "stages": stages,
                  "last_touch": _iso(last_touch)})
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def pipeline_summary():
    latest = {}
    for row in ProspectStage.query.order_by(ProspectStage.entered_at.asc(), ProspectStage.id.asc()).all():
        latest[row.prospect_id] = row
    counts = {s: 0 for s in STAGES}
    aging = {"0-2d": 0, "3-7d": 0, "8-30d": 0, "30d+": 0}
    oldest = []
    for p in CallProspect.query.with_entities(CallProspect.id, CallProspect.company, CallProspect.city,
                                              CallProspect.contact_name, CallProspect.phone,
                                              CallProspect.created_at).all():
        row = latest.get(p.id)
        stage = row.stage if row else "new"
        entered = row.entered_at if row else p.created_at
        counts[stage] = counts.get(stage, 0) + 1
        days = _age_days(entered)
        if stage in ACTIVE_STAGES:
            aging[_bucket(days)] += 1
        if stage in ("engaged", "qualified"):
            oldest.append({"id": p.id, "company": p.company, "city": p.city, "contact_name": p.contact_name,
                           "phone": p.phone, "stage": stage, "stage_age_days": days,
                           "stage_entered_at": _iso(entered)})
    oldest.sort(key=lambda d: d["stage_entered_at"] or "")
    return {"counts": counts, "aging": aging, "oldest": oldest[:20],
            "total": sum(counts.values()), "as_of": _now_naive().isoformat()}


# ---------------------------------------------------------------------------
# End-of-shift report
# ---------------------------------------------------------------------------

def _local(dt):
    from timeutils import to_local
    return to_local(dt)


def build_shift_report(sh):
    end = sh.ended_at or _now_naive()
    va = sh.va_name
    mine = db.or_(CallAttempt.va_name == va, CallAttempt.va_name.is_(None))
    attempts = (CallAttempt.query
                .filter(CallAttempt.created_at >= sh.started_at, CallAttempt.created_at <= end, mine)
                .order_by(CallAttempt.created_at.asc()).all())
    dials = [a for a in attempts if a.outcome != "skip"]
    connects = [a for a in dials if a.outcome in CONNECT_OUTCOMES]
    interested = [a for a in dials if a.outcome in INTERESTED_OUTCOMES]
    callbacks = [a for a in dials if a.outcome == "callback"]
    wins = [a for a in dials if a.outcome in WIN_OUTCOMES]
    texts = (DeskActivity.query
             .filter(DeskActivity.kind == "sms", DeskActivity.direction == "out",
                     DeskActivity.created_at >= sh.started_at, DeskActivity.created_at <= end,
                     db.or_(DeskActivity.va_name == va, DeskActivity.va_name.is_(None)))
             .count())

    def names(rows):
        seen, out = set(), []
        for a in rows:
            if a.prospect_id in seen:
                continue
            seen.add(a.prospect_id)
            p = db.session.get(CallProspect, a.prospect_id)
            if p:
                out.append(p.company)
        return out

    hours = round(max(0, (end - sh.started_at).total_seconds()) / 3600.0, 2)
    start_l, end_l = _local(sh.started_at), _local(end)
    day = start_l.strftime("%a %b %-d")
    rep = {
        "shift_id": sh.id, "va": va, "day": day, "hours": hours,
        "started_local": start_l.strftime("%-I:%M %p"), "ended_local": end_l.strftime("%-I:%M %p"),
        "dials": len(dials), "connects": len(connects), "interested": len(interested),
        "callbacks": len(callbacks), "texts": texts, "wins": len(wins),
        "interested_names": names(interested), "won_names": names(wins),
        "auto_closed": bool(sh.auto_closed),
    }
    lines = [
        "{} · {} – {} · {:g} h{}".format(day, rep["started_local"], rep["ended_local"], hours,
                                         " (auto-closed)" if sh.auto_closed else ""),
        "Dials {} · Connects {} · Interested {} · Callbacks {} · Texts {} · Wins {}".format(
            rep["dials"], rep["connects"], rep["interested"], rep["callbacks"], rep["texts"], rep["wins"]),
    ]
    if rep["interested_names"]:
        lines.append("Interested: " + ", ".join(rep["interested_names"]))
    if rep["won_names"]:
        lines.append("Won: " + ", ".join(rep["won_names"]))
    if rep["dials"] == 0:
        lines.append("No dials logged this shift.")
    rep["body"] = "\n".join(lines)
    rep["subject"] = "Shift report — {} {}".format(va, day)
    return rep


def end_of_shift_report(va, sh):
    """Build, store, and send the report for a just-closed shift. Never raises."""
    try:
        if sh is None or not sh.ended_at:
            return None
        rep = build_shift_report(sh)
        DeskSetting.put("shift_report:" + sh.id, json.dumps(rep))
        try:
            import desk_health
            desk_health._send_alert(rep["subject"], rep["body"])
        except Exception:
            logger.exception("shift report alert failed")
        audit("shift_report", "shift", sh.id, {"dials": rep["dials"], "wins": rep["wins"], "hours": rep["hours"]})
        return rep
    except Exception:
        logger.exception("end_of_shift_report failed for %s", getattr(sh, "id", "?"))
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _body():
    return request.get_json(silent=True) or {}


def _prospect_or_404(data):
    p = db.session.get(CallProspect, (data.get("prospect_id") or "").strip())
    if not p:
        return None, (jsonify({"error": "Prospect not found — reload the page."}), 404)
    return p, None


@crm_bp.route("/api/va/crm/pipeline", methods=["POST"])
@_ratelimit
@require_desk()
def crm_pipeline(ident):
    return jsonify(pipeline_summary()), 200


@crm_bp.route("/api/va/crm/stage", methods=["POST"])
@_ratelimit
@require_desk()
def crm_stage(ident):
    data = _body()
    p, err = _prospect_or_404(data)
    if err:
        return err
    stage = (data.get("stage") or "").strip().lower()
    if stage not in STAGES:
        return jsonify({"error": "Stage must be one of: " + ", ".join(STAGES)}), 400
    moved = set_stage(p, stage, by=ident["name"], force=True)
    db.session.commit()
    if moved:
        audit("stage", "prospect", p.id, {"stage": moved, "manual": True})
    return jsonify({"ok": True, "stage": current_stage(p.id), "changed": bool(moved)}), 200


@crm_bp.route("/api/va/crm/tags", methods=["POST"])
@_ratelimit
@require_desk()
def crm_tags(ident):
    data = _body()
    p, err = _prospect_or_404(data)
    if err:
        return err
    add = data.get("add") or []
    remove = data.get("remove") or []
    if not isinstance(add, list) or not isinstance(remove, list):
        return jsonify({"error": "add and remove must be lists."}), 400
    tags, added, removed = set_tags(p.id, add, remove, by=ident["name"])
    if added or removed:
        audit("tags", "prospect", p.id, {"added": added, "removed": removed})
    return jsonify({"ok": True, "tags": tags, "added": added, "removed": removed}), 200


@crm_bp.route("/api/va/crm/tag-suggest", methods=["POST"])
@_ratelimit
@require_desk()
def crm_tag_suggest(ident):
    return jsonify({"tags": suggest_tags(_body().get("q") or "")}), 200


@crm_bp.route("/api/va/crm/claim", methods=["POST"])
@_ratelimit
@require_desk()
def crm_claim(ident):
    data = _body()
    p, err = _prospect_or_404(data)
    if err:
        return err
    if not ident.get("name"):
        return jsonify({"error": "Type your name on the desk first."}), 400
    mine, holder = claim(p.id, ident["name"])
    if holder:
        mins = max(0, int((holder.expires_at - _now_naive()).total_seconds() // 60))
        return jsonify(dict(holder.to_dict(), error="{} is on this card.".format(holder.va_name),
                            minutes_left=mins)), 409
    audit("claim", "prospect", p.id, {"until": _iso(mine.expires_at)})
    return jsonify(dict(mine.to_dict(), ok=True)), 200


@crm_bp.route("/api/va/crm/release", methods=["POST"])
@_ratelimit
@require_desk()
def crm_release(ident):
    data = _body()
    p, err = _prospect_or_404(data)
    if err:
        return err
    ok = release(p.id, ident.get("name") or "", force=is_manager(ident))
    if ok:
        audit("release", "prospect", p.id)
    return jsonify({"ok": True, "released": ok}), 200


@crm_bp.route("/api/va/crm/claim-status", methods=["POST"])
@_ratelimit
@require_desk()
def crm_claim_status(ident):
    data = _body()
    p, err = _prospect_or_404(data)
    if err:
        return err
    c = _live_claim(p.id)
    if not c:
        return jsonify({"prospect_id": p.id, "claimed_by": None, "claimed_until": None, "mine": False}), 200
    return jsonify(dict(c.to_dict(), mine=(c.va_name == ident.get("name")),
                        minutes_left=max(0, int((c.expires_at - _now_naive()).total_seconds() // 60)))), 200


@crm_bp.route("/api/va/crm/account", methods=["POST"])
@_ratelimit
@require_desk()
def crm_account(ident):
    data = _body()
    p, err = _prospect_or_404(data)
    if err:
        return err
    try:
        acct, ct, created = link_account(p, account_id=(data.get("account_id") or None),
                                         name=(data.get("name") or None), kind=data.get("kind"),
                                         city=data.get("city"), by=ident["name"])
    except LookupError:
        return jsonify({"error": "Account not found."}), 404
    except ValueError:
        return jsonify({"error": "Give the account a name."}), 400
    audit("account_link", "prospect", p.id, {"account_id": acct.id, "created": created})
    return jsonify({"ok": True, "created": created, "account": acct.to_dict(), "contact": ct.to_dict()}), 200


@crm_bp.route("/api/admin/crm/accounts", methods=["GET"])
@require_desk(MANAGER_ROLES)
def admin_accounts(ident):
    return jsonify({"accounts": account_rollup(request.args.get("q") or None)}), 200


@crm_bp.route("/api/va/crm/shift-report", methods=["POST"])
@_ratelimit
@require_desk()
def crm_shift_report(ident):
    data = _body()
    sh = db.session.get(VaShift, (data.get("shift_id") or "").strip())
    if not sh:
        return jsonify({"error": "Shift not found."}), 404
    if sh.va_name != ident.get("name") and not is_manager(ident):
        return jsonify({"error": "That shift belongs to someone else."}), 403
    raw = DeskSetting.get("shift_report:" + sh.id)
    if raw:
        try:
            return jsonify({"report": json.loads(raw), "stored": True}), 200
        except ValueError:
            pass
    rep = build_shift_report(sh)
    if sh.ended_at:
        DeskSetting.put("shift_report:" + sh.id, json.dumps(rep))
    return jsonify({"report": rep, "stored": bool(sh.ended_at)}), 200
