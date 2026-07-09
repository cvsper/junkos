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
import re

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


# ---------------------------------------------------------------------------
# Intro EMAIL — for leads whose listing shows an email instead of a manager's
# phone (Tracy's 2026-07-09 suggestion). Sends from the Umuve recruiting
# address, never the VA's personal email. Same passcode gate, same whitelist
# principle: the client picks fields, the body is built server-side only.
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _va_email_from():
    return (os.environ.get("VA_EMAIL_FROM")
            or os.environ.get("OUTREACH_FROM") or "").strip() or None


@vahub_bp.route("/va/email", methods=["GET"])
def va_email_page():
    return Response(VA_EMAIL_HTML, mimetype="text/html")


@vahub_bp.route("/va/email.js", methods=["GET"])
def va_email_js():
    return Response(VA_EMAIL_JS, mimetype="application/javascript")


@vahub_bp.route("/api/va/email", methods=["POST"])
@_ratelimit
def va_email_send():
    if not os.environ.get("TRIXIE_ASSISTANT_PASSCODE"):
        return jsonify({"error": "Not set up yet — ask Shamar to add the access code."}), 503

    data = request.get_json(silent=True) or {}
    if not _passcode_ok(data.get("passcode")):
        return jsonify({"error": "That access code didn't work — double-check with Shamar."}), 401

    to_email = (data.get("email") or "").strip().lower()
    if not _EMAIL_RE.match(to_email):
        return jsonify({"error": "Enter a valid email address."}), 400

    name = (data.get("name") or "").strip()[:80]
    company = (data.get("company") or "").strip()[:120]
    city = (data.get("city") or "").strip()[:80]
    va_name = (data.get("va_name") or "").strip()[:40]

    from email_templates import va_operator_intro_html
    html = va_operator_intro_html(name=name, company=company, city=city, va_name=va_name)
    if company:
        subject = "Paying junk-removal jobs for {}".format(company)
    elif city:
        subject = "Paying junk-removal jobs in {}".format(city)
    else:
        subject = "Paying junk-removal jobs for your trucks"

    # Sync send (off the event loop via tpool) so the VA sees real failures,
    # from the recruiting identity — _send_email_sync never raises.
    from notifications import _send_email_sync
    from_addr = _va_email_from()
    result = _run(lambda: _send_email_sync(to_email, subject, html,
                                           from_override=from_addr))
    if result is None and from_addr:
        # The recruiting identity can fail independently of the provider
        # (e.g. its domain isn't verified) — retry once from the default
        # sender rather than dead-ending the VA.
        logger.warning("va_hub email from %s failed; retrying from default sender", from_addr)
        result = _run(lambda: _send_email_sync(to_email, subject, html))
    if result is None:
        return jsonify({"error": "Email isn't configured yet — ask Shamar."}), 503

    logger.info("va_hub intro email sent to %s (company=%s)", to_email, company or "-")
    return jsonify({"ok": True, "to": to_email, "subject": subject})



import base64 as _b64

_LOGO_PNG = _b64.b64decode("""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""")


