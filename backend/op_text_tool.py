"""
Send Setup Link — a one-tap tool for the VA to text an interested hauler the
Umuve operator-onboarding links, sent from the platform's Twilio number.

Routes:
  GET  /optext           -> single-page tool (HTML; links same-origin css/js)
  GET  /optext/app.css   -> stylesheet
  GET  /optext/app.js    -> client script
  GET  /optext/diag      -> TEMP no-send health check (Twilio config + reachable)
  POST /api/optext/send  -> passcode-gated; sends the setup-link SMS via Twilio

Reuses sms_service.send_sms / format_phone (same Twilio number as booking SMS).
Shares the access code with the coach (TRIXIE_ASSISTANT_PASSCODE) so the VA has
ONE login. Fails CLOSED if the passcode isn't configured.
"""
from __future__ import annotations

import hmac
import logging
import os

from flask import Blueprint, Response, jsonify, request

try:
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)

optext_bp = Blueprint("optext", __name__)

APPLY_URL = "https://goumuve.com/operators"
APP_URL = "https://apps.apple.com/app/id6759131650"


def _build_message(name: str) -> str:
    greeting = "Hi {},".format(name.strip()) if name and name.strip() else "Hi there,"
    return (
        "{greeting} it's Umuve (you-move) — thanks for your interest! Get set up "
        "& start getting paid junk-removal jobs:\n"
        "1) Apply: {apply}\n"
        "2) Umuve Pro app: {app}\n"
        "3) Connect Stripe, then tap Go Online.\n"
        "Shamar will help you finish — just reply with any questions. "
        "Reply STOP to opt out."
    ).format(greeting=greeting, apply=APPLY_URL, app=APP_URL)


def _passcode_ok(supplied: str) -> bool:
    expected = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    if not expected:
        return False  # fail closed
    return hmac.compare_digest(str(supplied or ""), str(expected))


def _run(fn):
    """Run a blocking call off the eventlet green thread (native thread pool)."""
    try:
        from eventlet import tpool  # type: ignore
    except Exception:
        tpool = None
    if tpool is not None:
        return tpool.execute(fn)
    return fn()


def _twilio_from():
    return (os.environ.get("TWILIO_PHONE_NUMBER")
            or os.environ.get("TWILIO_FROM_NUMBER") or "")


_ratelimit = (
    limiter.limit("60 per hour; 12 per minute")
    if limiter is not None
    else (lambda f: f)
)


@optext_bp.route("/optext", methods=["GET"])
def optext_page():
    return Response(OPTEXT_HTML, mimetype="text/html")


@optext_bp.route("/optext/app.css", methods=["GET"])
def optext_css():
    return Response(OPTEXT_CSS, mimetype="text/css")


@optext_bp.route("/optext/app.js", methods=["GET"])
def optext_js():
    return Response(OPTEXT_JS, mimetype="application/javascript")


@optext_bp.route("/optext/diag", methods=["GET"])
def optext_diag():
    # TEMPORARY no-send health check — remove after verifying. Sends no SMS.
    info = {
        "passcode_set": bool(os.environ.get("TRIXIE_ASSISTANT_PASSCODE")),
        "from_number_set": bool(_twilio_from()),
        "sid_set": bool(os.environ.get("TWILIO_ACCOUNT_SID")),
        "token_set": bool(os.environ.get("TWILIO_AUTH_TOKEN")),
    }
    try:
        import sms_service
        client = sms_service._get_twilio()
        if client is None:
            info.update(ok=False, error="Twilio client not initialised (missing SID/token)")
            return jsonify(info)
        # read-only call: confirms creds + account are usable for messaging
        _run(lambda: client.messages.list(limit=1))
        info.update(ok=True)
    except Exception as e:
        info.update(ok=False, error=(type(e).__name__ + ": " + str(e))[:400])
    return jsonify(info)


@optext_bp.route("/api/optext/send", methods=["POST"])
@_ratelimit
def optext_send():
    if not os.environ.get("TRIXIE_ASSISTANT_PASSCODE"):
        return jsonify({"error": "Not set up yet — ask Shamar to add the access code."}), 503

    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("passcode")):
        return jsonify({"error": "That access code didn't work — double-check with Shamar."}), 401

    name = (data.get("name") or "").strip()[:80]
    raw_phone = (data.get("phone") or "").strip()

    import sms_service
    formatted = sms_service.format_phone(raw_phone)
    if not formatted or len(formatted) < 11:
        return jsonify({"error": "Enter a valid US cell number (10 digits)."}), 400

    client = sms_service._get_twilio()
    from_num = _twilio_from()
    if client is None or not from_num:
        return jsonify({"error": "Texting isn't configured yet — ask Shamar to set the Twilio number."}), 503

    body = _build_message(name)
    try:
        msg = _run(lambda: client.messages.create(body=body, from_=from_num, to=formatted))
        sid = getattr(msg, "sid", None)
        logger.info("optext sent to %s (sid=%s)", formatted, sid)
        return jsonify({"ok": True, "to": formatted, "sid": sid})
    except Exception as e:
        logger.exception("optext send failed")
        return jsonify({
            "error": "Couldn't send the text — double-check the number, or our SMS provider may be down. Try again.",
            "debug": (type(e).__name__ + ": " + str(e))[:300],
        }), 502


