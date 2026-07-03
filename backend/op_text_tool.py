"""
Send Setup Link — a one-tap tool for the VA to text an interested hauler the
Umuve operator-onboarding links, sent from the platform's Twilio number.

Routes:
  GET  /optext           -> single-page tool (HTML; links same-origin css/js)
  GET  /optext/app.css   -> stylesheet
  GET  /optext/app.js    -> client script
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

    # Register the hauler as a concierge operator in the same tap — they start
    # receiving SMS job offers immediately, no app required. Idempotent; an
    # app-registered number is left alone. The setup link below still goes out
    # so they can graduate to the full app + instant payouts when ready.
    concierge_status = None
    try:
        from recruiter import register_concierge
        res = register_concierge(formatted, name=name, source="optext",
                                 send_welcome=False)
        concierge_status = res.get("status")
        logger.info("optext concierge register for %s: %s", formatted, concierge_status)
    except Exception:
        logger.exception("optext concierge register failed for %s", formatted)

    body = _build_message(name)
    try:
        msg = _run(lambda: client.messages.create(body=body, from_=from_num, to=formatted))
        sid = getattr(msg, "sid", None)
        logger.info("optext sent to %s (sid=%s)", formatted, sid)
        return jsonify({"ok": True, "to": formatted, "sid": sid,
                        "concierge": concierge_status})
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
<meta name="theme-color" content="#0B0E12" />
<title>Umuve — Setup Link</title>
<link rel="stylesheet" href="/va/app.css" />
<link rel="stylesheet" href="/optext/app.css" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="gatewrap">
      <img class="brand-lg rv" src="/va/logo.png" alt="Umuve" />
      <div class="eyebrow rv">Internal · VA suite</div>
      <h1 class="display" aria-label="Setup link">SETUP&nbsp;LINK</h1>
      <p class="sub rv">They said YES — this text signs them up to get jobs.</p>
      <form id="gate-form" autocomplete="off" class="rv">
        <label class="lbl" for="code">Access code</label>
        <input id="code" type="password" autocomplete="off" placeholder="Enter your code" />
        <button class="btn" type="submit">Start</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
      <p class="hint rv">Same code as your coach. From Shamar.</p>
    </div>
  </section>

  <section id="tool" class="tool" hidden>
    <header class="bar">
      <a class="back" href="/va" aria-label="Back to VA tools">←</a>
      <img class="brand" src="/va/logo.png" alt="Umuve" />
      <div class="bar-sub">Texts send from the Umuve number</div>
    </header>

    <div class="body">
      <h2 class="display display-sm" aria-label="They said yes">THEY SAID&nbsp;YES</h2>
      <form id="send-form" autocomplete="off" class="rv">
        <label class="lbl" for="name">Hauler / company name <span class="opt">(optional)</span></label>
        <input id="name" type="text" placeholder="e.g. Mike at Palm Beach Haulers" />
        <label class="lbl" for="phone">Their cell number</label>
        <input id="phone" type="tel" inputmode="tel" placeholder="(561) 555-0123" />
        <button id="send" class="btn" type="submit">Text the setup link</button>
        <p id="result" class="result" hidden></p>
      </form>

      <div class="preview rv">
        <div class="preview-h">What they&rsquo;ll receive</div>
        <div class="bubble">Hi [name], it&rsquo;s Umuve (you-move) — thanks for your interest! Get set up &amp; start getting paid junk-removal jobs:
1) Apply: goumuve.com/operators
2) Umuve Pro app
3) Connect Stripe, then tap Go Online.
Shamar will help you finish — just reply with any questions.</div>
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


OPTEXT_CSS = r"""/* Design system lives in /va/app.css (single source). This file keeps the
route alive for cached clients and holds optext-only tweaks. */
.bar .brand{margin-right:auto}
"""


OPTEXT_JS = r"""(function(){
  var API = "/api/optext/send";
  var KEY = "umuve_coach_code";   // shared login with the coach + /va tools
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
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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
      scope.querySelectorAll(".display-sm").forEach(function(d){ d.classList.add("uline"); });
      return;
    }
    scope.querySelectorAll(".display").forEach(splitChars);
    scope.querySelectorAll(".display .ch").forEach(function(c, i){
      setTimeout(function(){ c.classList.add("in"); }, 40 + i * 26);
    });
    scope.querySelectorAll(".rv").forEach(function(b, i){
      setTimeout(function(){ b.classList.add("in"); }, 140 + i * 65);
    });
    scope.querySelectorAll(".display-sm").forEach(function(d){
      setTimeout(function(){ d.classList.add("uline"); }, 200);
    });
  }

  function code(){ return localStorage.getItem(KEY) || ""; }
  function show(el){ el.hidden = false; }
  function showTool(){ gate.hidden = true; tool.hidden = false; reveal(tool); nameEl.focus(); }
  function showGate(msg){
    tool.hidden = true; gate.hidden = false; reveal(gate);
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