@vahub_bp.route("/va/logo.png", methods=["GET"])
def va_logo():
    resp = Response(_LOGO_PNG, mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


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
      <img class="brand-lg rv" src="/va/logo.png" alt="Umuve" /><div class="eyebrow rv">Internal · VA suite</div>
      <h1 class="display" id="display-gate" aria-label="VA Tools">VA&nbsp;TOOLS</h1>
      <p class="sub rv">Every call ends one of five ways. This sends the right message for each.</p>
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
      <img class="brand" src="/va/logo.png" alt="Umuve" />
      <div class="bar-sub">VA tools · texts send from the Umuve number</div>
    </header>
    <div class="body">
      <h2 class="display display-sm" id="display-hub" aria-label="After the call">AFTER THE&nbsp;CALL</h2>
      <a class="situ rv" href="/optext">
        <div class="situ-key ok-key">YES</div>
        <div class="situ-txt">
          <div class="situ-t">They said yes</div>
          <div class="situ-d">Send the <b>setup link</b> — signs them up to get <b>jobs by text</b>.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ rv" href="/va/text?t=voicemail">
        <div class="situ-key">VM</div>
        <div class="situ-txt">
          <div class="situ-t">They didn&rsquo;t answer</div>
          <div class="situ-d"><b>Voicemail follow-up</b>. No links yet — their <b>YES comes first</b>.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ rv" href="/va/text?t=info">
        <div class="situ-key">FAQ</div>
        <div class="situ-txt">
          <div class="situ-t">They want details</div>
          <div class="situ-d"><b>Info pack</b> — <b>pay split</b>, how jobs work, no commitments.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ rv" href="/va/email">
        <div class="situ-key">@</div>
        <div class="situ-txt">
          <div class="situ-t">They only gave an email</div>
          <div class="situ-d"><b>Intro email</b> from the Umuve address — for listings with <b>no manager phone</b>.</div>
        </div>
        <div class="situ-go">→</div>
      </a>
      <a class="situ rv" href="/coach">
        <div class="situ-key">SOS</div>
        <div class="situ-txt">
          <div class="situ-t">Stuck on a call?</div>
          <div class="situ-d">Ask the <b>Umuve coach</b> — <b>objections</b>, scripts, answers.</div>
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
      <img class="brand-lg rv" src="/va/logo.png" alt="Umuve" /><div class="eyebrow rv">Internal · VA suite</div>
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
      <img class="brand" src="/va/logo.png" alt="Umuve" />
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

/* ---------- round 2: ambient ember + brand + emphasis ---------- */
body{position:relative}
body::before{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;
  background:
    radial-gradient(42vh 42vh at 12% -6%, rgba(255,106,44,.16), transparent 70%),
    radial-gradient(50vh 50vh at 108% 34%, rgba(255,106,44,.07), transparent 70%),
    radial-gradient(34vh 34vh at -8% 86%, rgba(255,106,44,.05), transparent 70%);
  animation:ember 16s ease-in-out infinite alternate}
@keyframes ember{from{opacity:.75;transform:translateY(0)}to{opacity:1;transform:translateY(-2.5vh)}}
#app{position:relative;z-index:1}
.brand{height:20px;display:block}
.brand-lg{height:34px;display:block;margin-bottom:18px}
.display-sm{position:relative;padding-bottom:10px}
.display-sm::after{content:"";position:absolute;left:1vw;bottom:0;width:58px;height:4px;
  border-radius:2px;background:var(--accent);transform-origin:left;transform:scaleX(0)}
.display-sm.uline::after{transform:scaleX(1);transition:transform .6s cubic-bezier(.2,.7,.2,1) .35s}
.situ:hover .situ-key,.situ:active .situ-key{background:var(--accent);color:#0B0E12;border-color:transparent}
.situ-d b{color:var(--ink);font-weight:600}
@media (prefers-reduced-motion:reduce){body::before{animation:none}.display-sm::after{transform:scaleX(1)}}

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
    scope.querySelectorAll(".display-sm").forEach(function(d){
      setTimeout(function(){ d.classList.add("uline"); }, 200);
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


VA_EMAIL_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="robots" content="noindex, nofollow" />
<meta name="theme-color" content="#0B0E12" />
<title>Umuve — Send an Email</title>
<link rel="stylesheet" href="/va/app.css" />
</head>
<body>
<div id="app">
  <section id="gate" class="gate">
    <div class="gatewrap">
      <img class="brand-lg rv" src="/va/logo.png" alt="Umuve" /><div class="eyebrow rv">Internal · VA suite</div>
      <h1 class="display" aria-label="Send an email">SEND AN&nbsp;EMAIL</h1>
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
      <img class="brand" src="/va/logo.png" alt="Umuve" />
      <div class="bar-sub">Emails send from the Umuve address</div>
    </header>

    <div class="body">
      <h2 class="display display-sm rv">INTRO&nbsp;EMAIL</h2>
      <p class="sub rv">For leads whose listing only shows an email — no manager phone. Their reply comes back to the Umuve inbox.</p>

      <form id="email-form" autocomplete="off" class="rv">
        <label class="lbl" for="va">Your first name</label>
        <input id="va" type="text" placeholder="e.g. Tracy" />
        <label class="lbl" for="name">Contact first name <span class="opt">(optional)</span></label>
        <input id="name" type="text" placeholder="e.g. Eric" />
        <label class="lbl" for="company">Company <span class="opt">(optional)</span></label>
        <input id="company" type="text" placeholder="e.g. Gator Dumpster" />
        <label class="lbl" for="city">City / area <span class="opt">(optional)</span></label>
        <input id="city" type="text" placeholder="e.g. West Palm Beach" />
        <label class="lbl" for="lead-email">Their email address</label>
        <input id="lead-email" type="email" inputmode="email" placeholder="name@company.com" />
        <button id="email-send" class="btn" type="submit">Send the intro email</button>
        <p id="email-result" class="result" hidden></p>
      </form>

      <div class="preview rv">
        <div class="preview-h">Subject line</div>
        <div class="bubble" id="subj"></div>
      </div>
      <div class="preview rv">
        <div class="preview-h">What they&rsquo;ll receive <span class="opt">(styled with the Umuve logo when it lands)</span></div>
        <div class="bubble" id="email-bubble"></div>
      </div>

      <div id="email-sent-wrap" class="sent-wrap" hidden>
        <div class="sent-h">Sent this session</div>
        <ul id="email-sent" class="sent"></ul>
      </div>
    </div>
  </section>
</div>
<script src="/va/app.js"></script>
<script src="/va/email.js"></script>
</body>
</html>
"""


VA_EMAIL_JS = r"""(function(){
  var KEY = "umuve_coach_code";   // gate + reveal come from /va/app.js
  var VA_KEY = "umuve_va_name";
  var form = document.getElementById("email-form");
  if(!form) return;
  function code(){ return localStorage.getItem(KEY) || ""; }
  function v(id){ return document.getElementById(id).value.trim(); }
  function greet(n){ return n ? "Hi " + n + "," : "Hi there,"; }

  function subject(){
    var c = v("company"), ci = v("city");
    if(c) return "Paying junk-removal jobs for " + c;
    if(ci) return "Paying junk-removal jobs in " + ci;
    return "Paying junk-removal jobs for your trucks";
  }
  function body(){
    var va = v("va") || "the Umuve team";
    var who = v("company") || "you";
    var area = v("city") || "South Florida";
    return greet(v("name")) + "\n\n" +
      "I'm " + va + " with Umuve — I tried reaching " + who + " by phone and figured email might be easier.\n\n" +
      "We're a junk removal marketplace in South Florida. Customers book and pay for pickups on our platform, and we send those jobs by text to local hauling companies like yours.\n\n" +
      "✓ Booked, paid jobs sent by text — take only the ones you want\n" +
      "✓ Keep ~72% of the job price plus 100% of tips\n" +
      "✓ Get paid after each job — same-day payout available\n" +
      "✓ No fees, no contracts, no minimums\n\n" +
      "We're live in Palm Beach County now and adding haulers across " + area + ". Setup takes about 2 minutes.\n\n" +
      "[ See How It Works → goumuve.com/operators ]\n\n" +
      "Or just reply to this email and I'll get you set up.\n\n" +
      "— " + va + ", Umuve";
  }
  function refresh(){
    document.getElementById("subj").textContent = subject();
    document.getElementById("email-bubble").textContent = body();
  }

  document.getElementById("va").value = localStorage.getItem(VA_KEY) || "";
  ["va","name","company","city"].forEach(function(id){
    document.getElementById(id).addEventListener("input", refresh);
  });
  refresh();

  var busy = false;
  function setResult(kind, text){
    var r = document.getElementById("email-result");
    r.textContent = text; r.className = "result show " + kind;
  }
  form.addEventListener("submit", function(e){
    e.preventDefault();
    if(busy) return;
    var va = v("va"), email = v("lead-email");
    if(!va){ setResult("bad", "Add your first name so the lead knows who wrote."); return; }
    if(!email || email.indexOf("@") < 1){ setResult("bad", "Enter their email address first."); return; }
    localStorage.setItem(VA_KEY, va);
    var btn = document.getElementById("email-send");
    busy = true; btn.disabled = true; btn.textContent = "Sending…";
    fetch("/api/va/email", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ passcode: code(), va_name: va, name: v("name"),
                             company: v("company"), city: v("city"), email: email })
    }).then(function(r){ return r.json().then(function(j){ return {status:r.status, body:j}; }); })
    .then(function(res){
      busy = false; btn.disabled = false; btn.textContent = "Send the intro email";
      if(res.status === 401){
        localStorage.removeItem(KEY);
        setResult("bad", "That code didn't work — double-check with Shamar, then reload this page.");
        return;
      }
      if(res.status >= 200 && res.status < 300 && res.body.ok){
        setResult("ok", "Sent to " + (res.body.to || email) + " ✅");
        var li = document.createElement("li");
        li.textContent = (v("company") ? v("company") + " — " : "") + (res.body.to || email);
        var list = document.getElementById("email-sent");
        list.insertBefore(li, list.firstChild);
        document.getElementById("email-sent-wrap").hidden = false;
        ["name","company","city","lead-email"].forEach(function(id){
          document.getElementById(id).value = "";
        });
        refresh();
      } else {
        setResult("bad", res.body.error || "Couldn't send — try again.");
      }
    }).catch(function(){
      busy = false; btn.disabled = false; btn.textContent = "Send the intro email";
      setResult("bad", "Couldn't reach the server — check your connection and try again.");
    });
  });
})();
"""
