"""Call Desk line — texting, browser calling, and an inbox for the VA desk.

Replaces Quo (account suspended Sep 2026). One dedicated Twilio number is
the desk's outbound caller ID and the number prospects reply to. Every
text and call in either direction lands in `desk_activities`, keyed to the
CallProspect when we know them, so the desk shows a real conversation
instead of a separate phone app.

Twilio webhooks (signature-validated, same validator as /api/sms/inbound):
  POST /api/desk/twilio/sms              inbound text/MMS on the desk line
  POST /api/desk/twilio/sms-status       delivery status for desk-sent texts
  POST /api/desk/twilio/voice            TwiML App voice URL — browser → phone
  POST /api/desk/twilio/voice/after-out  outbound dial finished (status+duration)
  POST /api/desk/twilio/voice/inbound    someone called the desk line: ring the
                                         browser AND the forward cell at once
  POST /api/desk/twilio/voice/after-in   inbound dial finished; voicemail if missed
  POST /api/desk/twilio/voice/vm-done    after the voicemail recording
  POST /api/desk/twilio/voice/transcript voicemail transcript → activity body

VA-facing (passcode-gated, same code as /va):
  POST /api/va/desk/token    Twilio Voice access token for the browser dialer
                             ({"enabled": false} until the env is set)
  POST /api/va/desk/thread   conversation for one prospect; marks it read
  POST /api/va/desk/text     free-form text from the desk line
  POST /api/va/desk/inbox    recent replies across all prospects + unread count
  POST /api/va/desk/capacity how much line is left, in texts or minutes (never $)

Env:
  DESK_TWILIO_NUMBER    E.164 desk line. Unset → texts fall back to the main
                        Umuve number (sms_service) and the dialer stays off.
  DESK_FORWARD_NUMBER   VA's cell. Rings alongside the browser on inbound
                        calls; gets a one-line ping when a prospect texts.
  DESK_FORWARD_SMS      "off" to silence the text ping (default on).
  DESK_RECORD_CALLS     "on" to record desk calls (default off).
  TWILIO_API_KEY_SID / TWILIO_API_KEY_SECRET / TWILIO_TWIML_APP_SID
                        browser calling (scripts/desk_line_setup.py makes them).
  TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN   existing.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from desk_auth import desk_identity, desk_va_name, audit, is_manager
from models import db, CallProspect, DeskActivity, DeskSetting, DeskTranscriptLine
from xml.sax.saxutils import quoteattr

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)

deskline_bp = Blueprint("deskline", __name__)

_ratelimit = (
    limiter.limit("240 per hour; 30 per minute")
    if limiter is not None
    else (lambda f: f)
)

_OPT_OUT = ("stop", "unsubscribe", "cancel", "quit", "end", "stopall")
_STATUS_WHITELIST = ("queued", "accepted", "sending", "sent", "delivered",
                     "undelivered", "failed", "read")
TEXT_MAX = 640
THREAD_LIMIT = 60
INBOX_LIMIT = 30


# ---------------------------------------------------------------------------
# Config + small helpers
# ---------------------------------------------------------------------------
def _env(name, default=""):
    return (os.environ.get(name) or default).strip()


def desk_number():
    return _env("DESK_TWILIO_NUMBER")


def forward_number():
    return _env("DESK_FORWARD_NUMBER")


def _base_url():
    return (_env("BACKEND_URL") or "https://junkos-backend.onrender.com").rstrip("/")


def _now():
    return datetime.now(timezone.utc)


def _now_naive():
    return _now().replace(tzinfo=None)


def _digits(phone):
    d = re.sub(r"\D", "", phone or "")
    return d[-10:] if len(d) >= 10 else d


def _e164(digits):
    return "+1" + digits if len(digits) == 10 else ""


def _passcode_ok(supplied):
    expected = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    if not expected:
        return False
    return hmac.compare_digest(str(supplied or ""), str(expected))


def _run(fn):
    """Run a blocking network call off the eventlet hub when present."""
    try:
        from eventlet import tpool  # type: ignore
    except Exception:
        tpool = None
    if tpool is not None:
        return tpool.execute(fn)
    return fn()


_client_cache = {}


def _client():
    sid, tok = _env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN")
    if not sid or not tok:
        return None
    key = (sid, tok)
    if key not in _client_cache:
        try:
            from twilio.rest import Client
            _client_cache.clear()
            _client_cache[key] = Client(sid, tok)
        except Exception:
            logger.exception("Twilio client init failed")
            return None
    return _client_cache[key]


def _validate():
    """Reuse the fail-safe validator from the main SMS webhook."""
    try:
        from routes.sms_webhook import _validate_twilio_signature
        return _validate_twilio_signature()
    except Exception:
        logger.exception("desk webhook validator errored; allowing request")
        return True


def _twiml(resp):
    return Response(str(resp), mimetype="text/xml")


def _empty_twiml():
    from twilio.twiml.messaging_response import MessagingResponse
    return _twiml(MessagingResponse())


def match_prospect(digits):
    """Find the prospect a number belongs to (front desk OR decision-maker cell)."""
    if len(digits) != 10:
        return None
    p = CallProspect.query.filter_by(phone_digits=digits).first()
    if p:
        return p
    tail = digits[-7:]
    for cand in (CallProspect.query
                 .filter(CallProspect.direct_phone.isnot(None),
                         CallProspect.direct_phone.like("%{}%".format(tail[:3])))
                 .limit(50).all()):
        if _digits(cand.direct_phone) == digits:
            return cand
    return None


def _append_note(existing, line):
    stamp = _now().strftime("%Y-%m-%d %H:%M")
    entry = "[{}] {}".format(stamp, line)
    return (existing + "\n" + entry) if existing else entry


# ---------------------------------------------------------------------------
# Recording activities
# ---------------------------------------------------------------------------
def record_inbound_text(from_phone, body, media_urls=None, sid=None, prospect=None):
    """Store an inbound text and wake the prospect's card. Returns the activity.

    Also called from the main /api/sms/inbound handler so replies to info
    packs sent from the Umuve number show up in the desk thread too (only
    when the sender is a known prospect — customer texts never land here).
    """
    digits = _digits(from_phone)
    if prospect is None:
        prospect = match_prospect(digits)
    lower = (body or "").strip().lower()
    first = lower.split()[0].strip(".!,") if lower else ""
    opted_out = first in _OPT_OUT

    act = DeskActivity(
        prospect_id=prospect.id if prospect else None,
        phone_digits=digits, kind="sms", direction="in",
        body=(body or "")[:2000] or None,
        media=list(media_urls or []) or None,
        twilio_sid=sid, status="opted_out" if opted_out else "received",
    )
    db.session.add(act)
    if opted_out:
        from compliance import register_opt_out  # Phase 2: STOP lands on the DNC registry
        register_opt_out(digits, source="sms_stop", note=(body or "")[:120] or None)

    if prospect:
        snippet = (body or "").replace("\n", " ").strip()[:200]
        if opted_out:
            prospect.status = "dead"
            prospect.last_outcome = "opted_out"
            prospect.next_followup_at = None
            prospect.last_note = _append_note(prospect.last_note, "OPTED OUT by text")
        else:
            prospect.last_note = _append_note(
                prospect.last_note, "THEY TEXTED: " + (snippet or "(photo)"))
            if prospect.status in ("queued", "interested", "vendor_listed", "dead") \
                    and prospect.last_outcome != "opted_out":
                if prospect.status in ("queued", "dead"):
                    prospect.status = "interested"
                # Surface on the desk right now: replies outrank the queue.
                prospect.next_followup_at = _now_naive()
    db.session.commit()
    try:
        from growth import notify_reply; notify_reply(prospect, (body or "").strip() or "(photo)")
    except Exception:
        logger.exception("notify_reply failed")
    return act


def _ping_forward(prospect, from_phone, body):
    """One-line text to the VA's cell so a reply isn't missed off-desk."""
    to = forward_number()
    if not to or _env("DESK_FORWARD_SMS", "on").lower() == "off":
        return
    who = prospect.company if prospect else "Unknown number " + (from_phone or "")
    snippet = (body or "(photo)").replace("\n", " ").strip()[:120]
    msg = "Umuve desk: {} replied — \"{}\". Answer from the desk: {}/va/calls".format(
        who, snippet, _base_url())
    send_desk_text(to, msg, log=False)


def send_desk_text(to_phone, body, prospect=None, va_name=None, log=True):
    """Send from the desk line (falls back to the main Umuve number).

    Returns the message SID or None. Never raises.
    """
    digits = _digits(to_phone)
    to = _e164(digits)
    if not to:
        return None
    # Phase 2 compliance guard: never text a number on the do-not-call list.
    from compliance import text_allowed
    ok, why = text_allowed(digits)
    if not ok:
        logger.warning("desk text to ...%s blocked: %s", digits[-4:], why)
        return None
    sid = None
    frm = desk_number()
    client = _client()
    if frm and client:
        try:
            kwargs = dict(body=body, from_=frm, to=to)
            base = _base_url()
            if base.startswith("https://"):
                kwargs["status_callback"] = base + "/api/desk/twilio/sms-status"
            msg = _run(lambda: client.messages.create(**kwargs))
            sid = msg.sid
        except Exception:
            logger.exception("desk text via %s failed", frm)
            sid = None
    else:
        import sms_service
        sid = _run(lambda: sms_service.send_sms(to, body))
    if log and sid:
        db.session.add(DeskActivity(
            prospect_id=prospect.id if prospect else None,
            phone_digits=digits, kind="sms", direction="out",
            body=body[:2000], twilio_sid=sid, status="queued",
            va_name=(va_name or None), read_at=_now_naive(),
        ))
        if prospect:
            prospect.last_texted_at = _now_naive()
        db.session.commit()
    return sid


def _log_call(direction, digits, sid, prospect=None, status="ringing", va_name=None):
    act = DeskActivity(
        prospect_id=prospect.id if prospect else None,
        phone_digits=digits, kind="call", direction=direction,
        twilio_sid=sid, status=status, va_name=va_name or None,
        read_at=_now_naive() if direction == "out" else None,
    )
    db.session.add(act)
    if prospect and direction == "out":
        prospect.last_called_at = _now_naive()
    db.session.commit()
    return act


def _finish_call(sid, dial_status, duration, missed_status="no-answer"):
    act = DeskActivity.query.filter_by(twilio_sid=sid, kind="call").first()
    if not act:
        return None
    if act.status == "vm_dropped":
        act.read_at = act.read_at or _now_naive()
    elif dial_status == "completed":
        act.status = "completed"
        act.read_at = act.read_at or _now_naive()
    else:
        act.status = missed_status if act.direction == "in" else (dial_status or "failed")
    try:
        act.duration = int(duration) if duration not in (None, "") else act.duration
    except (TypeError, ValueError):
        pass
    db.session.commit()
    return act


# ---------------------------------------------------------------------------
# Twilio webhooks — messaging
# ---------------------------------------------------------------------------
@deskline_bp.route("/api/desk/twilio/sms", methods=["POST"])
def twilio_sms_inbound():
    if not _validate():
        return Response("Forbidden", status=403)
    from_phone = request.form.get("From", "")
    body = (request.form.get("Body") or "").strip()
    try:
        n = int(request.form.get("NumMedia", 0) or 0)
    except ValueError:
        n = 0
    media = [request.form.get("MediaUrl{}".format(i), "") for i in range(n)]
    media = [m for m in media if m]
    sid = request.form.get("MessageSid") or request.form.get("SmsSid")

    if _digits(from_phone) and _digits(from_phone) == _digits(forward_number()):
        # The VA texting the desk line from her own cell — not a prospect.
        return _empty_twiml()

    try:
        prospect = match_prospect(_digits(from_phone))
        record_inbound_text(from_phone, body, media, sid=sid, prospect=prospect)
        _ping_forward(prospect, from_phone, body)
    except Exception:
        logger.exception("desk inbound sms handling failed")
        db.session.rollback()
    return _empty_twiml()


@deskline_bp.route("/api/desk/twilio/sms-status", methods=["POST"])
def twilio_sms_status():
    if not _validate():
        return Response("Forbidden", status=403)
    sid = request.form.get("MessageSid") or request.form.get("SmsSid") or ""
    status = (request.form.get("MessageStatus") or "").lower()
    if sid and status in _STATUS_WHITELIST:
        act = DeskActivity.query.filter_by(twilio_sid=sid, kind="sms").first()
        if act and FALLBACK_MARK in (act.status or ""):
            act = None          # already carried by the toll-free line; a repeat callback changes nothing
        if act:
            act.status = status
            code = None
            if status in ("failed", "undelivered"):
                code = str(request.form.get("ErrorCode") or "")[:8]
                if code:
                    act.status = status + ":" + code
            db.session.commit()
            if code in FALLBACK_CODES:
                resend_via_tollfree(act, code)
    return Response("", status=204)


# Carrier codes that mean "this line is not allowed to send", not "this
# person is unreachable". 30034 is an unregistered 10DLC number: the message
# is fine, the line is the problem, so the toll-free line carries it instead.
FALLBACK_CODES = ("30034",)
FALLBACK_MARK = ">tf"


def _fallback_suffix():
    d = _digits(desk_number())
    pretty = "({}) {}-{}".format(d[:3], d[3:6], d[6:]) if len(d) == 10 else ""
    return ("\n— Umuve desk, reply or call " + pretty) if pretty else "\n— Umuve desk"


def resend_via_tollfree(act, code):
    """A desk-line text the carrier refused goes out again from the toll-free
    line, once, with the desk number on the end so a reply or a call still
    reaches the VA (the main line mirrors replies into the desk inbox).
    Returns the new activity or None."""
    if not act or act.kind != "sms" or act.direction != "out" or not act.body:
        return None
    if FALLBACK_MARK in (act.status or "") or "— Umuve desk" in act.body:
        return None
    to = _e164(act.phone_digits)
    if not to:
        return None
    body = (act.body.rstrip() + _fallback_suffix())[:1600]
    try:
        import sms_service
        new_sid = sms_service.send_sms(to, body)
    except Exception:
        logger.exception("toll-free resend failed for %s", act.id)
        new_sid = None
    act.status = "undelivered:" + code + (FALLBACK_MARK if new_sid else "")
    if not new_sid:
        db.session.commit()
        return None
    prospect = db.session.get(CallProspect, act.prospect_id) if act.prospect_id else None
    twin = DeskActivity(prospect_id=act.prospect_id, phone_digits=act.phone_digits, kind="sms",
                        direction="out", body=body[:2000], twilio_sid=new_sid, status="queued",
                        va_name=act.va_name, read_at=_now_naive())
    db.session.add(twin)
    if prospect:
        prospect.last_texted_at = _now_naive()
    db.session.commit()
    audit("text_resent_tollfree", "activity", act.id, {"to_last4": (act.phone_digits or "")[-4:], "code": code})
    return twin


def refused_texts(hours=24):
    """Desk-line texts the carrier refused in the window that nobody has
    carried yet, one per number (the newest), skipping anyone who has since
    received a delivered text from us."""
    since = _now_naive() - timedelta(hours=hours)
    rows = (DeskActivity.query.filter(DeskActivity.kind == "sms", DeskActivity.direction == "out",
                                      DeskActivity.created_at >= since)
            .order_by(DeskActivity.created_at.desc()).all())
    delivered_after = {}
    for r in rows:                                   # newest first
        st = r.status or ""
        carried = FALLBACK_MARK in st or "— Umuve desk" in (r.body or "")
        if st in ("delivered", "sent", "read") or carried:
            delivered_after.setdefault(r.phone_digits, r.created_at)
    out, seen = [], set()
    for r in rows:
        st = r.status or ""
        if not any(("undelivered:" + c) == st or ("failed:" + c) == st for c in FALLBACK_CODES):
            continue
        if r.phone_digits in seen or not r.body or "— Umuve desk" in r.body:
            continue
        if (r.phone_digits or "")[:3] in ("800", "833", "844", "855", "866", "877", "888"):
            continue                                 # a business's toll-free line, never a customer
        later = delivered_after.get(r.phone_digits)
        if later and later >= r.created_at:
            continue
        seen.add(r.phone_digits)
        out.append(r)
    return out


def resend_refused(hours=24, apply=False):
    """Dry run by default: what would go out. With apply, sends each through
    resend_via_tollfree and reports what happened."""
    rows = refused_texts(hours)
    report = []
    for r in rows:
        item = {"activity_id": r.id, "to_last4": (r.phone_digits or "")[-4:], "va": r.va_name,
                "at": r.created_at.isoformat() if r.created_at else None,
                "body": (r.body or "")[:90]}
        if apply:
            twin = resend_via_tollfree(r, "30034")
            item["sent"] = bool(twin)
            item["new_sid"] = twin.twilio_sid if twin else None
        report.append(item)
    return {"hours": hours, "apply": apply, "count": len(report), "texts": report}


def delivery_report(hours=24):
    """Are desk-line texts actually arriving? Outbound texts in the window,
    how many the carrier refused, the code that dominates, and how many the
    toll-free line carried instead. Drives the banner on the desk."""
    since = _now_naive() - timedelta(hours=hours)
    rows = (DeskActivity.query.filter(DeskActivity.kind == "sms", DeskActivity.direction == "out",
                                      DeskActivity.created_at >= since).all())
    attempted = len(rows)
    failed = [r for r in rows if (r.status or "").startswith(("undelivered", "failed"))]
    codes = {}
    for r in failed:
        c = (r.status or "").split(":")[-1].replace(FALLBACK_MARK, "") if ":" in (r.status or "") else ""
        if c:
            codes[c] = codes.get(c, 0) + 1
    top = max(codes, key=codes.get) if codes else None
    resent = sum(1 for r in failed if FALLBACK_MARK in (r.status or ""))
    blocked = sum(1 for r in failed if any(c in (r.status or "") for c in FALLBACK_CODES))
    level = "bad" if (blocked >= 3 and attempted and blocked / attempted >= 0.25) else "ok"
    return {"hours": hours, "attempted": attempted, "undelivered": len(failed), "blocked": blocked,
            "resent": resent, "top_code": top, "level": level}


# ---------------------------------------------------------------------------
# Twilio webhooks — voice
# ---------------------------------------------------------------------------
def _record_attr():
    return {"record": "record-from-answer-dual"} if _env("DESK_RECORD_CALLS").lower() == "on" else {}


def _vm_key(va_name):
    return "vm_url:" + (va_name or "desk").strip().lower()[:60]


def voicemail_for(va_name):
    return DeskSetting.get(_vm_key(va_name))


def _slug(v):
    return re.sub(r"[^a-z0-9]+", "-", (v or "").lower())[:40]


@deskline_bp.route("/api/desk/twilio/voice", methods=["POST"])
def twilio_voice_outbound():
    """TwiML App voice URL: the browser dialer asked to call `To`."""
    if not _validate():
        return Response("Forbidden", status=403)
    from twilio.twiml.voice_response import VoiceResponse
    resp = VoiceResponse()
    va_name = (request.form.get("va_name") or "").strip()[:80]
    if request.form.get("mode") == "record_vm":
        # The VA records the voicemail that gets dropped on answering machines.
        resp.say("After the beep, record the voicemail you want left on answering machines. "
                 "Press pound when you're done.", voice="Polly.Joanna")
        resp.record(max_length=60, play_beep=True, finish_on_key="#", trim="trim-silence",
                    action=_base_url() + "/api/desk/twilio/voice/vm-recorded?va=" + quote(va_name))
        resp.hangup()
        return _twiml(resp)
    to_digits = _digits(request.form.get("To", ""))
    to = _e164(to_digits)
    frm = desk_number()
    if not to or not frm:
        resp.say("The desk line isn't set up for calling yet.")
        resp.hangup()
        return _twiml(resp)
    prospect = None
    pid = request.form.get("prospect_id")
    if pid:
        prospect = db.session.get(CallProspect, pid)
    if prospect is None:
        prospect = match_prospect(to_digits)
    parent_sid = request.form.get("CallSid") or ""
    _log_call("out", to_digits, parent_sid, prospect, va_name=va_name)
    dial = resp.dial(caller_id=frm, timeout=30,
                     action=_base_url() + "/api/desk/twilio/voice/after-out",
                     **_record_attr())
    number_kwargs = {}
    if request.form.get("amd") == "1":
        # Power dial: detect answering machines; the AMD callback drops the
        # VA's recorded voicemail into the callee leg and hangs it up.
        number_kwargs = {
            "machine_detection": "DetectMessageEnd",
            "machine_detection_timeout": 20,
            "amd_status_callback": (_base_url() + "/api/desk/twilio/voice/amd?parent=" + parent_sid
                                    + "&va=" + quote(va_name)),
            "amd_status_callback_method": "POST",
        }
    if request.form.get("copilot") == "1":
        # Two-party consent: the callee hears a recording notice before the bridge.
        number_kwargs["url"] = _base_url() + "/api/desk/twilio/voice/whisper"
    dial.number(to, **number_kwargs)
    xml = str(resp)
    if request.form.get("copilot") == "1":
        cb = _base_url() + "/api/desk/twilio/transcript-rt?parent=" + parent_sid
        start = ("<Start><Transcription statusCallbackUrl={} track=\"both_tracks\" partialResults=\"false\" "
                 "languageCode=\"en-US\" enableAutomaticPunctuation=\"true\" name={}/></Start>"
                 ).format(quoteattr(cb), quoteattr("desk-" + parent_sid))
        xml = xml.replace("<Response>", "<Response>" + start, 1)
    return Response(xml, mimetype="text/xml")


@deskline_bp.route("/api/desk/twilio/voice/whisper", methods=["POST"])
def twilio_voice_whisper():
    """Played to the callee before the bridge when Copilot is on."""
    if not _validate():
        return Response("Forbidden", status=403)
    from twilio.twiml.voice_response import VoiceResponse
    resp = VoiceResponse()
    resp.say("This call may be recorded for quality.", voice="Polly.Joanna")
    return _twiml(resp)


@deskline_bp.route("/api/desk/twilio/transcript-rt", methods=["POST"])
def twilio_transcript_rt():
    """Twilio Real-Time Transcription events → transcript lines."""
    if not _validate():
        return Response("Forbidden", status=403)
    if request.form.get("TranscriptionEvent") != "transcription-content":
        return Response("", status=204)
    parent = request.args.get("parent") or request.form.get("CallSid") or ""
    try:
        data = json.loads(request.form.get("TranscriptionData") or "{}")
    except ValueError:
        data = {}
    text = (data.get("transcript") or "").strip()
    if not parent or not text:
        return Response("", status=204)
    if (request.form.get("Final") or "true").lower() == "false":
        return Response("", status=204)
    track = "va" if (request.form.get("Track") or "").startswith("inbound") else "them"
    act = DeskActivity.query.filter_by(twilio_sid=parent, kind="call").first()
    try:
        seq = int(request.form.get("SequenceId") or 0)
    except ValueError:
        seq = 0
    db.session.add(DeskTranscriptLine(call_sid=parent, prospect_id=act.prospect_id if act else None,
                                      track=track, text=text[:2000], seq=seq))
    db.session.commit()
    return Response("", status=204)


@deskline_bp.route("/api/desk/twilio/voice/vm-recorded", methods=["POST"])
def twilio_voice_vm_recorded():
    if not _validate():
        return Response("Forbidden", status=403)
    from twilio.twiml.voice_response import VoiceResponse
    resp = VoiceResponse()
    url = request.form.get("RecordingUrl") or ""
    va = (request.args.get("va") or "").strip()[:80]
    dur = request.form.get("RecordingDuration") or "0"
    if url:
        DeskSetting.put(_vm_key(va), url)
        DeskSetting.put(_vm_key(va) + ":seconds", str(dur))
        resp.say("Saved. That voicemail will be left on answering machines when you power dial.",
                 voice="Polly.Joanna")
    else:
        resp.say("Nothing was recorded. Try again from the desk.", voice="Polly.Joanna")
    resp.hangup()
    return _twiml(resp)


@deskline_bp.route("/api/desk/twilio/voice/amd", methods=["POST"])
def twilio_voice_amd():
    """Answering-machine result for a power-dialed leg. On a machine, play the
    VA's recorded voicemail into that leg and end it; the browser leg then
    drops and the card can advance."""
    if not _validate():
        return Response("Forbidden", status=403)
    answered_by = (request.form.get("AnsweredBy") or "").lower()
    child_sid = request.form.get("CallSid") or ""
    parent_sid = request.args.get("parent") or ""
    va = (request.args.get("va") or "").strip()[:80]
    act = DeskActivity.query.filter_by(twilio_sid=parent_sid, kind="call").first() if parent_sid else None
    if act:
        act.body = ((act.body + " · ") if act.body else "") + "AMD: " + answered_by
        db.session.commit()
    if not answered_by.startswith("machine"):
        return Response("", status=204)
    vm = voicemail_for(va)
    client = _client()
    if not vm or not client or not child_sid:
        if act:
            act.status = "machine"
            db.session.commit()
        return Response("", status=204)
    try:
        twiml = "<Response><Play>{}</Play><Hangup/></Response>".format(vm)
        _run(lambda: client.calls(child_sid).update(twiml=twiml))
        if act:
            act.status = "vm_dropped"
            db.session.commit()
    except Exception:
        logger.exception("voicemail drop failed on %s", child_sid)
    return Response("", status=204)


@deskline_bp.route("/api/desk/twilio/voice/after-out", methods=["POST"])
def twilio_voice_after_out():
    if not _validate():
        return Response("Forbidden", status=403)
    _finish_call(request.form.get("CallSid"), request.form.get("DialCallStatus"),
                 request.form.get("DialCallDuration"))
    from twilio.twiml.voice_response import VoiceResponse
    resp = VoiceResponse()
    resp.hangup()
    return _twiml(resp)


def _maya_loop_risk(from_digits, minutes=10):
    """True when this caller was already handed to Maya very recently.

    Maya transfers anything she can't handle to the desk line. If nobody
    answers, the desk's own fallback hands it straight back to Maya, who
    transfers again — the caller ping-pongs and never reaches a person. One
    hand-off per caller per window; after that, take a message.
    """
    if not from_digits:
        return False
    try:
        from models_inbound import InboundCall
        from datetime import timedelta as _td
        since = _now().replace(tzinfo=None) - _td(minutes=minutes)
        return db.session.query(
            InboundCall.query
            .filter(InboundCall.phone_digits == from_digits,
                    InboundCall.disposition == "to_maya",
                    InboundCall.created_at >= since)
            .exists()).scalar()
    except Exception:
        logger.exception("maya loop check failed for %s", from_digits)
        return False


@deskline_bp.route("/api/desk/twilio/voice/inbound", methods=["POST"])
def twilio_voice_inbound():
    """Someone called the desk line: ring the browser and the VA's cell together."""
    if not _validate():
        return Response("Forbidden", status=403)
    from twilio.twiml.voice_response import VoiceResponse
    resp = VoiceResponse()
    from_digits = _digits(request.form.get("From", ""))
    prospect = match_prospect(from_digits)
    call_sid = request.form.get("CallSid")
    act = _log_call("in", from_digits, call_sid, prospect)

    fwd = forward_number()
    import inbound
    if not inbound.inbound_enabled():
        # Legacy line: browser + cell together, voicemail on a miss.
        dial = resp.dial(timeout=25, action=_base_url() + "/api/desk/twilio/voice/after-in",
                         **_record_attr())
        dial.client("desk")
        if fwd:
            dial.number(fwd)
        return _twiml(resp)

    # Phase 6: customers (LSA) ring the humans first, Maya second.
    kind = "prospect" if prospect else inbound.classify_caller(from_digits)[0]
    in_hours = inbound.in_human_hours()
    # Which number they dialled tells us the channel (leads.py): a call on the
    # Google-ads number is a paid lead and is treated as one from the first ring.
    from leads import source_for_number
    source = source_for_number(request.form.get("To", ""))
    try:
        inbound.record_call(call_sid, from_digits, kind, in_hours=1 if in_hours else 0,
                            disposition="ringing", source=source)
    except Exception:
        logger.exception("inbound_calls insert failed for %s", call_sid)
        db.session.rollback()
    resp.say("Thanks for calling Umuve.", voice="Polly.Joanna")
    if in_hours or (source in inbound.PAID_SOURCES and inbound.humans_online()):
        # a paid lead rings a clocked-in human even outside the posted hours
        dial = resp.dial(timeout=inbound.ring_seconds(),
                         action=_base_url() + "/api/desk/twilio/voice/after-in",
                         **_record_attr())
        for identity in inbound.ring_identities():
            dial.client(identity)
        if fwd:
            dial.number(fwd)
        return _twiml(resp)
    # Outside human hours: offer a person first, Maya second.
    if inbound.maya_fallback_enabled() and not _maya_loop_risk(from_digits):
        if inbound.callback_menu_enabled():
            inbound.touch_call(call_sid, disposition="choice")
            inbound.choice_twiml(resp, _base_url())
            return _twiml(resp)
        act.status = "to_maya"
        db.session.commit()
        inbound.touch_call(call_sid, disposition="to_maya")
        inbound.maya_twiml(resp, _base_url())
        return _twiml(resp)
    act.status = "voicemail"
    db.session.commit()
    inbound.touch_call(call_sid, disposition="voicemail")
    inbound.voicemail_twiml(resp, _base_url())
    return _twiml(resp)


