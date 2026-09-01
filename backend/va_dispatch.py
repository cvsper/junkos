"""VA Dispatch Desk — job board + hauler assignment for the VA suite.

Born from the first real Maya phone close (Aug 2026, $400): phone customers
never touch the app, so booked jobs need a human dispatcher to put a hauler
on them. The desk shows every open job as a manifest card — price forward,
address as the headline — and one tap assigns an approved hauler through
the exact same machinery the admin dashboard uses (dispatch_service):
operator delegation, concierge SMS console links, and every customer /
driver notification fire identically.

Routes:
  GET  /va/dispatch             -> console page (same gate/passcode as /va)
  GET  /va/dispatch.css         -> desk-only styles (layered over /va/app.css)
  GET  /va/dispatch.js          -> client script
  POST /api/va/dispatch/board   -> passcode-gated; open jobs + recent activity
  POST /api/va/dispatch/haulers -> passcode-gated; ranked haulers for a job
  POST /api/va/dispatch/assign  -> passcode-gated; assign hauler to job
  POST /api/va/dispatch/log-job -> passcode-gated; log a phone-closed booking

Guardrails:
  - The desk can only touch jobs in ASSIGNABLE_STATUSES with no hauler yet.
  - Synthetic/seed rows never reach the board (SYNTHETIC marker + a cutoff
    date that predates real bookings screens out the Feb placeholders).
  - Every action lands in va_dispatch_actions with the VA's name.
"""
from __future__ import annotations

import hmac
import logging
import os
import re
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from models import (
    Contractor, Job, Payment, User, VaDispatchAction, db, generate_referral_code,
    generate_uuid,
)
from dispatch_service import ASSIGNABLE_STATUSES, AssignmentError, assign_contractor_to_job

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)

vadispatch_bp = Blueprint("vadispatch", __name__)

_ratelimit = (
    limiter.limit("240 per hour; 30 per minute")
    if limiter is not None
    else (lambda f: f)
)

# Jobs created before real phone bookings existed are seed/test rows — the
# May load-test rows carry a SYNTHETIC marker, the Feb placeholders predate
# this cutoff. Neither belongs on a dispatcher's board.
REAL_JOBS_SINCE = datetime(2026, 6, 1)


def _passcode_ok(supplied):
    expected = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    if not expected:
        return False  # fail closed
    return hmac.compare_digest(str(supplied or ""), str(expected))


def _digits(phone):
    return re.sub(r"\D", "", phone or "")


def _items_summary(items):
    """[{category, quantity, size?}] -> '2x sofa, 1x hot tub (large)'."""
    if not items:
        return ""
    parts = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        cat = str(entry.get("category") or "item").replace("_", " ")
        qty = entry.get("quantity") or 1
        size = entry.get("size")
        parts.append("{}x {}{}".format(qty, cat, " ({})".format(size) if size else ""))
    return ", ".join(parts)


