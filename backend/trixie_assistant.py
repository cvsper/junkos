"""
Ask Umuve — hosted call-coach assistant for the sales VA.

Routes:
  GET  /coach           -> serves the single-page chat UI (static, no secrets)
  POST /api/coach/chat  -> passcode-gated proxy to Claude Haiku with the Umuve
                           system prompt.

Fails CLOSED: if TRIXIE_ASSISTANT_PASSCODE or ANTHROPIC_API_KEY is not set, the
chat endpoint refuses to run, so the assistant is never open to the public.

Config (set in Render env, NEVER in code):
  TRIXIE_ASSISTANT_PASSCODE  -- access code the VA enters (required)
  ANTHROPIC_API_KEY          -- already used elsewhere in the backend (required)
  COACH_MODEL                -- optional; defaults to claude-haiku-4-5-20251001
"""
from __future__ import annotations

import hmac
import logging
import os

from flask import Blueprint, Response, jsonify, request

try:  # rate limiting is a nice-to-have; never block registration on it
    from extensions import limiter
except Exception:  # pragma: no cover
    limiter = None

logger = logging.getLogger(__name__)

coach_bp = Blueprint("coach", __name__)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_TURNS = 16        # cap conversation history sent to the model (cost guard)
MAX_TOKENS = 1024
MAX_MSG_CHARS = 4000

SYSTEM_PROMPT = (
    "You are \"Ask Umuve,\" a friendly, sharp call coach for Trixie, who "
    "cold-calls junk-removal and hauling company owners to recruit them onto "
    "Umuve. Keep answers SHORT, practical, and ready to say out loud on a "
    "call. Sound warm and human, never robotic or pushy. When she asks how to "
    "handle something, give her the exact words.\n\n"
    "ABOUT UMUVE:\n"
    "- Umuve (pronounced \"you-move\") is an app marketplace for junk removal / "
    "hauling — \"Uber for junk removal.\" Customers book and PAY in the app; "
    "Umuve routes the job to a nearby local hauler (\"operator\"); the hauler "
    "hauls it and gets paid.\n"
    "- Trixie's job: get hauler/truck owners to APPLY and get ONLINE in the "
    "\"Umuve Pro\" iPhone app so they receive paying jobs. The win = a truck "
    "actually ONLINE.\n"
    "- Launch market: West Palm Beach / Palm Beach County, Florida.\n"
    "- The pitch: \"Umuve brings paying junk-removal jobs to local haulers. The "
    "customer books and pays through our app, we send the job to your phone, "
    "you haul it. No subscription, no upfront cost — you keep most of the "
    "ticket, we take a small cut only on completed jobs. We're launching West "
    "Palm Beach and onboarding a few haulers first — want a spot?\"\n\n"
    "KEY FACTS:\n"
    "- Cost to hauler: $0 to join, $0 monthly, $0 per lead. Umuve takes a small "
    "commission ONLY on completed jobs; the hauler keeps the majority. Don't "
    "quote an exact %% — say the founder Shamar covers the exact split at "
    "setup.\n"
    "- Payment: via Stripe, direct to the hauler's bank after each job.\n"
    "- Signup: 1) Apply at goumuve.com/operators  2) Get the Umuve Pro app "
    "(apps.apple.com/app/id6759131650)  3) connect Stripe + tap \"Go Online.\"\n"
    "- They need: general liability insurance, a truck, driver's license, bank "
    "account.\n"
    "- Founder Shamar personally helps every new operator finish setup, same "
    "day.\n"
    "- Umuve Pro is iPhone only; Android users apply at goumuve.com/operators "
    "and Shamar helps with the app.\n\n"
    "HOW TO COACH HER:\n"
    "- For objections: acknowledge, answer in one breath, steer back to "
    "\"let's get you a spot.\"\n"
    "- The goal of every call: get a YES, get their cell, text the setup link "
    "LIVE, then post the handoff in the #signups Slack channel so Shamar gets "
    "them online same-day.\n"
    "- If she asks for a script, text, or voicemail, write it tight and "
    "natural.\n"
    "- If you don't know an Umuve-specific detail, say so and tell her to "
    "check with Shamar — never invent facts (especially numbers, policies, or "
    "coverage areas).\n"
    "- Keep replies short enough to glance at mid-call: a couple of short "
    "lines, not walls of text."
).replace("%%", "%")


def _passcode_ok(supplied: str) -> bool:
    expected = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    if not expected:
        return False  # fail closed when unconfigured
    return hmac.compare_digest(str(supplied or ""), str(expected))


def _anthropic_client():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return None
    try:
        import anthropic  # type: ignore
        return anthropic.Anthropic(api_key=key)
    except Exception:
        logger.warning("anthropic SDK unavailable for coach")
        return None