@deskline_bp.route("/api/desk/twilio/voice/after-in", methods=["POST"])
def twilio_voice_after_in():
    if not _validate():
        return Response("Forbidden", status=403)
    from twilio.twiml.voice_response import VoiceResponse
    resp = VoiceResponse()
    status = request.form.get("DialCallStatus")
    call_sid = request.form.get("CallSid")
    duration = request.form.get("DialCallDuration")
    act = _finish_call(call_sid, status, duration)
    import inbound
    phase6 = inbound.inbound_enabled()
    if status == "completed":
        if phase6 and act:
            act.status = "answered_by_human"
            db.session.commit()
            try:
                inbound.touch_call(call_sid, disposition="answered_by_human",
                                   duration=int(duration) if duration else None,
                                   answered_by=(request.form.get("DialCallTo") or "")[:80] or None)
            except Exception:
                logger.exception("inbound_calls update failed for %s", call_sid)
                db.session.rollback()
        resp.hangup()
        return _twiml(resp)
    if phase6 and inbound.maya_fallback_enabled() and not _maya_loop_risk(_digits(request.form.get("From", ""))):
        # Nobody picked up. Ask what they'd rather have before assuming a robot.
        if inbound.callback_menu_enabled():
            inbound.touch_call(call_sid, disposition="choice")
            inbound.choice_twiml(resp, _base_url())
            return _twiml(resp)
        if act:
            act.status = "to_maya"
            db.session.commit()
        inbound.touch_call(call_sid, disposition="to_maya")
        inbound.maya_twiml(resp, _base_url())
        return _twiml(resp)
    if act:
        act.status = "voicemail"
        db.session.commit()
    if phase6:
        inbound.touch_call(call_sid, disposition="voicemail")
    resp.say("You've reached Umuve. Leave your name, number, and what you need, "
             "and we'll call you right back.", voice="Polly.Joanna")
    resp.record(max_length=120, play_beep=True, transcribe=True,
                transcribe_callback=_base_url() + "/api/desk/twilio/voice/transcript",
                action=_base_url() + "/api/desk/twilio/voice/vm-done")
    resp.hangup()
    return _twiml(resp)