def _job_card(job):
    customer = job.customer
    return {
        "id": job.id,
        "code": job.confirmation_code,
        "status": job.status,
        "address": job.address,
        "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
        "scheduled_human": (job.scheduled_at.strftime("%a %b %-d, %-I:%M %p")
                            if job.scheduled_at else "Not scheduled"),
        "total_price": job.total_price,
        "items": _items_summary(job.items),
        "notes": (job.notes or "")[:400],
        "lead_source": job.lead_source or "",
        "customer_name": (customer.name if customer else None) or "Customer",
        "customer_phone": customer.phone if customer else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def _open_jobs_query():
    from sqlalchemy import or_
    return (Job.query
            .filter(Job.status.in_(ASSIGNABLE_STATUSES),
                    Job.driver_id.is_(None),
                    Job.operator_id.is_(None),
                    Job.created_at >= REAL_JOBS_SINCE,
                    # NULL notes must survive the synthetic screen (NOT ILIKE
                    # alone drops NULL rows under SQL three-valued logic).
                    or_(Job.notes.is_(None), ~Job.notes.ilike("%SYNTHETIC%")))
            .order_by(Job.scheduled_at.asc().nullslast(), Job.created_at.asc()))


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@vadispatch_bp.route("/api/va/dispatch/board", methods=["POST"])
@_ratelimit
def dispatch_board():
    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401

    jobs = [_job_card(j) for j in _open_jobs_query().limit(50).all()]

    recent = []
    for act in (VaDispatchAction.query
                .order_by(VaDispatchAction.created_at.desc()).limit(5).all()):
        job = db.session.get(Job, act.job_id)
        hauler = db.session.get(Contractor, act.contractor_id) if act.contractor_id else None
        recent.append({
            "action": act.action,
            "va_name": act.va_name,
            "job_code": job.confirmation_code if job else None,
            "job_address": job.address if job else None,
            "hauler_name": (hauler.user.name if hauler and hauler.user else None),
            "at": act.created_at.isoformat() if act.created_at else None,
        })

    return jsonify({"jobs": jobs, "recent": recent}), 200


@vadispatch_bp.route("/api/va/dispatch/haulers", methods=["POST"])
@_ratelimit
def dispatch_haulers():
    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401

    job = db.session.get(Job, data.get("job_id") or "")
    if not job:
        return jsonify({"error": "Job not found."}), 404

    try:
        from dispatcher import haversine
    except Exception:  # pragma: no cover
        haversine = None

    rows = (Contractor.query
            .filter(Contractor.approval_status == "approved")
            .all())

    haulers = []
    for c in rows:
        distance = None
        if (haversine and job.lat is not None and job.lng is not None
                and c.current_lat is not None and c.current_lng is not None):
            distance = round(haversine(job.lat, job.lng, c.current_lat, c.current_lng), 1)
        if c.is_operator:
            kind = "operator"
        elif c.is_concierge:
            kind = "text"
        else:
            kind = "app"
        haulers.append({
            "id": c.id,
            "name": (c.user.name if c.user else None) or "Hauler",
            "phone": c.user.phone if c.user else None,
            "kind": kind,
            "is_online": bool(c.is_online),
            "avg_rating": round(c.avg_rating or 0, 1),
            "total_jobs": c.total_jobs or 0,
            "truck_type": c.truck_type,
            "distance_miles": distance,
        })

    # Online first, then nearest (unknown distance last), then most proven.
    haulers.sort(key=lambda h: (
        0 if h["is_online"] else 1,
        h["distance_miles"] if h["distance_miles"] is not None else 9999,
        -h["total_jobs"],
    ))

    return jsonify({"job": _job_card(job), "haulers": haulers}), 200


@vadispatch_bp.route("/api/va/dispatch/assign", methods=["POST"])
@_ratelimit
def dispatch_assign():
    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401

    va_name = (data.get("va_name") or "").strip()[:80]

    job = db.session.get(Job, data.get("job_id") or "")
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job.status not in ASSIGNABLE_STATUSES or job.driver_id or job.operator_id:
        return jsonify({"error": "This job was already assigned or has moved on — refresh the board."}), 409

    contractor = db.session.get(Contractor, data.get("contractor_id") or "")
    if not contractor:
        return jsonify({"error": "Hauler not found."}), 404

    try:
        job_dict = assign_contractor_to_job(
            job, contractor,
            assigned_by="{} (dispatch desk)".format(va_name or "The dispatch desk"))
    except AssignmentError as e:
        return jsonify({"error": str(e)}), e.status_code

    db.session.add(VaDispatchAction(
        job_id=job.id, contractor_id=contractor.id, action="assign", va_name=va_name or None))
    db.session.commit()

    hauler_name = (contractor.user.name if contractor.user else None) or "the hauler"
    kind_note = ("They'll get the job console by text."
                 if contractor.is_concierge else
                 "They've been notified in the app.")
    logger.info("VA dispatch: %s assigned job %s to %s", va_name or "?", job.id, contractor.id)

    return jsonify({"success": True, "job": job_dict,
                    "message": "Assigned to {}. {}".format(hauler_name, kind_note)}), 200


@vadispatch_bp.route("/api/va/dispatch/log-job", methods=["POST"])
@_ratelimit
def dispatch_log_job():
    """Log a job closed by a human on the phone (no Maya, no website).

    Creates the guest customer + pending job, exactly like a web guest
    booking but priced by hand — it lands on this same board for assignment.
    """
    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("code")):
        return jsonify({"error": "That code didn't work."}), 401

    va_name = (data.get("va_name") or "").strip()[:80]
    name = (data.get("customer_name") or "").strip()[:120]
    phone = (data.get("customer_phone") or "").strip()[:40]
    email = (data.get("customer_email") or "").strip().lower()[:254]
    address = (data.get("address") or "").strip()
    items_text = (data.get("items_text") or "").strip()[:400]
    notes = (data.get("notes") or "").strip()[:600]

    if len(_digits(phone)) != 10:
        return jsonify({"error": "Customer phone needs 10 digits."}), 400
    if not address:
        return jsonify({"error": "The job address is required."}), 400
    try:
        price = round(float(data.get("price")), 2)
    except (TypeError, ValueError):
        return jsonify({"error": "Price must be a number, like 400 or 400.50."}), 400
    if not (0 < price < 20000):
        return jsonify({"error": "That price looks off — double-check it."}), 400

    scheduled_at = None
    raw_sched = (data.get("scheduled_at") or "").strip()
    if raw_sched:
        try:
            scheduled_at = datetime.strptime(raw_sched, "%Y-%m-%dT%H:%M")
        except ValueError:
            return jsonify({"error": "Couldn't read the date/time — use the picker."}), 400

    # Reuse an existing customer when we can match them; otherwise create a
    # guest record. Phone-only customers are fine — email is optional.
    # users.phone is UNIQUE, so the phone match must be thorough or the
    # insert below would blow up on a formatting-variant duplicate.
    customer = None
    if email:
        customer = User.query.filter_by(email=email).first()
    if customer is None:
        customer = User.query.filter_by(phone=phone).first()
    if customer is None:
        digits = _digits(phone)
        for u in User.query.filter(User.phone.isnot(None)).filter(
                User.phone.like("%{}%".format(digits[-4:]))).limit(200):
            if _digits(u.phone)[-10:] == digits:
                customer = u
                break
    if customer is None:
        customer = User(
            id=generate_uuid(),
            email=email or None,
            name=name or None,
            phone=phone,
            role="customer",
        )
        db.session.add(customer)
        db.session.flush()
    else:
        if name and not customer.name:
            customer.name = name
        if phone and not customer.phone:
            customer.phone = phone

    note_lines = []
    if items_text:
        note_lines.append("Items: {}".format(items_text))
    if notes:
        note_lines.append(notes)
    note_lines.append("Phone booking logged by {} at the dispatch desk.".format(va_name or "the VA desk"))

    job = Job(
        id=generate_uuid(),
        customer_id=customer.id,
        status="pending",
        address=address,
        scheduled_at=scheduled_at,
        base_price=price,
        total_price=price,
        notes="\n".join(note_lines),
        lead_source="phone",
        confirmation_code=generate_referral_code(),
    )
    db.session.add(job)
    db.session.flush()

    db.session.add(Payment(
        id=generate_uuid(),
        job_id=job.id,
        amount=price,
        service_fee=0.0,
        payment_status="pending",
    ))
    db.session.add(VaDispatchAction(
        job_id=job.id, contractor_id=None, action="log_job", va_name=va_name or None))
    try:
        db.session.commit()
    except Exception:
        # users.phone / users.email are UNIQUE — a formatting variant that
        # slipped past the match above lands here rather than as a 500.
        db.session.rollback()
        logger.exception("VA dispatch: log-job commit failed")
        return jsonify({"error": "A customer with that phone or email already "
                                 "exists in a different format — add the email "
                                 "or double-check the number."}), 409

    logger.info("VA dispatch: %s logged phone job %s ($%s)", va_name or "?", job.id, price)
    return jsonify({"success": True, "job": _job_card(job),
                    "message": "Job {} is on the board.".format(job.confirmation_code)}), 200


