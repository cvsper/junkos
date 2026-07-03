"""VA Tools Hub — one place for the VAs, organized by SITUATION not by tool.

Born from Tracy's 2026-07-03 suggestion: she needed a voicemail follow-up text
that is distinct from the setup-link text, "so there is no mix up." The hub
makes the distinction physical — you pick the situation you're in, and the
right text is the only one you can send from there.

Routes:
  GET  /va             -> hub: situation cards (gate shares the coach passcode)
  GET  /va/text        -> category sender (?t=voicemail|info preselects)
  GET  /va/app.css     -> stylesheet (same design system as /optext)
  GET  /va/app.js      -> client script
  POST /api/va/send    -> passcode-gated; template WHITELIST (server-side text
                          only — the client picks a category, never free text)

Unlike /optext, sending here does NOT register the lead as a concierge
operator: these are pre-consent touches (no-answer follow-ups, info requests).
Registration keeps happening only on the setup-link path after a YES.
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

vahub_bp = Blueprint("vahub", __name__)


def _greet(name):
    return "Hi {},".format(name.strip()) if name and name.strip() else "Hi there,"


def _from_line(va_name):
    v = (va_name or "").strip()
    return "this is {} with Umuve".format(v) if v else "it's Umuve"


def build_va_message(template, name, va_name):
    """Server-side template whitelist. Returns None for unknown templates."""
    if template == "voicemail":
        return (
            "{greet} {frm} — just left you a voicemail. We send paying "
            "junk-removal jobs in Palm Beach County to local haulers: you keep "
            "~72% plus 100% of tips, no fees, jobs come by text and you only "
            "take the ones you want. Worth a quick chat? Reply YES and I'll "
            "send your 2-min setup link. Reply STOP to opt out."
        ).format(greet=_greet(name), frm=_from_line(va_name))
    if template == "info":
        return (
            "{greet} {frm} — the info you asked for: we text you paid "
            "junk-removal jobs in Palm Beach County. You keep ~72% of the job "
            "price plus 100% of tips. No monthly fees, no minimums — accept "
            "only the jobs you want, get paid after each one. Ready? Reply YES "
            "and I'll send your 2-min setup link. Reply STOP to opt out."
        ).format(greet=_greet(name), frm=_from_line(va_name))
    return None


def _passcode_ok(supplied):
    expected = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    if not expected:
        return False  # fail closed
    return hmac.compare_digest(str(supplied or ""), str(expected))


def _run(fn):
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


@vahub_bp.route("/va", methods=["GET"])
def va_hub_page():
    return Response(VA_HUB_HTML, mimetype="text/html")


@vahub_bp.route("/va/text", methods=["GET"])
def va_text_page():
    return Response(VA_TEXT_HTML, mimetype="text/html")


@vahub_bp.route("/va/app.css", methods=["GET"])
def va_css():
    return Response(VA_CSS, mimetype="text/css")


@vahub_bp.route("/va/app.js", methods=["GET"])
def va_js():
    return Response(VA_JS, mimetype="application/javascript")


@vahub_bp.route("/api/va/send", methods=["POST"])
@_ratelimit
def va_send():
    if not os.environ.get("TRIXIE_ASSISTANT_PASSCODE"):
        return jsonify({"error": "Not set up yet — ask Shamar to add the access code."}), 503

    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("passcode")):
        return jsonify({"error": "That access code didn't work — double-check with Shamar."}), 401

    template = (data.get("template") or "").strip()
    name = (data.get("name") or "").strip()[:80]
    va_name = (data.get("va_name") or "").strip()[:40]
    body = build_va_message(template, name, va_name)
    if body is None:
        return jsonify({"error": "Pick which text to send first."}), 400

    import sms_service
    formatted = sms_service.format_phone((data.get("phone") or "").strip())
    if not formatted or len(formatted) < 11:
        return jsonify({"error": "Enter a valid US cell number (10 digits)."}), 400

    client = sms_service._get_twilio()
    from_num = _twilio_from()
    if client is None or not from_num:
        return jsonify({"error": "Texting isn't configured yet — ask Shamar to set the Twilio number."}), 503

    try:
        msg = _run(lambda: client.messages.create(body=body, from_=from_num, to=formatted))
        sid = getattr(msg, "sid", None)
        logger.info("va_hub sent template=%s to %s (sid=%s)", template, formatted, sid)
        return jsonify({"ok": True, "to": formatted, "sid": sid, "template": template})
    except Exception as e:
        logger.exception("va_hub send failed")
        return jsonify({
            "error": "Couldn't send the text — double-check the number, or our SMS provider may be down. Try again.",
            "debug": (type(e).__name__ + ": " + str(e))[:300],
        }), 502


VA_HUB_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<meta name="theme-color" content="#0B0E12" />
<title>Umuve — VA Tools</title>
<link rel="stylesheet" href="/va/app.css" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="gatewrap">
      <div class="eyebrow rv">Umuve · Internal</div>
      <h1 class="display" id="display-gate" aria-label="VA Tools">VA&nbsp;TOOLS</h1>
      <p class="sub rv">Every call ends one of four ways. This sends the right text for each.</p>
      <form id="gate-form" autocomplete="off" class="rv">
        <label class="lbl" for="code">Access code</label>
        <input id="code" type="password" autocomplete="off" placeholder="Enter your code" />
        <button class="btn" type="submit">Open tools</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
      <p class="hint rv">Same code as your coach. From Shamar.</p>
    </div>
  </section>

  <section id="tool" class="tool" hidden>
    <header class="bar">
      <div class="wordmark">UMUVE</div>
      <div class="bar-sub">VA tools · texts send from the Umuve number</div>
    </header>
    <div class="body">
      <h2 class="display display-sm" id="display-hub" aria-label="After the call">AFTER THE&nbsp;CALL</h2>
      <a class="situ rv" href="/optext">
        <div class="situ-key ok-key">YES</div>
        <div class="situ-txt">
          <div class="situ-t">They said yes</div>
          <div class="situ-d">Send the setup link — signs them up to get jobs by text.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ rv" href="/va/text?t=voicemail">
        <div class="situ-key">VM</div>
        <div class="situ-txt">
          <div class="situ-t">They didn&rsquo;t answer</div>
          <div class="situ-d">Voicemail follow-up. No links yet — their YES comes first.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ rv" href="/va/text?t=info">
        <div class="situ-key">FAQ</div>
        <div class="situ-txt">
          <div class="situ-t">They want details</div>
          <div class="situ-d">Info pack — pay split, how jobs work, no commitments.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ rv" href="/coach">
        <div class="situ-key">SOS</div>
        <div class="situ-txt">
          <div class="situ-t">Stuck on a call?</div>
          <div class="situ-d">Ask the Umuve coach — objections, scripts, answers.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
    </div>
  </section>
</div>
<script src="/va/app.js"></script>
</body>
</html>
"""