OPTEXT_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<title>Umuve — Send Setup Link</title>
<link rel="stylesheet" href="/optext/app.css" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="card">
      <div class="mark">U</div>
      <h1>Send Setup Link</h1>
      <p class="sub">Text an interested hauler the Umuve onboarding links in one tap.</p>
      <form id="gate-form" autocomplete="off">
        <label class="lbl" for="code">Access code</label>
        <input id="code" type="password" inputmode="text" autocomplete="off" placeholder="Enter your code" />
        <button class="btn" type="submit">Start</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
      <p class="hint">Same code as your coach. From Shamar.</p>
    </div>
  </section>

  <section id="tool" class="tool" hidden>
    <header class="bar">
      <div class="mark sm">U</div>
      <div class="bar-id">
        <div class="bar-title">Send Setup Link</div>
        <div class="bar-sub">Texts from the Umuve number</div>
      </div>
    </header>

    <div class="body">
      <form id="send-form" autocomplete="off">
        <label class="lbl" for="name">Hauler / company name <span class="opt">(optional)</span></label>
        <input id="name" type="text" placeholder="e.g. Mike at Palm Beach Haulers" />
        <label class="lbl" for="phone">Their cell number</label>
        <input id="phone" type="tel" inputmode="tel" placeholder="(561) 555-0123" />
        <button id="send" class="btn" type="submit">Text the setup link</button>
        <p id="result" class="result" hidden></p>
      </form>

      <div class="preview">
        <div class="preview-h">What they'll receive</div>
        <div class="bubble">Hi [name], it's Umuve (you-move) — thanks for your interest! Get set up &amp; start getting paid junk-removal jobs:<br>1) Apply: goumuve.com/operators<br>2) Umuve Pro app<br>3) Connect Stripe, then tap Go Online.<br>Shamar will help you finish — just reply with any questions.</div>
      </div>

      <div id="sent-wrap" class="sent-wrap" hidden>
        <div class="sent-h">Sent this session</div>
        <ul id="sent" class="sent"></ul>
      </div>
    </div>
  </section>
</div>
<script src="/optext/app.js"></script>
</body>
</html>
"""


OPTEXT_CSS = r""":root{
  --canvas:#EEF1F5; --surface:#FFFFFF; --ink:#16202C; --muted:#5B6878;
  --accent:#FF6A2C; --accent-press:#E85B1F; --line:#E3E8EE; --ok:#1FA971;
  --bot:#FFFFFF; --shadow:0 1px 2px rgba(16,32,44,.06),0 8px 24px rgba(16,32,44,.06);
  --display:ui-rounded,"SF Pro Rounded",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --body:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--canvas);color:var(--ink);font-family:var(--body);-webkit-font-smoothing:antialiased;line-height:1.45}
#app{max-width:560px;margin:0 auto;min-height:100dvh;display:flex;flex-direction:column}