@deskline_bp.route("/api/desk/twilio/voice/choice", methods=["POST"])
def twilio_voice_choice():
    """What the caller pressed when nobody picked up.

    1 → a person calls them back (a real desk task, not a text).
    2 → Maya.
    nothing → ask once more, then Maya, so this is never worse than before.
    """
    if not _validate():
        return Response("Forbidden", status=403)
    from twilio.twiml.voice_response import VoiceResponse
    import inbound
    resp = VoiceResponse()
    digits_pressed = (request.form.get("Digits") or "").strip()
    call_sid = request.form.get("CallSid")
    from_digits = _digits(request.form.get("From", ""))
    try:
        attempt = int(request.args.get("attempt") or 0)
    except ValueError:
        attempt = 0
    act = DeskActivity.query.filter_by(twilio_sid=call_sid, kind="call").first()

    if digits_pressed == "1":
        source = None
        try:
            from leads import source_for_number
            source = source_for_number(request.form.get("To", ""))
        except Exception:
            pass
        try:
            inbound.record_phone_callback(from_digits, call_sid, source)
        except Exception:
            logger.exception("phone callback capture failed for %s", call_sid)
            db.session.rollback()
        if act:
            act.status = "callback"
            db.session.commit()
        inbound.touch_call(call_sid, disposition="callback_menu", outcome="callback")
        inbound.callback_confirm_twiml(resp)
        return _twiml(resp)

    if digits_pressed != "2" and attempt + 1 < inbound.CHOICE_ATTEMPTS:
        # Silence or a stray key — ask once more, shorter.
        inbound.choice_twiml(resp, _base_url(), attempt=attempt + 1)
        return _twiml(resp)

    if inbound.maya_fallback_enabled() and not _maya_loop_risk(from_digits):
        if act:
            act.status = "to_maya"
            db.session.commit()
        inbound.touch_call(call_sid, disposition="to_maya")
        inbound.maya_twiml(resp, _base_url())
        return _twiml(resp)
    if act:
        act.status = "voicemail"
        db.session.commit()
    inbound.touch_call(call_sid, disposition="voicemail")
    inbound.voicemail_twiml(resp, _base_url())
    return _twiml(resp)