# ---------------------------------------------------------------------------
# Console page
# ---------------------------------------------------------------------------

def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@vadispatch_bp.route("/va/dispatch", methods=["GET"])
def dispatch_page():
    return Response(DISPATCH_HTML, mimetype="text/html")


@vadispatch_bp.route("/va/dispatch.css", methods=["GET"])
def dispatch_css():
    return _no_cache(Response(DISPATCH_CSS, mimetype="text/css"))


@vadispatch_bp.route("/va/dispatch.js", methods=["GET"])
def dispatch_js():
    return _no_cache(Response(DISPATCH_JS, mimetype="application/javascript"))


DISPATCH_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<meta name="theme-color" content="#0B0E12" />
<title>Umuve — Dispatch Desk</title>
<link rel="stylesheet" href="/va/app.css?v=3" />
<link rel="stylesheet" href="/va/dispatch.css?v=1" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="gatewrap">
      <img class="brand-lg rv" src="/va/logo.png" alt="Umuve" /><div class="eyebrow rv">Internal · VA suite</div>
      <h1 class="display" id="display-gate" aria-label="Dispatch">DISPATCH</h1>
      <p class="sub rv">Open jobs on the left of the phone, a hauler on the other end. Put them together.</p>
      <form id="gate-form" class="rv">
        <label class="lbl" for="code">Passcode</label>
        <input id="code" type="password" autocomplete="current-password" placeholder="Team passcode" />
        <label class="lbl" for="va">Your name</label>
        <input id="va" type="text" autocomplete="name" placeholder="So actions are signed" />
        <button class="btn" type="submit">Open the desk</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
    </div>
  </section>

  <section id="tool" class="tool" hidden>
    <header class="bar">
      <a class="back" href="/va" aria-label="Back to VA tools">←</a>
      <span class="wordmark">DISPATCH</span>
      <span class="bar-sub" id="bar-sub">—</span>
    </header>

    <div class="body">
      <p id="desk-err" class="err" hidden></p>
      <p id="desk-toast" class="toast" hidden></p>

      <!-- board -->
      <div id="board">
        <details class="logbox" id="logbox">
          <summary>Log a phone job</summary>
          <p class="log-sub">Closed a customer on a call yourself? Enter it here — it lands on this board for assignment.</p>
          <form id="log-form">
            <label class="lbl" for="lg-name">Customer name</label>
            <input id="lg-name" type="text" placeholder="Jane Rivera" />
            <label class="lbl" for="lg-phone">Customer phone</label>
            <input id="lg-phone" type="tel" placeholder="(561) 555-0142" />
            <label class="lbl" for="lg-addr">Job address</label>
            <input id="lg-addr" type="text" placeholder="Street, city" />
            <label class="lbl" for="lg-price">Price quoted ($)</label>
            <input id="lg-price" type="number" inputmode="decimal" step="0.01" min="1" placeholder="400" />
            <label class="lbl" for="lg-when">Scheduled for <span class="opt">— optional</span></label>
            <input id="lg-when" type="datetime-local" />
            <label class="lbl" for="lg-items">What's being hauled <span class="opt">— optional</span></label>
            <input id="lg-items" type="text" placeholder="Sofa, mattress, hot tub…" />
            <label class="lbl" for="lg-notes">Notes <span class="opt">— optional</span></label>
            <input id="lg-notes" type="text" placeholder="Gate code, stairs, heavy items…" />
            <button class="btn" type="submit" id="lg-btn">Add job to the board</button>
            <p id="lg-err" class="err" hidden></p>
          </form>
        </details>

        <div class="boardhead">
          <span class="boardcount" id="board-count">—</span>
          <button class="ghostbtn" id="refresh" type="button">Refresh</button>
        </div>
        <div id="jobs"></div>
        <div id="board-empty" class="board-empty" hidden>
          <p>No open jobs right now.</p>
          <p class="be-sub">New bookings from Maya, the website, or the form above land here the moment they exist.</p>
        </div>

        <div id="recent" hidden>
          <div class="recent-head">Recent desk activity</div>
          <div id="recent-rows"></div>
        </div>
      </div>

      <!-- hauler picker -->
      <div id="picker" hidden>
        <button class="ghostbtn" id="picker-back" type="button">← Back to the board</button>
        <div class="deskcard" id="picker-job"></div>
        <div class="picker-head">Choose a hauler</div>
        <div id="haulers"></div>
      </div>
    </div>
  </section>