.mark{font-family:var(--display);font-weight:700;color:#fff;background:#1B2A3A;width:54px;height:54px;border-radius:16px;display:grid;place-items:center;font-size:26px;position:relative;box-shadow:var(--shadow)}
.mark::after{content:"";position:absolute;right:-3px;bottom:-3px;width:18px;height:18px;border-radius:6px;background:var(--accent)}
.mark.sm{width:38px;height:38px;border-radius:11px;font-size:19px}
.mark.sm::after{width:12px;height:12px;border-radius:4px;right:-2px;bottom:-2px}

.gate{flex:1;display:flex;align-items:center;justify-content:center;padding:24px}
.card{width:100%;max-width:380px;background:var(--surface);border:1px solid var(--line);border-radius:22px;padding:32px 28px;box-shadow:var(--shadow);text-align:center}
.card .mark{margin:0 auto 18px}
h1{font-family:var(--display);font-weight:700;font-size:26px;margin:0 0 8px;letter-spacing:-.02em}
.sub{color:var(--muted);margin:0 0 24px;font-size:15px}
.lbl{display:block;text-align:left;font-family:var(--display);font-weight:600;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:14px 0 7px}
.lbl .opt{font-weight:500;letter-spacing:0;text-transform:none;color:#9aa6b2}
.card .lbl:first-of-type{margin-top:0}
input{width:100%;padding:14px 15px;font-size:16px;font-family:var(--body);color:var(--ink);background:#F6F8FA;border:1.5px solid var(--line);border-radius:13px;outline:none}
input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(255,106,44,.18);background:#fff}
.btn{width:100%;margin-top:16px;padding:15px;font-size:16px;font-family:var(--display);font-weight:600;color:#fff;background:var(--accent);border:none;border-radius:13px;cursor:pointer;transition:background .15s,transform .05s}
.btn:hover{background:var(--accent-press)}
.btn:active{transform:translateY(1px)}
.btn:disabled{background:#C7CDD4;cursor:default}
.hint{color:var(--muted);font-size:12.5px;margin:18px 0 0}
.err{color:#C0341F;font-size:13.5px;margin:12px 0 0;text-align:left}

.tool{flex:1;display:flex;flex-direction:column}
.bar{display:flex;align-items:center;gap:12px;padding:14px 18px;padding-top:max(14px,env(safe-area-inset-top));background:var(--surface);border-bottom:1px solid var(--line)}
.bar-title{font-family:var(--display);font-weight:700;font-size:17px}
.bar-sub{color:var(--muted);font-size:12.5px;margin-top:1px}
.body{padding:20px 18px max(20px,env(safe-area-inset-bottom));display:flex;flex-direction:column;gap:20px}
#send-form{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:20px 18px;box-shadow:var(--shadow)}
.result{margin:14px 0 0;padding:12px 14px;border-radius:12px;font-size:14.5px;display:none}
.result.show{display:block}
.result.ok{background:#E7F7EF;color:#0E6B45;border:1px solid #B6E6CE}
.result.bad{background:#FBEAE6;color:#B23218;border:1px solid #F1C4B8}

.preview{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:16px 18px}
.preview-h,.sent-h{font-family:var(--display);font-weight:600;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
.bubble{background:#EAF0F6;border:1px solid var(--line);border-radius:14px;border-bottom-left-radius:5px;padding:12px 14px;font-size:14px;color:#27313c;line-height:1.5}
.sent-wrap{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:16px 18px}
.sent{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.sent li{font-size:14px;color:var(--ink);display:flex;align-items:center;gap:8px}
.sent li::before{content:"✅"}

:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


OPTEXT_JS = r"""(function(){
  var API = "/api/optext/send";
  var KEY = "umuve_coach_code";   // shared login with the coach
  var gate = document.getElementById("gate");
  var tool = document.getElementById("tool");
  var gateErr = document.getElementById("gate-err");
  var nameEl = document.getElementById("name");
  var phoneEl = document.getElementById("phone");
  var sendBtn = document.getElementById("send");
  var result = document.getElementById("result");
  var sentWrap = document.getElementById("sent-wrap");
  var sentList = document.getElementById("sent");
  var busy = false;

  function code(){ return localStorage.getItem(KEY) || ""; }
  function show(el){ el.hidden = false; }

  function showTool(){ gate.hidden = true; tool.hidden = false; nameEl.focus(); }
  function showGate(msg){
    tool.hidden = true; gate.hidden = false;
    if(msg){ gateErr.textContent = msg; gateErr.hidden = false; } else { gateErr.hidden = true; }
    document.getElementById("code").focus();
  }
  function setResult(kind, text){
    result.textContent = text;
    result.className = "result show " + kind;
  }

  function send(){
    if(busy) return;
    var phone = phoneEl.value.trim();
    var name = nameEl.value.trim();
    if(!phone){ setResult("bad", "Enter their cell number first."); return; }
    busy = true; sendBtn.disabled = true; sendBtn.textContent = "Sending…";
    fetch(API, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ passcode: code(), name: name, phone: phone })
    }).then(function(r){ return r.json().then(function(j){ return {status:r.status, body:j}; }); })
    .then(function(res){
      busy = false; sendBtn.disabled = false; sendBtn.textContent = "Text the setup link";
      if(res.status === 401){ showGate("That code didn't work — double-check with Shamar."); return; }
      if(res.status >= 200 && res.status < 300 && res.body.ok){
        var label = (name ? name + " — " : "") + (res.body.to || phone);
        setResult("ok", "Sent to " + (res.body.to || phone) + " ✅");
        var li = document.createElement("li"); li.textContent = label;
        sentList.insertBefore(li, sentList.firstChild);
        show(sentWrap);
        nameEl.value = ""; phoneEl.value = ""; nameEl.focus();
      } else {
        setResult("bad", res.body.error || "Couldn't send — try again.");
      }
    }).catch(function(){
      busy = false; sendBtn.disabled = false; sendBtn.textContent = "Text the setup link";
      setResult("bad", "Couldn't reach the server — check your connection and try again.");
    });
  }

  document.getElementById("gate-form").addEventListener("submit", function(e){
    e.preventDefault();
    var v = document.getElementById("code").value.trim();
    if(!v){ gateErr.textContent = "Enter your access code."; gateErr.hidden = false; return; }
    localStorage.setItem(KEY, v);
    showTool();
  });
  document.getElementById("send-form").addEventListener("submit", function(e){ e.preventDefault(); send(); });

  if(code()){ showTool(); } else { showGate(); }
})();
"""