_ratelimit = (
    limiter.limit("40 per hour; 8 per minute")
    if limiter is not None
    else (lambda f: f)
)


@coach_bp.route("/coach", methods=["GET"])
def coach_page():
    return Response(COACH_HTML, mimetype="text/html")


@coach_bp.route("/api/coach/chat", methods=["POST"])
@_ratelimit
def coach_chat():
    # Fail closed if not configured.
    if not os.environ.get("TRIXIE_ASSISTANT_PASSCODE"):
        return jsonify({
            "error": "The coach isn't set up yet — ask Shamar to add the access code."
        }), 503

    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("passcode")):
        return jsonify({
            "error": "That access code didn't work — double-check with Shamar."
        }), 401

    raw = data.get("messages") or []
    messages = []
    for m in raw[-MAX_TURNS:]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = (m.get("content") or "").strip()[:MAX_MSG_CHARS]
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    if not messages or messages[-1]["role"] != "user":
        return jsonify({"error": "Type a question first 🙂"}), 400

    client = _anthropic_client()
    if client is None:
        return jsonify({
            "error": "The coach is temporarily unavailable. Try again in a moment."
        }), 503

    model = os.environ.get("COACH_MODEL", DEFAULT_MODEL)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        reply = "".join(getattr(b, "text", "") for b in resp.content).strip()
        if not reply:
            reply = "Hmm, I didn't catch that — try asking another way?"
        return jsonify({"reply": reply})
    except Exception:
        logger.exception("coach chat failed")
        return jsonify({
            "error": "Couldn't reach the coach right now — give it a second and try again."
        }), 502