</div>
<script src="/va/dispatch.js?v=1"></script>
</body>
</html>
"""


DISPATCH_CSS = r"""/* Dispatch Desk — layers over /va/app.css tokens */
[hidden]{display:none!important}
.toast{margin:0;padding:11px 14px;border-radius:12px;font-size:13.5px;
  background:rgba(61,214,140,.12);color:var(--ok);border:1px solid rgba(61,214,140,.35)}

/* board chrome */
.boardhead{display:flex;align-items:center;justify-content:space-between;margin:4px 0 2px}
.boardcount{font-family:var(--display);font-weight:600;font-size:10.5px;
  letter-spacing:.22em;text-transform:uppercase;color:var(--faint)}
.ghostbtn{font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.06em;
  color:var(--muted);background:var(--surface);border:1px solid var(--line);
  border-radius:11px;padding:9px 14px;cursor:pointer}
.ghostbtn:active{transform:translateY(1px)}
.board-empty{background:var(--surface);border:1px dashed var(--line);border-radius:18px;
  padding:26px 20px;text-align:center}
.board-empty p{margin:0;font-size:15px}
.be-sub{color:var(--faint);font-size:12.5px!important;margin-top:6px!important}

/* job manifest card */
.jobcard{background:var(--surface);border:1px solid var(--line);border-radius:18px;
  padding:16px 16px 14px;margin-bottom:12px}
