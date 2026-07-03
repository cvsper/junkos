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
<title>Umuve — VA Tools</title>
<link rel="stylesheet" href="/va/app.css" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="card">
      <div class="mark">U</div>
      <h1>VA Tools</h1>
      <p class="sub">Pick the situation — the right text is already loaded.</p>
      <form id="gate-form" autocomplete="off">
        <label class="lbl" for="code">Access code</label>
        <input id="code" type="password" autocomplete="off" placeholder="Enter your code" />
        <button class="btn" type="submit">Open tools</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
      <p class="hint">Same code as your coach. From Shamar.</p>
    </div>
  </section>

  <section id="tool" class="tool" hidden>
    <header class="bar">
      <div class="mark sm">U</div>
      <div class="bar-id">
        <div class="bar-title">VA Tools</div>
        <div class="bar-sub">What just happened on your call?</div>
      </div>
    </header>
    <div class="body">
      <a class="situ" href="/optext">
        <div class="situ-emoji">✅</div>
        <div class="situ-txt">
          <div class="situ-t">They said YES</div>
          <div class="situ-d">Send the setup link — signs them up to get jobs by text.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ" href="/va/text?t=voicemail">
        <div class="situ-emoji">📵</div>
        <div class="situ-txt">
          <div class="situ-t">They didn't answer</div>
          <div class="situ-d">Drop the voicemail follow-up text. No links yet — their YES comes first.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ" href="/va/text?t=info">
        <div class="situ-emoji">💬</div>
        <div class="situ-txt">
          <div class="situ-t">They want details</div>
          <div class="situ-d">Send the info pack — pay split, how jobs work, no commitments.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ" href="/coach">
        <div class="situ-emoji">🎧</div>
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
<title>Umuve — Send a Text</title>
<link rel="stylesheet" href="/va/app.css" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="card">
      <div class="mark">U</div>
      <h1>Send a Text</h1>
      <p class="sub">Same login as your other tools.</p>
      <form id="gate-form" autocomplete="off">
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
      <div class="bar-id">
        <div class="bar-title" id="bar-title">Send a Text</div>
        <div class="bar-sub">Texts from the Umuve number</div>
      </div>
    </header>

    <div class="body">
      <div class="seg" role="tablist" aria-label="Which text">
        <button class="seg-btn" id="tab-voicemail" role="tab" data-t="voicemail">📵 Voicemail follow-up</button>
        <button class="seg-btn" id="tab-info" role="tab" data-t="info">💬 Info pack</button>
      </div>

      <form id="send-form" autocomplete="off">
        <label class="lbl" for="va">Your first name</label>
        <input id="va" type="text" placeholder="e.g. Tracy" />
        <label class="lbl" for="name">Lead / company name <span class="opt">(optional)</span></label>
        <input id="name" type="text" placeholder="e.g. Eric at Gator Dumpster" />
        <label class="lbl" for="phone">Their cell number</label>
        <input id="phone" type="tel" inputmode="tel" placeholder="(561) 555-0123" />
        <button id="send" class="btn" type="submit">Send the text</button>
        <p id="result" class="result" hidden></p>
      </form>

      <div class="preview">
        <div class="preview-h">What they'll receive</div>
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
  --canvas:#EEF1F5; --surface:#FFFFFF; --ink:#16202C; --muted:#5B6878;
  --accent:#FF6A2C; --accent-press:#E85B1F; --line:#E3E8EE; --ok:#1FA971;
  --shadow:0 1px 2px rgba(16,32,44,.06),0 8px 24px rgba(16,32,44,.06);
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
.back{font-size:22px;text-decoration:none;color:var(--ink);width:38px;height:38px;display:grid;place-items:center;border-radius:11px;background:#F6F8FA;border:1px solid var(--line)}
.body{padding:20px 18px max(20px,env(safe-area-inset-bottom));display:flex;flex-direction:column;gap:16px}

.situ{display:flex;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:var(--shadow);text-decoration:none;color:var(--ink);transition:transform .06s}
.situ:active{transform:scale(.985)}
.situ-emoji{font-size:26px;width:48px;height:48px;display:grid;place-items:center;background:#F6F8FA;border-radius:14px;flex:none}
.situ-t{font-family:var(--display);font-weight:700;font-size:16.5px}
.situ-d{color:var(--muted);font-size:13.5px;margin-top:2px;line-height:1.4}
.situ-go{margin-left:auto;color:var(--accent);font-size:20px;font-weight:700;flex:none}

.seg{display:flex;gap:8px;background:var(--surface);border:1px solid var(--line);border-radius:15px;padding:6px;box-shadow:var(--shadow)}
.seg-btn{flex:1;padding:11px 8px;font-family:var(--display);font-weight:600;font-size:13.5px;color:var(--muted);background:transparent;border:none;border-radius:11px;cursor:pointer}
.seg-btn.on{background:#1B2A3A;color:#fff}

#send-form{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:20px 18px;box-shadow:var(--shadow)}
#send-form .lbl:first-of-type{margin-top:0}
.result{margin:14px 0 0;padding:12px 14px;border-radius:12px;font-size:14.5px;display:none}
.result.show{display:block}
.result.ok{background:#E7F7EF;color:#0E6B45;border:1px solid #B6E6CE}
.result.bad{background:#FBEAE6;color:#B23218;border:1px solid #F1C4B8}

.preview{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:16px 18px}
.preview-h,.sent-h{font-family:var(--display);font-weight:600;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
.bubble{background:#EAF0F6;border:1px solid var(--line);border-radius:14px;border-bottom-left-radius:5px;padding:12px 14px;font-size:14px;color:#27313c;line-height:1.5;white-space:pre-wrap}
.sent-wrap{background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:16px 18px}
.sent{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.sent li{font-size:14px;color:var(--ink);display:flex;align-items:center;gap:8px}
.sent li::before{content:"✅"}

:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


VA_JS = r"""(function(){
  var KEY = "umuve_coach_code";   // shared login across coach/optext/va tools
  var VA_KEY = "umuve_va_name";
  var gate = document.getElementById("gate");
  var tool = document.getElementById("tool");
  var gateErr = document.getElementById("gate-err");

  function code(){ return localStorage.getItem(KEY) || ""; }
  function showTool(){ gate.hidden = true; tool.hidden = false; }
  function showGate(msg){
    tool.hidden = true; gate.hidden = false;
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
      title: "Voicemail follow-up",
      btn: "Send the voicemail follow-up",
      build: function(name, va){
        return greet(name) + " " + fromLine(va) + " — just left you a voicemail. We send paying junk-removal jobs in Palm Beach County to local haulers: you keep ~72% plus 100% of tips, no fees, jobs come by text and you only take the ones you want. Worth a quick chat? Reply YES and I'll send your 2-min setup link. Reply STOP to opt out.";
      }
    },
    info: {
      title: "Info pack",
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
    pick(current);
  }

  function pick(k){
    current = k;
    ["voicemail","info"].forEach(function(x){
      document.getElementById("tab-" + x).classList.toggle("on", x === k);
    });
    document.getElementById("bar-title").textContent = TEMPLATES[k].title;
    document.getElementById("send").textContent = TEMPLATES[k].btn;
    history.replaceState(null, "", "/va/text?t=" + k);
    refresh();
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