@deskline_bp.route("/api/desk/twilio/voice/after-maya", methods=["POST"])
def twilio_voice_after_maya():
    """The Maya leg ended. A clean hand-off hangs up; if her line didn't
    answer, the caller still gets the mailbox instead of dead air."""
    if not _validate():
        return Response("Forbidden", status=403)
    from twilio.twiml.voice_response import VoiceResponse
    import inbound
    resp = VoiceResponse()
    status = request.form.get("DialCallStatus")
    call_sid = request.form.get("CallSid")
    duration = request.form.get("DialCallDuration")
    if status == "completed":
        try:
            inbound.touch_call(call_sid, disposition="to_maya",
                               duration=int(duration) if duration else None)
        except Exception:
            db.session.rollback()
        resp.hangup()
        return _twiml(resp)
    act = DeskActivity.query.filter_by(twilio_sid=call_sid, kind="call").first()
    if act:
        act.status = "voicemail"
        db.session.commit()
    inbound.touch_call(call_sid, disposition="voicemail")
    inbound.voicemail_twiml(resp, _base_url())
    return _twiml(resp)


@deskline_bp.route("/api/desk/twilio/voice/vm-done", methods=["POST"])
def twilio_voice_vm_done():
    if not _validate():
        return Response("Forbidden", status=403)
    act = DeskActivity.query.filter_by(twilio_sid=request.form.get("CallSid"), kind="call").first()
    url = request.form.get("RecordingUrl")
    if act and url:
        act.recording_url = url[:300]
        act.status = "voicemail"
        db.session.commit()
    from twilio.twiml.voice_response import VoiceResponse
    resp = VoiceResponse()
    resp.say("Thanks. We'll be in touch.", voice="Polly.Joanna")
    resp.hangup()
    return _twiml(resp)