VA_TEXT_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<meta name="theme-color" content="#0B0E12" />
<title>Umuve — Send a Text</title>
<link rel="stylesheet" href="/va/app.css" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="gatewrap">
      <div class="eyebrow rv">Umuve · Internal</div>
      <h1 class="display" aria-label="Send a text">SEND A&nbsp;TEXT</h1>
      <p class="sub rv">Same login as your other tools.</p>
      <form id="gate-form" autocomplete="off" class="rv">
        <label class="lbl" for="code">Access code</label>
        <input id="code" type="password" autocomplete="off" placeholder="Enter your code" />
        <button class="btn" type="submit">Start</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
    </div>
  </section>

  <section id="tool" class="tool" hidden>
    <header class="bar">
      <a class="back" href="/va" aria-label="Back to VA tools">←</a>
      <div class="wordmark">UMUVE</div>
      <div class="bar-sub">Texts send from the Umuve number</div>
    </header>

    <div class="body">
      <h2 class="display display-sm rv" id="bar-title">VOICEMAIL</h2>

      <div class="seg rv" role="tablist" aria-label="Which text">
        <button class="seg-btn" id="tab-voicemail" role="tab" data-t="voicemail">VM follow-up</button>
        <button class="seg-btn" id="tab-info" role="tab" data-t="info">Info pack</button>
      </div>

      <form id="send-form" autocomplete="off" class="rv">
        <label class="lbl" for="va">Your first name</label>
        <input id="va" type="text" placeholder="e.g. Tracy" />
        <label class="lbl" for="name">Lead / company name <span class="opt">(optional)</span></label>
        <input id="name" type="text" placeholder="e.g. Eric at Gator Dumpster" />
        <label class="lbl" for="phone">Their cell number</label>
        <input id="phone" type="tel" inputmode="tel" placeholder="(561) 555-0123" />
        <button id="send" class="btn" type="submit">Send the text</button>
        <p id="result" class="result" hidden></p>
      </form>

      <div class="preview rv">
        <div class="preview-h">What they&rsquo;ll receive</div>
        <div class="bubble" id="bubble"></div>
      </div>

      <div id="sent-wrap" class="sent-wrap" hidden>
        <div class="sent-h">Sent this session</div>
        <ul id="sent" class="sent"></ul>
      </div>
    </div>
  </section>