COACH_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<title>Ask Umuve — Call Coach</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet" />
<style>
  :root{
    --canvas:#EEF1F5; --surface:#FFFFFF; --ink:#16202C; --muted:#5B6878;
    --accent:#FF6A2C; --accent-press:#E85B1F; --user:#1B2A3A; --line:#E3E8EE;
    --ok:#1FA971; --bot:#FFFFFF; --shadow:0 1px 2px rgba(16,32,44,.06),0 8px 24px rgba(16,32,44,.06);
    --display:'Space Grotesk',ui-sans-serif,system-ui,sans-serif;
    --body:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0;background:var(--canvas);color:var(--ink);font-family:var(--body);
    -webkit-font-smoothing:antialiased;line-height:1.45;
  }
  #app{max-width:680px;margin:0 auto;height:100dvh;display:flex;flex-direction:column;background:var(--canvas)}

  /* shared mark */
  .mark{
    font-family:var(--display);font-weight:700;color:#fff;background:var(--user);
    width:54px;height:54px;border-radius:16px;display:grid;place-items:center;font-size:26px;
    position:relative;box-shadow:var(--shadow);
  }
  .mark::after{content:"";position:absolute;right:-3px;bottom:-3px;width:18px;height:18px;border-radius:6px;background:var(--accent)}
  .mark.sm{width:38px;height:38px;border-radius:11px;font-size:19px}
  .mark.sm::after{width:12px;height:12px;border-radius:4px;right:-2px;bottom:-2px}

  /* ---- gate ---- */
  .gate{flex:1;display:flex;align-items:center;justify-content:center;padding:24px}
  .gate-card{
    width:100%;max-width:380px;background:var(--surface);border:1px solid var(--line);
    border-radius:22px;padding:32px 28px;box-shadow:var(--shadow);text-align:center;
  }
  .gate-card .mark{margin:0 auto 18px}
  .gate h1{font-family:var(--display);font-weight:700;font-size:27px;margin:0 0 8px;letter-spacing:-.02em}
  .gate .sub{color:var(--muted);margin:0 0 24px;font-size:15px}
  .lbl{display:block;text-align:left;font-family:var(--display);font-weight:600;font-size:11px;
    letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:0 0 7px}
  input#code{
    width:100%;padding:14px 15px;font-size:16px;font-family:var(--body);color:var(--ink);
    background:#F6F8FA;border:1.5px solid var(--line);border-radius:13px;outline:none;
  }
  input#code:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(255,106,44,.18);background:#fff}
  .btn{
    width:100%;margin-top:14px;padding:14px;font-size:16px;font-family:var(--display);font-weight:600;
    color:#fff;background:var(--accent);border:none;border-radius:13px;cursor:pointer;transition:background .15s,transform .05s;
  }
  .btn:hover{background:var(--accent-press)}
  .btn:active{transform:translateY(1px)}
  .hint{color:var(--muted);font-size:12.5px;margin:18px 0 0}
  .err{color:#C0341F;font-size:13.5px;margin:12px 0 0;text-align:left}

  /* ---- chat ---- */
  .chat{flex:1;display:flex;flex-direction:column;min-height:0}
  .bar{
    display:flex;align-items:center;gap:12px;padding:12px 16px;
    padding-top:max(12px,env(safe-area-inset-top));
    background:var(--surface);border-bottom:1px solid var(--line);
  }
  .bar-id{flex:1;min-width:0}
  .bar-title{font-family:var(--display);font-weight:700;font-size:17px;letter-spacing:-.01em}
  .bar-sub{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:12.5px;margin-top:1px}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 3px rgba(31,169,113,.18)}
  .bar-btn{
    font-family:var(--display);font-weight:600;font-size:12.5px;color:var(--muted);
    background:transparent;border:1px solid var(--line);border-radius:9px;padding:7px 11px;cursor:pointer;
  }
  .bar-btn:hover{color:var(--ink);border-color:var(--muted)}

  .thread{flex:1;overflow-y:auto;padding:20px 16px 8px;display:flex;flex-direction:column;gap:12px;scroll-behavior:smooth}
  .row{display:flex;max-width:88%}
  .row.user{align-self:flex-end;justify-content:flex-end}
  .row.bot{align-self:flex-start}
  .bubble{
    padding:11px 14px;border-radius:18px;font-size:15.5px;white-space:normal;word-wrap:break-word;
    animation:rise .22s ease both;
  }
  .row.bot .bubble{background:var(--bot);border:1px solid var(--line);border-bottom-left-radius:6px;box-shadow:var(--shadow)}
  .row.user .bubble{background:var(--user);color:#fff;border-bottom-right-radius:6px}
  .bubble strong{font-weight:700}
  @keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

  .typing{display:flex;gap:4px;padding:14px 15px}
  .typing span{width:7px;height:7px;border-radius:50%;background:var(--muted);opacity:.5;animation:blink 1.2s infinite}
  .typing span:nth-child(2){animation-delay:.2s}
  .typing span:nth-child(3){animation-delay:.4s}
  @keyframes blink{0%,60%,100%{opacity:.25;transform:translateY(0)}30%{opacity:.9;transform:translateY(-3px)}}

  /* ---- composer ---- */
  .composer{
    background:var(--surface);border-top:1px solid var(--line);
    padding:10px 12px max(10px,env(safe-area-inset-bottom));
  }
  .chips{display:flex;gap:8px;overflow-x:auto;padding-bottom:9px;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  .chips::-webkit-scrollbar{display:none}
  .chip{
    flex:0 0 auto;font-family:var(--body);font-size:13px;color:var(--ink);background:#F1F4F7;
    border:1px solid var(--line);border-radius:999px;padding:8px 13px;cursor:pointer;white-space:nowrap;transition:background .12s,border-color .12s;
  }
  .chip:hover{background:#E8EDF2;border-color:var(--muted)}
  .send-row{display:flex;align-items:flex-end;gap:9px}
  textarea#input{
    flex:1;resize:none;max-height:140px;font-family:var(--body);font-size:16px;color:var(--ink);
    background:#F6F8FA;border:1.5px solid var(--line);border-radius:16px;padding:12px 14px;outline:none;line-height:1.4;
  }
  textarea#input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(255,106,44,.16);background:#fff}
  .send{
    flex:0 0 auto;width:46px;height:46px;border-radius:50%;border:none;background:var(--accent);color:#fff;
    cursor:pointer;display:grid;place-items:center;transition:background .15s,transform .05s;
  }
  .send:hover{background:var(--accent-press)}
  .send:active{transform:translateY(1px)}
  .send:disabled{background:#C7CDD4;cursor:default}
  .send svg{width:20px;height:20px;display:block}

  :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
  @media (prefers-reduced-motion:reduce){
    *{animation:none!important;scroll-behavior:auto!important}
  }
</style>
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="gate-card">
      <div class="mark">U</div>
      <h1>Ask Umuve</h1>
      <p class="sub">Your call coach. Ask anything mid-call — fast, plain answers you can say out loud.</p>
      <form id="gate-form" autocomplete="off">
        <label class="lbl" for="code">Access code</label>
        <input id="code" type="password" inputmode="text" autocomplete="off" placeholder="Enter your code" />
        <button class="btn" type="submit">Start</button>
        <p id="gate-err" class="err" hidden></p>
      </form>
      <p class="hint">Code from Shamar. Keep this tab open while you dial.</p>
    </div>
  </section>

  <section id="chat" class="chat" hidden>
    <header class="bar">
      <div class="mark sm">U</div>
      <div class="bar-id">
        <div class="bar-title">Ask Umuve</div>
        <div class="bar-sub"><span class="dot"></span> Coach · ready</div>
      </div>
      <button id="reset" class="bar-btn" type="button">Clear</button>
    </header>
    <div id="thread" class="thread" aria-live="polite"></div>
    <div class="composer">
      <div class="chips" id="chips">
        <button class="chip" type="button">He says he already has enough work</button>
        <button class="chip" type="button">Explain Stripe simply</button>
        <button class="chip" type="button">Reword the voicemail shorter</button>
        <button class="chip" type="button">He has an Android, not iPhone</button>
        <button class="chip" type="button">Follow-up text for "call me Friday"</button>
      </div>
      <form id="send-form" class="send-row">
        <textarea id="input" rows="1" placeholder="Ask your coach…" aria-label="Ask your coach"></textarea>
        <button id="send" class="send" type="submit" aria-label="Send">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
        </button>
      </form>
    </div>
  </section>
</div>

<script>
(function(){
  var API = "/api/coach/chat";
  var KEY = "umuve_coach_code";
  var gate = document.getElementById("gate");
  var chat = document.getElementById("chat");
  var thread = document.getElementById("thread");
  var input = document.getElementById("input");
  var sendBtn = document.getElementById("send");
  var gateErr = document.getElementById("gate-err");
  var history = [];   // {role, content} for the API
  var busy = false;

  function code(){ return localStorage.getItem(KEY) || ""; }
  function esc(s){ return s.replace(/[&<>]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c]; }); }
  function fmt(s){ return esc(s).replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").replace(/\n/g,"<br>"); }
  function scroll(){ thread.scrollTop = thread.scrollHeight; }

  function bubble(role, text){
    var row = document.createElement("div");
    row.className = "row " + (role === "user" ? "user" : "bot");
    var b = document.createElement("div");
    b.className = "bubble";
    b.innerHTML = role === "user" ? esc(text) : fmt(text);
    row.appendChild(b);
    thread.appendChild(row);
    scroll();
    return row;
  }

  function typing(){
    var row = document.createElement("div");
    row.className = "row bot";
    row.id = "typing";
    row.innerHTML = '<div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>';
    thread.appendChild(row);
    scroll();
    return row;
  }

  function showChat(){
    gate.hidden = true; chat.hidden = false;
    if(!thread.childElementCount){
      bubble("bot", "Hey Trixie! I'm your Umuve call coach 👋 Ask me anything — an objection, how to word a text, how to explain Stripe. Tap a quick question below or type your own.");
    }
    input.focus();
  }
  function showGate(msg){
    chat.hidden = true; gate.hidden = false;
    if(msg){ gateErr.textContent = msg; gateErr.hidden = false; } else { gateErr.hidden = true; }
    document.getElementById("code").focus();
  }

  function setBusy(v){ busy = v; sendBtn.disabled = v; }

  function send(text){
    text = (text || "").trim();
    if(!text || busy) return;
    bubble("user", text);
    history.push({role:"user", content:text});
    input.value = ""; autosize();
    setBusy(true);
    var t = typing();
    fetch(API, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ passcode: code(), messages: history })
    }).then(function(r){
      return r.json().then(function(j){ return {status:r.status, body:j}; });
    }).then(function(res){
      t.remove();
      if(res.status === 401){ setBusy(false); showGate("That code didn't work — double-check with Shamar."); return; }
      if(res.status >= 200 && res.status < 300 && res.body.reply){
        history.push({role:"assistant", content:res.body.reply});
        bubble("bot", res.body.reply);
      } else {
        bubble("bot", res.body.error || "Couldn't reach the coach — try again.");
      }
      setBusy(false); input.focus();
    }).catch(function(){
      t.remove();
      bubble("bot", "Couldn't reach the coach — check your connection and try again.");
      setBusy(false);
    });
  }

  function autosize(){ input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 140) + "px"; }

  // events
  document.getElementById("gate-form").addEventListener("submit", function(e){
    e.preventDefault();
    var v = document.getElementById("code").value.trim();
    if(!v){ gateErr.textContent = "Enter your access code."; gateErr.hidden = false; return; }
    localStorage.setItem(KEY, v);
    showChat();
  });
  document.getElementById("send-form").addEventListener("submit", function(e){ e.preventDefault(); send(input.value); });
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", function(e){
    if(e.key === "Enter" && !e.shiftKey){ e.preventDefault(); send(input.value); }
  });
  document.getElementById("chips").addEventListener("click", function(e){
    if(e.target.classList.contains("chip")){ send(e.target.textContent); }
  });
  document.getElementById("reset").addEventListener("click", function(){
    history = []; thread.innerHTML = ""; showChat();
  });

  // boot
  if(code()){ showChat(); } else { showGate(); }
})();
</script>
</body>
</html>
"""