.jobtop{display:flex;align-items:baseline;gap:10px;margin-bottom:6px}
.jobprice{font-family:var(--display);font-weight:900;font-size:clamp(26px,7.5vw,34px);
  letter-spacing:-.02em;font-variant-numeric:tabular-nums;color:var(--ink)}
.jobcode{font-family:var(--display);font-weight:600;font-size:10px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--faint);margin-left:auto}
.jobaddr{font-family:var(--display);font-weight:800;font-size:clamp(16px,4.6vw,20px);
  letter-spacing:-.01em;line-height:1.15;margin:0 0 10px}
.jobchips{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}
.jchip{font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--muted);background:var(--raise);
  border:1px solid var(--line);border-radius:8px;padding:4px 8px}
.jchip-when{color:#7FB8FF;border-color:rgba(127,184,255,.4)}
.jchip-src{color:var(--accent);border-color:rgba(255,106,44,.4)}
.jobfacts{border-top:1px solid var(--line);padding-top:8px;margin-bottom:12px}
.jf{display:flex;gap:12px;padding:5px 0}
.jf-k{flex:none;width:64px;font-family:var(--display);font-weight:600;font-size:10px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--faint);padding-top:2px}
.jf-v{color:var(--muted);font-size:13.5px;line-height:1.45;overflow-wrap:anywhere;white-space:pre-line}
.jf-v a{color:var(--ink);text-decoration:none;border-bottom:1px solid rgba(255,106,44,.5)}
.assignbtn{width:100%;padding:14px;font-size:15px;font-family:var(--display);font-weight:700;
  color:#0B0E12;background:var(--accent);border:none;border-radius:13px;cursor:pointer}
.assignbtn:active{transform:translateY(1px)}

/* log a phone job */
.logbox{background:var(--surface);border:1px solid var(--line);border-radius:18px;
  padding:14px 16px;margin-bottom:14px}
.logbox summary{font-family:var(--display);font-weight:600;font-size:10.5px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--accent);cursor:pointer;list-style:none}
.logbox summary::before{content:"▸ "}
.logbox[open] summary::before{content:"▾ "}
.log-sub{color:var(--faint);font-size:12.5px;line-height:1.5;margin:10px 0 2px}

/* recent activity */
.recent-head{font-family:var(--display);font-weight:600;font-size:10px;letter-spacing:.2em;
  text-transform:uppercase;color:var(--faint);margin:18px 0 8px}
.recent-row{color:var(--faint);font-size:12.5px;line-height:1.6;padding:4px 0;
  border-top:1px solid var(--line)}
.recent-row b{color:var(--muted);font-weight:600}

/* hauler picker */
.picker-head{font-family:var(--display);font-weight:600;font-size:10.5px;
  letter-spacing:.22em;text-transform:uppercase;color:var(--faint);margin:16px 0 8px}
.deskcard{background:var(--surface);border:1px solid var(--line);border-radius:18px;
  padding:16px;margin-top:12px}