</div>
<script src="/va/app.js"></script>
</body>
</html>
"""


VA_CSS = r""":root{
  --canvas:#0B0E12; --surface:#141922; --raise:#1A2029; --ink:#F4F6F8;
  --muted:rgba(244,246,248,.62); --faint:rgba(244,246,248,.38);
  --accent:#FF6A2C; --accent-press:#E85B1F; --line:rgba(244,246,248,.09);
  --ok:#3DD68C; --glow:0 0 0 3px rgba(255,106,44,.22);
  --display:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --body:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--canvas);color:var(--ink);font-family:var(--body);-webkit-font-smoothing:antialiased;line-height:1.45}
#app{max-width:560px;margin:0 auto;min-height:100dvh;display:flex;flex-direction:column;overflow:hidden}

/* ---------- display type: massive, condensed, bleeds the edge ---------- */
.display{font-family:var(--display);font-weight:900;text-transform:uppercase;
  font-size:clamp(64px,21vw,118px);line-height:.88;letter-spacing:-.05em;
  margin:6px 0 14px -3vw;width:106%;transform:scaleX(.93);transform-origin:left center;
  color:var(--ink);white-space:nowrap}
.display .ch{display:inline-block}
.display-sm{font-size:clamp(34px,11vw,58px);margin:2px 0 10px -1vw;width:104%}
.eyebrow{font-family:var(--display);font-weight:600;font-size:11.5px;letter-spacing:.32em;
  text-transform:uppercase;color:var(--accent);margin-bottom:14px}

/* ---------- gate ---------- */
.gate{flex:1;display:flex;align-items:center;padding:24px}
.gatewrap{width:100%}
.sub{color:var(--muted);margin:0 0 26px;font-size:15.5px;max-width:34ch}
.lbl{display:block;font-family:var(--display);font-weight:600;font-size:10.5px;
  letter-spacing:.18em;text-transform:uppercase;color:var(--faint);margin:16px 0 7px}
.lbl .opt{letter-spacing:0;text-transform:none;color:var(--faint);font-weight:500}
input{width:100%;padding:15px 16px;font-size:16px;font-family:var(--body);color:var(--ink);
  background:var(--surface);border:1.5px solid var(--line);border-radius:14px;outline:none;
  transition:border-color .15s, box-shadow .15s}
input::placeholder{color:var(--faint)}
input:focus{border-color:var(--accent);box-shadow:var(--glow)}
.btn{width:100%;margin-top:18px;padding:16px;font-size:16px;font-family:var(--display);
  font-weight:700;letter-spacing:.02em;color:#0B0E12;background:var(--accent);border:none;
  border-radius:14px;cursor:pointer;transition:background .15s,transform .05s}