@deskline_bp.route("/api/desk/twilio/voice/transcript", methods=["POST"])
def twilio_voice_transcript():
    if not _validate():
        return Response("Forbidden", status=403)
    act = DeskActivity.query.filter_by(twilio_sid=request.form.get("CallSid"), kind="call").first()
    if act is None:
        # Twilio's transcription callback does not always carry the CallSid
        # we stored; the recording it belongs to is the surer key.
        rec_sid = (request.form.get("RecordingSid") or "").strip()
        rec_url = (request.form.get("RecordingUrl") or "").strip()
        needle = rec_sid or rec_url
        if needle:
            act = (DeskActivity.query.filter(DeskActivity.kind == "call",
                                             DeskActivity.recording_url.isnot(None),
                                             DeskActivity.recording_url.contains(needle))
                   .order_by(DeskActivity.created_at.desc()).first())
    text = (request.form.get("TranscriptionText") or "").strip()
    if act:
        if text:
            act.body = text[:2000]
        url = request.form.get("RecordingUrl")
        if url and not act.recording_url:
            act.recording_url = url[:300]
        act.status = "voicemail"
        db.session.commit()
        prospect = db.session.get(CallProspect, act.prospect_id) if act.prospect_id else None
        if text:
            _ping_forward(prospect, _e164(act.phone_digits), "Voicemail: " + text)
        try:
            from growth import notify_reply; notify_reply(prospect, "Voicemail: " + (text or "(no transcript)"))
        except Exception:
            logger.exception("notify_reply failed")
    return Response("", status=204)