.haulrow{display:flex;align-items:center;gap:12px;background:var(--surface);
  border:1px solid var(--line);border-radius:16px;padding:14px;margin-bottom:10px}
.haulmain{min-width:0;flex:1}
.haulname{font-family:var(--display);font-weight:800;font-size:16px;letter-spacing:-.01em;
  margin-bottom:3px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.hchip{font-family:var(--display);font-weight:700;font-size:9.5px;letter-spacing:.12em;
  text-transform:uppercase;border-radius:7px;padding:3px 7px;border:1px solid var(--line);color:var(--muted)}
.hchip-online{color:var(--ok);border-color:rgba(61,214,140,.4)}
.hchip-text{color:#7FB8FF;border-color:rgba(127,184,255,.4)}
.hchip-operator{color:var(--accent);border-color:rgba(255,106,44,.4)}
.haulmeta{color:var(--faint);font-size:12.5px}
.haulbtn{flex:none;font-family:var(--display);font-weight:700;font-size:13px;
  color:var(--ink);background:var(--raise);border:1.5px solid rgba(255,106,44,.45);
  border-radius:12px;padding:11px 16px;cursor:pointer;transition:background .12s,color .12s}
.haulbtn.confirm{background:var(--accent);color:#0B0E12;border-color:var(--accent)}
.haulbtn:disabled{opacity:.5;cursor:default}
.sr-none{color:var(--faint);font-size:13px;padding:6px 2px}
@media (min-width:700px){
  #jobs{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .jobcard{margin-bottom:0}
}
"""


DISPATCH_JS = r"""(function(){
  var KEY = "umuve_coach_code";      // shared login across the VA suite
  var VA_KEY = "umuve_va_name";
  var gate = document.getElementById("gate");
  var tool = document.getElementById("tool");
  var gateErr = document.getElementById("gate-err");
  var deskErr = document.getElementById("desk-err");
  var toast = document.getElementById("desk-toast");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var busy = false;
  var confirmTimer = null;

  function splitChars(el){
    if(!el || el.dataset.split) return;
    el.dataset.split = "1";
    var text = el.textContent;
    el.textContent = "";
    for(var i = 0; i < text.length; i++){
      var s = document.createElement("span");
      s.className = "ch";
      s.textContent = text[i] === " " ? " " : text[i];
      el.appendChild(s);
    }
  }
  function reveal(scope){
    if(reduced){
      scope.querySelectorAll(".rv,.display .ch").forEach(function(el){ el.classList.add("in"); });
      return;
    }
    scope.querySelectorAll(".display").forEach(splitChars);
    scope.querySelectorAll(".display .ch").forEach(function(c, i){
      setTimeout(function(){ c.classList.add("in"); }, 40 + i * 26);
    });
    scope.querySelectorAll(".rv").forEach(function(b, i){
      setTimeout(function(){ b.classList.add("in"); }, 140 + i * 65);
    });
  }

  function code(){ return localStorage.getItem(KEY) || ""; }
  function vaName(){ return localStorage.getItem(VA_KEY) || ""; }
  function showTool(){ gate.hidden = true; tool.hidden = false; }
  function showGate(msg){
    tool.hidden = true; gate.hidden = false; reveal(gate);
    if(msg && gateErr){ gateErr.textContent = msg; gateErr.hidden = false; }
    var c = document.getElementById("code"); if(c) c.focus();
  }
  function err(msg){
    deskErr.textContent = msg || ""; deskErr.hidden = !msg;
    if(msg) deskErr.scrollIntoView({block:"nearest"});
  }
  function flash(msg){
    toast.textContent = msg; toast.hidden = false;
    setTimeout(function(){ toast.hidden = true; }, 5000);
  }
  function esc(s){
    return String(s == null ? "" : s).replace(/[&<>"']/g, function(ch){
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch];
    });
  }

  function api(path, body, done){
    if(busy) return; busy = true;
    body = body || {};
    body.code = code();
    body.va_name = vaName();
    fetch(path, {method:"POST", headers:{"Content-Type":"application/json"},
                 body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {ok:r.ok, status:r.status, j:j}; }); })
      .then(function(res){
        busy = false;
        if(res.status === 401){ localStorage.removeItem(KEY); showGate("That code didn't work — try again."); return; }
        done(res);
      })
      .catch(function(){ busy = false; err("Network hiccup — try that again."); });
  }

  /* ---------- board ---------- */
  var board = document.getElementById("board");
  var picker = document.getElementById("picker");
  var jobsEl = document.getElementById("jobs");
  var emptyEl = document.getElementById("board-empty");
  var countEl = document.getElementById("board-count");
  var recentEl = document.getElementById("recent");
  var recentRows = document.getElementById("recent-rows");

  function jobCard(j, withButton){
    var chips = '<span class="jchip jchip-when">' + esc(j.scheduled_human) + '</span>';
    if(j.lead_source) chips += '<span class="jchip jchip-src">' + esc(j.lead_source) + '</span>';
    chips += '<span class="jchip">' + esc(j.status) + '</span>';
    var facts = "";
    if(j.items) facts += '<div class="jf"><div class="jf-k">Load</div><div class="jf-v">' + esc(j.items) + '</div></div>';
    facts += '<div class="jf"><div class="jf-k">Customer</div><div class="jf-v">' + esc(j.customer_name)
          + (j.customer_phone ? ' · <a href="tel:' + esc(j.customer_phone) + '">' + esc(j.customer_phone) + '</a>' : '')
          + '</div></div>';
    if(j.notes) facts += '<div class="jf"><div class="jf-k">Notes</div><div class="jf-v">' + esc(j.notes) + '</div></div>';
    return '<div class="jobcard" data-id="' + esc(j.id) + '">'
      + '<div class="jobtop"><span class="jobprice">$' + Number(j.total_price || 0).toFixed(0) + '</span>'
      + '<span class="jobcode">' + esc(j.code || "") + '</span></div>'
      + '<h2 class="jobaddr">' + esc(j.address) + '</h2>'
      + '<div class="jobchips">' + chips + '</div>'
      + '<div class="jobfacts">' + facts + '</div>'
      + (withButton ? '<button class="assignbtn" type="button" data-pick="' + esc(j.id) + '">Choose a hauler →</button>' : '')
      + '</div>';
  }

  function loadBoard(){
    err("");
    api("/api/va/dispatch/board", {}, function(res){
      if(!res.ok){ err(res.j.error || "Couldn't load the board."); return; }
      var jobs = res.j.jobs || [];
      countEl.textContent = jobs.length === 1 ? "1 open job" : jobs.length + " open jobs";
      document.getElementById("bar-sub").textContent = vaName() ? "Signed in as " + vaName() : "";
      jobsEl.innerHTML = jobs.map(function(j){ return jobCard(j, true); }).join("");
      emptyEl.hidden = jobs.length !== 0;
      var recent = res.j.recent || [];
      recentEl.hidden = recent.length === 0;
      recentRows.innerHTML = recent.map(function(r){
        var what = r.action === "assign"
          ? "assigned <b>" + esc(r.job_code || "a job") + "</b> to <b>" + esc(r.hauler_name || "a hauler") + "</b>"
          : "logged phone job <b>" + esc(r.job_code || "") + "</b>";
        return '<div class="recent-row"><b>' + esc(r.va_name || "Someone") + '</b> ' + what + '</div>';
      }).join("");
      board.hidden = false; picker.hidden = true;
    });
  }

  jobsEl.addEventListener("click", function(e){
    var btn = e.target.closest("[data-pick]");
    if(btn) openPicker(btn.getAttribute("data-pick"));
  });
  document.getElementById("refresh").addEventListener("click", loadBoard);

  /* ---------- hauler picker ---------- */
  var haulersEl = document.getElementById("haulers");
  var pickerJob = document.getElementById("picker-job");
  var currentJobId = null;

  function openPicker(jobId){
    err("");
    api("/api/va/dispatch/haulers", {job_id: jobId}, function(res){
      if(!res.ok){ err(res.j.error || "Couldn't load haulers."); return; }
      currentJobId = jobId;
      pickerJob.innerHTML = jobCard(res.j.job, false);
      var haulers = res.j.haulers || [];
      if(haulers.length === 0){
        haulersEl.innerHTML = '<p class="sr-none">No approved haulers yet — approve one in the admin dashboard first.</p>';
      } else {
        haulersEl.innerHTML = haulers.map(function(h){
          var chips = "";
          if(h.is_online) chips += '<span class="hchip hchip-online">Online</span>';
          if(h.kind === "text") chips += '<span class="hchip hchip-text">Works by text</span>';
          if(h.kind === "operator") chips += '<span class="hchip hchip-operator">Fleet operator</span>';
          var meta = [];
          if(h.distance_miles != null) meta.push(h.distance_miles + " mi away");
          if(h.total_jobs) meta.push(h.total_jobs + " jobs");
          if(h.avg_rating) meta.push(h.avg_rating + "★");
          if(h.truck_type) meta.push(h.truck_type);
          return '<div class="haulrow">'
            + '<div class="haulmain"><div class="haulname">' + esc(h.name) + chips + '</div>'
            + '<div class="haulmeta">' + esc(meta.join(" · ") || "No history yet") + '</div></div>'
            + '<button class="haulbtn" type="button" data-assign="' + esc(h.id) + '">Assign</button>'
            + '</div>';
        }).join("");
      }
      board.hidden = true; picker.hidden = false;
      window.scrollTo(0, 0);
    });
  }

  document.getElementById("picker-back").addEventListener("click", function(){
    board.hidden = false; picker.hidden = true;
  });

  haulersEl.addEventListener("click", function(e){
    var btn = e.target.closest("[data-assign]");
    if(!btn) return;
    // two-tap confirm: first tap arms the button, second tap dispatches
    if(!btn.classList.contains("confirm")){
      haulersEl.querySelectorAll(".haulbtn.confirm").forEach(function(b){
        b.classList.remove("confirm"); b.textContent = "Assign";
      });
      btn.classList.add("confirm");
      btn.textContent = "Tap to confirm";
      clearTimeout(confirmTimer);
      confirmTimer = setTimeout(function(){
        btn.classList.remove("confirm"); btn.textContent = "Assign";
      }, 4000);
      return;
    }
    clearTimeout(confirmTimer);
    btn.disabled = true; btn.textContent = "Assigning…";
    api("/api/va/dispatch/assign",
        {job_id: currentJobId, contractor_id: btn.getAttribute("data-assign")},
        function(res){
      if(!res.ok){
        btn.disabled = false; btn.classList.remove("confirm"); btn.textContent = "Assign";
        err(res.j.error || "Assignment didn't go through.");
        if(res.status === 409) loadBoard();
        return;
      }
      flash(res.j.message || "Assigned.");
      loadBoard();
    });
  });

  /* ---------- log a phone job ---------- */
  var logForm = document.getElementById("log-form");
  var lgErr = document.getElementById("lg-err");
  logForm.addEventListener("submit", function(e){
    e.preventDefault();
    lgErr.hidden = true;
    var btn = document.getElementById("lg-btn");
    btn.disabled = true;
    api("/api/va/dispatch/log-job", {
      customer_name: document.getElementById("lg-name").value.trim(),
      customer_phone: document.getElementById("lg-phone").value.trim(),
      address: document.getElementById("lg-addr").value.trim(),
      price: document.getElementById("lg-price").value,
      scheduled_at: document.getElementById("lg-when").value,
      items_text: document.getElementById("lg-items").value.trim(),
      notes: document.getElementById("lg-notes").value.trim()
    }, function(res){
      btn.disabled = false;
      if(!res.ok){ lgErr.textContent = res.j.error || "Couldn't log the job."; lgErr.hidden = false; return; }
      logForm.reset();
      document.getElementById("logbox").open = false;
      flash(res.j.message || "Job added.");
      loadBoard();
    });
  });

  /* ---------- gate ---------- */
  var gateForm = document.getElementById("gate-form");
  gateForm.addEventListener("submit", function(e){
    e.preventDefault();
    var c = document.getElementById("code").value.trim();
    var v = document.getElementById("va").value.trim();
    if(!c){ gateErr.textContent = "Enter the passcode."; gateErr.hidden = false; return; }
    localStorage.setItem(KEY, c);
    if(v) localStorage.setItem(VA_KEY, v);
    gateErr.hidden = true;
    showTool();
    loadBoard();
  });

  if(code()){ showTool(); loadBoard(); }
  else showGate();
})();
"""