.btn:hover{background:var(--accent-press)}
.btn:active{transform:translateY(1px)}
.btn:disabled{background:#3A414B;color:var(--faint);cursor:default}
.hint{color:var(--faint);font-size:12.5px;margin:18px 0 0}
.err{color:#FF7A5C;font-size:13.5px;margin:12px 0 0}

/* ---------- shell ---------- */
.tool{flex:1;display:flex;flex-direction:column}
.bar{display:flex;align-items:baseline;gap:12px;padding:16px 20px;
  padding-top:max(16px,env(safe-area-inset-top));border-bottom:1px solid var(--line)}
.wordmark{font-family:var(--display);font-weight:900;font-size:15px;letter-spacing:.26em}
.wordmark::after{content:"";display:inline-block;width:7px;height:7px;border-radius:2px;
  background:var(--accent);margin-left:5px;vertical-align:baseline}
.bar-sub{color:var(--faint);font-size:12px;margin-left:auto;text-align:right}
.back{font-size:20px;text-decoration:none;color:var(--ink);width:36px;height:36px;
  display:grid;place-items:center;border-radius:11px;background:var(--surface);
  border:1px solid var(--line);align-self:center}
.body{padding:22px 20px max(24px,env(safe-area-inset-bottom));display:flex;flex-direction:column;gap:14px}

/* ---------- situation cards ---------- */
.situ{display:flex;align-items:center;gap:16px;background:var(--surface);
  border:1px solid var(--line);border-radius:18px;padding:18px;
  text-decoration:none;color:var(--ink);transition:transform .06s,border-color .15s}
.situ:active{transform:scale(.985)}
.situ:hover{border-color:rgba(255,106,44,.45)}
.situ-key{font-family:var(--display);font-weight:900;font-size:15px;letter-spacing:.04em;
  width:56px;height:56px;display:grid;place-items:center;border-radius:14px;flex:none;
  background:var(--raise);color:var(--muted);border:1px solid var(--line);
  transform:scaleX(.93)}
.situ:hover .situ-key{color:var(--accent)}
.ok-key{color:var(--accent);border-color:rgba(255,106,44,.4)}
.situ-t{font-family:var(--display);font-weight:700;font-size:17px;letter-spacing:-.01em}
.situ-d{color:var(--muted);font-size:13.5px;margin-top:3px;line-height:1.45}
.situ-go{margin-left:auto;color:var(--accent);font-size:20px;font-weight:700;flex:none}

/* ---------- sender ---------- */
.seg{display:flex;gap:6px;background:var(--surface);border:1px solid var(--line);
  border-radius:15px;padding:6px}
.seg-btn{flex:1;padding:12px 8px;font-family:var(--display);font-weight:700;font-size:13.5px;
  letter-spacing:.02em;color:var(--muted);background:transparent;border:none;
  border-radius:11px;cursor:pointer;transition:background .15s,color .15s}
.seg-btn.on{background:var(--accent);color:#0B0E12}
#send-form{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:20px 18px}
#send-form input{background:var(--raise)}
#send-form .lbl:first-of-type{margin-top:0}
.result{margin:14px 0 0;padding:12px 14px;border-radius:12px;font-size:14.5px;display:none}
.result.show{display:block}
.result.ok{background:rgba(61,214,140,.12);color:var(--ok);border:1px solid rgba(61,214,140,.35)}
.result.bad{background:rgba(255,122,92,.1);color:#FF7A5C;border:1px solid rgba(255,122,92,.35)}

.preview{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:16px 18px}
.preview-h,.sent-h{font-family:var(--display);font-weight:600;font-size:10.5px;
  letter-spacing:.18em;text-transform:uppercase;color:var(--faint);margin:0 0 10px}
.bubble{background:var(--raise);border:1px solid var(--line);border-radius:14px;
  border-bottom-left-radius:5px;padding:13px 15px;font-size:14px;color:var(--muted);
  line-height:1.55;white-space:pre-wrap;transition:filter .2s,opacity .2s}
.bubble.swap{filter:blur(6px);opacity:.4}
.sent-wrap{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:16px 18px}
.sent{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.sent li{font-size:14px;color:var(--muted);display:flex;align-items:center;gap:8px}
.sent li::before{content:"✓";color:var(--ok);font-weight:700}

/* ---------- cinematic entrances (skill recipe #6, capped at ~.55s) ---------- */
.rv{opacity:0;filter:blur(8px);transform:translateY(14px) scale(.975)}
.rv.in{opacity:1;filter:blur(0);transform:none;
  transition:opacity .5s cubic-bezier(.2,.7,.2,1),filter .5s cubic-bezier(.2,.7,.2,1),
  transform .5s cubic-bezier(.2,.7,.2,1)}
.display .ch{opacity:0;filter:blur(10px);transform:translateY(.35em) scaleY(1.15)}
.display .ch.in{opacity:1;filter:blur(0);transform:none;
  transition:opacity .45s cubic-bezier(.2,.7,.2,1),filter .45s cubic-bezier(.2,.7,.2,1),
  transform .45s cubic-bezier(.2,.7,.2,1)}

:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion:reduce){
  *{transition:none!important}
  .rv,.display .ch{opacity:1!important;filter:none!important;transform:none!important}
  .display{transform:scaleX(.93)}
}
"""


VA_JS = r"""(function(){
  var KEY = "umuve_coach_code";   // shared login across coach/optext/va tools
  var VA_KEY = "umuve_va_name";
  var gate = document.getElementById("gate");
  var tool = document.getElementById("tool");
  var gateErr = document.getElementById("gate-err");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- cinematic entrances: split display type into chars, stagger reveals ----
  function splitChars(el){
    if(!el || el.dataset.split) return;
    el.dataset.split = "1";
    var text = el.textContent;
    el.textContent = "";
    for(var i = 0; i < text.length; i++){
      var s = document.createElement("span");
      s.className = "ch";
      s.textContent = text[i] === " " ? " " : text[i];
      el.appendChild(s);
    }
  }
  function reveal(scope){
    if(reduced){
      scope.querySelectorAll(".rv,.display .ch").forEach(function(el){ el.classList.add("in"); });
      return;
    }
    scope.querySelectorAll(".display").forEach(splitChars);
    var chars = scope.querySelectorAll(".display .ch");
    chars.forEach(function(c, i){
      setTimeout(function(){ c.classList.add("in"); }, 40 + i * 26);
    });
    var blocks = scope.querySelectorAll(".rv");
    blocks.forEach(function(b, i){
      setTimeout(function(){ b.classList.add("in"); }, 140 + i * 65);
    });
  }

  function code(){ return localStorage.getItem(KEY) || ""; }
  function showTool(){ gate.hidden = true; tool.hidden = false; reveal(tool); }
  function showGate(msg){
    tool.hidden = true; gate.hidden = false; reveal(gate);
    if(msg && gateErr){ gateErr.textContent = msg; gateErr.hidden = false; }
    var c = document.getElementById("code"); if(c) c.focus();
  }

  var gateForm = document.getElementById("gate-form");
  if(gateForm){
    gateForm.addEventListener("submit", function(e){
      e.preventDefault();
      var v = document.getElementById("code").value.trim();
      if(!v){ gateErr.textContent = "Enter your access code."; gateErr.hidden = false; return; }
      localStorage.setItem(KEY, v);
      showTool(); init();
    });
  }

  // ---- sender page only ----
  var sendForm = document.getElementById("send-form");
  var TEMPLATES = {
    voicemail: {
      title: "VOICEMAIL",
      btn: "Send the voicemail follow-up",
      build: function(name, va){
        return greet(name) + " " + fromLine(va) + " — just left you a voicemail. We send paying junk-removal jobs in Palm Beach County to local haulers: you keep ~72% plus 100% of tips, no fees, jobs come by text and you only take the ones you want. Worth a quick chat? Reply YES and I'll send your 2-min setup link. Reply STOP to opt out.";
      }
    },
    info: {
      title: "INFO PACK",
      btn: "Send the info pack",
      build: function(name, va){
        return greet(name) + " " + fromLine(va) + " — the info you asked for: we text you paid junk-removal jobs in Palm Beach County. You keep ~72% of the job price plus 100% of tips. No monthly fees, no minimums — accept only the jobs you want, get paid after each one. Ready? Reply YES and I'll send your 2-min setup link. Reply STOP to opt out.";
      }
    }
  };
  function greet(n){ return n ? "Hi " + n + "," : "Hi there,"; }
  function fromLine(v){ return v ? "this is " + v + " with Umuve" : "it's Umuve"; }

  var current = "voicemail";
  function init(){
    if(!sendForm) return;   // hub page has no form
    var params = new URLSearchParams(location.search);
    var t = params.get("t");
    if(TEMPLATES[t]) current = t;
    var va = document.getElementById("va");
    va.value = localStorage.getItem(VA_KEY) || "";
    ["voicemail","info"].forEach(function(k){
      document.getElementById("tab-" + k).addEventListener("click", function(){ pick(k); });
    });
    ["va","name"].forEach(function(id){
      document.getElementById(id).addEventListener("input", refresh);
    });
    sendForm.addEventListener("submit", function(e){ e.preventDefault(); send(); });
    pick(current, true);
  }

  function setTitle(text){
    var el = document.getElementById("bar-title");
    el.textContent = text;
    el.dataset.split = "";
    if(!reduced){
      splitChars(el);
      el.querySelectorAll(".ch").forEach(function(c, i){
        setTimeout(function(){ c.classList.add("in"); }, 20 + i * 24);
      });
    }
  }

  function pick(k, first){
    current = k;
    ["voicemail","info"].forEach(function(x){
      document.getElementById("tab-" + x).classList.toggle("on", x === k);
    });
    setTitle(TEMPLATES[k].title);
    document.getElementById("send").textContent = TEMPLATES[k].btn;
    history.replaceState(null, "", "/va/text?t=" + k);
    var bubble = document.getElementById("bubble");
    if(!first && !reduced){
      bubble.classList.add("swap");
      setTimeout(function(){ refresh(); bubble.classList.remove("swap"); }, 160);
    } else {
      refresh();
    }
  }

  function refresh(){
    var name = document.getElementById("name").value.trim();
    var va = document.getElementById("va").value.trim();
    document.getElementById("bubble").textContent = TEMPLATES[current].build(name, va);
  }

  var busy = false;
  function setResult(kind, text){
    var r = document.getElementById("result");
    r.textContent = text; r.className = "result show " + kind;
  }
  function send(){
    if(busy) return;
    var phone = document.getElementById("phone").value.trim();
    var name = document.getElementById("name").value.trim();
    var va = document.getElementById("va").value.trim();
    if(!va){ setResult("bad", "Add your first name so the lead knows who texted."); return; }
    if(!phone){ setResult("bad", "Enter their cell number first."); return; }
    localStorage.setItem(VA_KEY, va);
    var btn = document.getElementById("send");
    busy = true; btn.disabled = true; btn.textContent = "Sending…";
    fetch("/api/va/send", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ passcode: code(), template: current, name: name, va_name: va, phone: phone })
    }).then(function(r){ return r.json().then(function(j){ return {status:r.status, body:j}; }); })
    .then(function(res){
      busy = false; btn.disabled = false; btn.textContent = TEMPLATES[current].btn;
      if(res.status === 401){ showGate("That code didn't work — double-check with Shamar."); return; }
      if(res.status >= 200 && res.status < 300 && res.body.ok){
        setResult("ok", "Sent to " + (res.body.to || phone) + " ✅");
        var li = document.createElement("li");
        li.textContent = TEMPLATES[current].title + " — " + (name ? name + " — " : "") + (res.body.to || phone);
        var list = document.getElementById("sent");
        list.insertBefore(li, list.firstChild);
        document.getElementById("sent-wrap").hidden = false;
        document.getElementById("name").value = "";
        document.getElementById("phone").value = "";
        refresh();
      } else {
        setResult("bad", res.body.error || "Couldn't send — try again.");
      }
    }).catch(function(){
      busy = false; btn.disabled = false; btn.textContent = TEMPLATES[current].btn;
      setResult("bad", "Couldn't reach the server — check your connection and try again.");
    });
  }

  if(code()){ showTool(); init(); } else { showGate(); }
})();
"""