# ---------------------------------------------------------------------------
# VA-facing API
# ---------------------------------------------------------------------------
def voice_config():
    need = ("TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET",
            "TWILIO_TWIML_APP_SID", "DESK_TWILIO_NUMBER")
    missing = [k for k in need if not _env(k)]
    return missing


@deskline_bp.route("/api/va/desk/token", methods=["POST"])
@_ratelimit
def desk_token():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    missing = voice_config()
    if missing:
        return jsonify({"enabled": False,
                        "reason": "Browser calling isn't set up yet — tap the number to "
                                  "call from your phone.",
                        "missing": missing}), 200
    try:
        from twilio.jwt.access_token import AccessToken
        from twilio.jwt.access_token.grants import VoiceGrant
        ttl = 3600
        # Per-VA identity (desk-<slug>) so inbound calls can ring exactly the
        # people on the clock; the legacy shared "desk" stays the fallback.
        try:
            from inbound import client_identity
            identity = client_identity(ident.get("name"))
        except Exception:
            identity = "desk"
        # The iOS desk app registers the same identity, so the inbound <Dial>
        # rings it with no change to the ring logic. What it needs beyond the
        # browser is a push credential: without it the SDK can't wake the app
        # for a call while the phone is locked, which is the whole point of a
        # native desk. TWILIO_IOS_PUSH_CREDENTIAL_SID comes from Twilio Console
        # after uploading the Apple VoIP Services certificate.
        platform = (data.get("platform") or "web").strip().lower()
        push_sid = _env("TWILIO_IOS_PUSH_CREDENTIAL_SID") if platform == "ios" else ""
        token = AccessToken(_env("TWILIO_ACCOUNT_SID"), _env("TWILIO_API_KEY_SID"),
                            _env("TWILIO_API_KEY_SECRET"), identity=identity, ttl=ttl)
        token.add_grant(VoiceGrant(outgoing_application_sid=_env("TWILIO_TWIML_APP_SID"),
                                   incoming_allow=True,
                                   push_credential_sid=push_sid or None))
        jwt = token.to_jwt()
        if isinstance(jwt, bytes):
            jwt = jwt.decode("utf-8")
        out = {"enabled": True, "token": jwt, "ttl": ttl, "identity": identity,
               "desk_number": desk_number(), "platform": platform}
        if platform == "ios":
            # Honest about what the token can do: an iOS token with no push
            # credential works only while the app is in the foreground.
            out["push"] = bool(push_sid)
            if not push_sid:
                out["push_reason"] = ("TWILIO_IOS_PUSH_CREDENTIAL_SID not set — the app "
                                      "will not ring while locked")
        return jsonify(out), 200
    except Exception:
        logger.exception("desk token build failed")
        return jsonify({"enabled": False,
                        "reason": "Browser calling hit an error — tap the number to "
                                  "call from your phone."}), 200


def _thread_query(p):
    from sqlalchemy import or_
    conds = [DeskActivity.prospect_id == p.id]
    if len(p.phone_digits or "") == 10:
        conds.append(DeskActivity.phone_digits == p.phone_digits)
    direct = _digits(p.direct_phone) if p.direct_phone else ""
    if len(direct) == 10:
        conds.append(DeskActivity.phone_digits == direct)
    return DeskActivity.query.filter(or_(*conds))


def thread_for(p, mark_read=True):
    rows = (_thread_query(p).order_by(DeskActivity.created_at.desc())
            .limit(THREAD_LIMIT).all())
    rows.reverse()
    if mark_read:
        now = _now_naive()
        dirty = False
        for r in rows:
            if r.direction == "in" and r.read_at is None:
                r.read_at = now
                dirty = True
        if dirty:
            db.session.commit()
    return [r.to_dict() for r in rows]


@deskline_bp.route("/api/va/desk/thread", methods=["POST"])
@_ratelimit
def desk_thread():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    return jsonify({"prospect_id": p.id, "messages": thread_for(p),
                    "desk_number": desk_number() or None,
                    "unread": unread_count()}), 200


@deskline_bp.route("/api/va/desk/text", methods=["POST"])
@_ratelimit
def desk_text():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Type the message first."}), 400
    if len(body) > TEXT_MAX:
        return jsonify({"error": "Keep it under {} characters.".format(TEXT_MAX)}), 400
    if p.last_outcome == "opted_out":
        return jsonify({"error": "They texted STOP — we can't message this number."}), 409
    to = (data.get("to") or "").strip()
    digits = _digits(to) if to else (_digits(p.direct_phone) if p.direct_phone else p.phone_digits)
    if len(digits or "") != 10:
        return jsonify({"error": "That doesn't look like a valid US number."}), 400
    va_name = desk_va_name(data)
    from compliance import text_allowed
    ok, why = text_allowed(digits)
    if not ok:
        return jsonify({"error": "Can't text this number — it's {}.".format(why)}), 409
    sid = send_desk_text(digits, body, prospect=p, va_name=va_name)
    if not sid:
        return jsonify({"error": "The text didn't go through — texting may be down, "
                                 "or that's not a textable number."}), 502
    audit("text", "prospect", p.id, {"to_last4": digits[-4:], "chars": len(body)})
    return jsonify({"ok": True, "sid": sid, "to": "(...) " + digits[-4:],
                    "messages": thread_for(p)}), 200


@deskline_bp.route("/api/va/desk/templates", methods=["POST"])
@_ratelimit
def desk_templates():
    """Canned texts for the composer — server-side copy the VA can edit before sending."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found — reload the page."}), 404
    va_name = desk_va_name(data)
    from va_calls import followup_text_for, info_text_for
    return jsonify({
        "intro": followup_text_for("voicemail", p, va_name),
        "info": info_text_for(p, va_name),
        "followup": followup_text_for("interested", p, va_name),
    }), 200


@deskline_bp.route("/api/va/desk/voicemail", methods=["POST"])
@_ratelimit
def desk_voicemail():
    """{"action": "status"|"clear"} — the VA's recorded voicemail-drop."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    va = (data.get("va_name") or "").strip()[:80]
    if (data.get("action") or "status") == "clear":
        DeskSetting.put(_vm_key(va), None)
        DeskSetting.put(_vm_key(va) + ":seconds", None)
        audit("voicemail_cleared", "va", va)
    url = voicemail_for(va)
    secs = DeskSetting.get(_vm_key(va) + ":seconds")
    return jsonify({"has_voicemail": bool(url), "seconds": int(secs) if secs else None,
                    "play_url": (url + ".mp3") if url else None}), 200


@deskline_bp.route("/api/va/desk/last-call", methods=["POST"])
@_ratelimit
def desk_last_call():
    """Most recent outbound call on this prospect — the power dialer reads its
    status (vm_dropped / machine / completed / no-answer) to decide what to do next."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found."}), 404
    act = (_thread_query(p).filter(DeskActivity.kind == "call", DeskActivity.direction == "out")
           .order_by(DeskActivity.created_at.desc()).first())
    return jsonify({"call": act.to_dict() if act else None}), 200


def _last_out_call(p):
    return (_thread_query(p).filter(DeskActivity.kind == "call", DeskActivity.direction == "out")
            .order_by(DeskActivity.created_at.desc()).first())


@deskline_bp.route("/api/va/desk/transcript", methods=["POST"])
@_ratelimit
def desk_transcript():
    """Lines for this prospect's latest outbound call, plus a live cue when
    their last sentence trips an objection trigger."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found."}), 404
    act = _last_out_call(p)
    if not act or not act.twilio_sid:
        return jsonify({"call_sid": None, "lines": [], "cue": None}), 200
    try:
        after = int(data.get("after_seq") or -1)
    except (TypeError, ValueError):
        after = -1
    q = DeskTranscriptLine.query.filter_by(call_sid=act.twilio_sid)
    all_lines = q.order_by(DeskTranscriptLine.seq.asc(), DeskTranscriptLine.created_at.asc()).all()
    new = [l.to_dict() for l in all_lines if l.seq > after]
    from call_kit import build_kit, detect_side
    from copilot import cue_for
    side = data.get("side") if data.get("side") in ("supply", "demand") else detect_side(p)
    kit = build_kit(p, va_name=desk_va_name(data), side=side)
    cue = cue_for([l.to_dict() for l in all_lines], kit, side)
    return jsonify({"call_sid": act.twilio_sid, "status": act.status, "lines": new,
                    "total": len(all_lines), "cue": cue}), 200


@deskline_bp.route("/api/va/desk/summarize", methods=["POST"])
@_ratelimit
def desk_summarize():
    """After the call: note + suggested outcome from the transcript. Nothing is logged here."""
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    p = db.session.get(CallProspect, data.get("prospect_id") or "")
    if not p:
        return jsonify({"error": "Prospect not found."}), 404
    act = _last_out_call(p)
    lines = []
    if act and act.twilio_sid:
        lines = [l.to_dict() for l in DeskTranscriptLine.query.filter_by(call_sid=act.twilio_sid)
                 .order_by(DeskTranscriptLine.seq.asc(), DeskTranscriptLine.created_at.asc()).all()]
    from call_kit import detect_side
    from copilot import summarize
    side = data.get("side") if data.get("side") in ("supply", "demand") else detect_side(p)
    res = _run(lambda: summarize(lines, p, side))
    res["lines"] = len(lines)
    if act and lines and not act.body:
        # keep the transcript on the call itself so the thread has it
        act.body = "Transcript: " + " ".join(
            ("[them] " if l["track"] == "them" else "[you] ") + l["text"] for l in lines)[:1900]
        db.session.commit()
    if act and lines:
        try:
            from coaching import score_call_async; score_call_async(act, lines, p)
        except Exception:
            logger.exception("coaching hook failed")
    return jsonify(res), 200


def unread_count():
    return DeskActivity.query.filter(DeskActivity.direction == "in",
                                     DeskActivity.read_at.is_(None)).count()


_NO_TRANSCRIPT = "(no transcript)"


def fill_transcript(act):
    """Fetch a voicemail's transcript from Twilio when the callback never
    landed. Returns the text, or None. Writes what it finds so the next
    inbox load is free; a recording Twilio could not transcribe is marked
    so it is not asked about again."""
    if not act or not act.recording_url or act.body:
        return act.body if act else None
    m = re.search(r"/Recordings/(RE[0-9a-f]{32})", act.recording_url)
    client = _client()
    if not m or client is None:
        return None
    try:
        trs = client.recordings(m.group(1)).transcriptions.list(limit=1)
    except Exception as e:
        logger.warning("transcript pull failed for %s: %s", act.id, e)
        return None
    if not trs:
        return None
    tr = trs[0]
    status = (getattr(tr, "status", "") or "").lower()
    text = (getattr(tr, "transcription_text", "") or "").strip()
    if status == "completed" and text:
        act.body = text[:2000]
    elif status in ("failed", "completed"):
        act.body = _NO_TRANSCRIPT
    else:
        return None                      # still in progress; ask again later
    db.session.commit()
    return act.body


def _voicemail_text(act, pulls):
    """The transcript on the row, pulled from Twilio if the callback missed
    and the budget allows. Never the placeholder."""
    body = act.body
    if not body and pulls[0] > 0:
        pulls[0] -= 1
        body = fill_transcript(act)
    return None if (not body or body == _NO_TRANSCRIPT) else body



@deskline_bp.route("/api/va/desk/inbox", methods=["POST"])
@_ratelimit
def desk_inbox():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    since = (_now() - timedelta(days=30)).replace(tzinfo=None)
    rows = (DeskActivity.query
            .filter(DeskActivity.direction == "in", DeskActivity.created_at >= since)
            .order_by(DeskActivity.created_at.desc()).limit(300).all())
    seen, items = {}, []
    pulls = [3]        # at most three Twilio round-trips per inbox load
    for r in rows:
        key = r.phone_digits
        if key in seen:
            if r.read_at is None:
                seen[key]["unread"] += 1
            # Rows are newest first, so the first recording we meet for a
            # number is their latest voicemail — even when a later call from
            # them rang out without one.
            if r.kind == "call" and r.recording_url and not seen[key].get("recording_id"):
                seen[key]["recording_id"] = r.id
                seen[key]["voicemail_at"] = r.created_at.isoformat() if r.created_at else None
                text = _voicemail_text(r, pulls)
                seen[key]["voicemail_text"] = text
                if seen[key]["preview"] in ("Missed call", "Call", "Voicemail"):
                    seen[key]["preview"] = ("Voicemail: " + text)[:160] if text else "Voicemail"
            continue
        p = db.session.get(CallProspect, r.prospect_id) if r.prospect_id else None
        if r.kind == "call":
            text = _voicemail_text(r, pulls) if r.recording_url else None
            preview = ("Voicemail: " + text) if text else (
                "Voicemail" if r.recording_url else
                "Missed call" if r.status in ("no-answer", "voicemail", "busy") else "Call")
        else:
            preview = r.body or ("Photo" if r.media else "")
        item = {
            "phone_digits": key,
            "phone": "({}) {}-{}".format(key[:3], key[3:6], key[6:]) if len(key) == 10 else key,
            "prospect_id": p.id if p else None,
            "company": p.company if p else None,
            "city": p.city if p else None,
            "preview": preview[:160],
            "kind": r.kind,
            "unread": 0 if r.read_at else 1,
            "at": r.created_at.isoformat() if r.created_at else None,
            "recording_id": r.id if (r.kind == "call" and r.recording_url) else None,
            "voicemail_text": text if (r.kind == "call" and r.recording_url) else None,
            "voicemail_at": (r.created_at.isoformat() if r.created_at else None)
                            if (r.kind == "call" and r.recording_url) else None,
        }
        seen[key] = item
        items.append(item)
        if len(items) >= INBOX_LIMIT:
            break
    return jsonify({"items": items, "unread": unread_count(),
                    "desk_number": desk_number() or None}), 200


@deskline_bp.route("/api/va/desk/recording/<act_id>", methods=["GET"])
@_ratelimit
def desk_recording(act_id):
    """Stream a voicemail to the desk.

    Twilio keeps recordings behind the account's auth token, so a link to
    the recording URL plays nothing in a browser. This fetches it with the
    token server-side and hands the audio to a signed-in VA. It is a GET so
    an <audio> element can be fed from a blob; passcode users pass ?code=.
    """
    ident = desk_identity({"code": request.args.get("code")})
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    act = db.session.get(DeskActivity, act_id or "")
    if not act or not act.recording_url:
        return jsonify({"error": "No recording on that call."}), 404
    url = act.recording_url
    if not url.startswith("https://api.twilio.com/"):
        return jsonify({"error": "That recording is not on Twilio."}), 404
    sid, tok = _env("TWILIO_ACCOUNT_SID"), _env("TWILIO_AUTH_TOKEN")
    if not sid or not tok:
        return jsonify({"error": "Twilio is not configured."}), 503
    import requests as _rq
    try:
        r = _rq.get(url if url.endswith(".mp3") else url + ".mp3", auth=(sid, tok), timeout=30)
    except Exception as e:
        logger.warning("voicemail fetch failed for %s: %s", act_id, e)
        return jsonify({"error": "Couldn't reach the recording."}), 502
    if r.status_code != 200:
        return jsonify({"error": "Twilio returned {}.".format(r.status_code)}), 502
    if act.read_at is None:
        act.read_at = _now().replace(tzinfo=None)
        db.session.commit()
    return Response(r.content, status=200, headers={
        "Content-Type": "audio/mpeg", "Cache-Control": "private, max-age=300",
        "Content-Disposition": "inline; filename=voicemail-{}.mp3".format(act.phone_digits or act_id)})


@deskline_bp.route("/api/va/desk/unread", methods=["POST"])
@_ratelimit
def desk_unread():
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    return jsonify({"unread": unread_count()}), 200


@deskline_bp.route("/api/va/desk/capacity", methods=["POST"])
@_ratelimit
def desk_capacity_left():
    """How much line is left, in texts or minutes — never in dollars.

    The VA needs to know whether the desk will last the shift; the account
    balance is the owner's business, so only units cross this line. Texts and
    minutes share one balance, so they read as alternatives, not two pools.
    """
    data = request.get_json(silent=True) or {}
    ident = desk_identity(data)
    if not ident:
        return jsonify({"error": "Sign in to the desk first."}), 401
    try:
        from twilio_capacity import desk_capacity, summary_line
        cap = desk_capacity()
    except Exception:
        logger.exception("desk capacity check failed")
        return jsonify({"ok": False, "texts": None, "minutes": None, "level": "unknown", "label": ""}), 200
    try:
        delivery = delivery_report(24)
    except Exception:
        logger.exception("delivery report failed")
        delivery = None
    return jsonify({"ok": bool(cap.get("ok")), "texts": cap.get("texts"),
                    "minutes": cap.get("minutes"), "level": cap.get("level"),
                    "label": summary_line(cap), "checked_at": cap.get("checked_at"),
                    "delivery": delivery}), 200
