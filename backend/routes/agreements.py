"""
B2B service agreements with in-app e-signature.

Flow:
  1. sevs opens /agreements (passcode-gated, same TRIXIE_ASSISTANT_PASSCODE as
     the VA tool suite), enters the client's details -> agreement is created
     and the signing link is emailed to the client (and returned for texting).
  2. Client opens /sign/<token> on any device: reads the full agreement,
     types their name/title, optionally draws a signature, checks the ESIGN
     consent box, and signs.
  3. Backend stamps the executed copy (signer, timestamp, IP, user agent),
     stores an immutable HTML snapshot + SHA-256, and emails the executed
     agreement to both parties. Re-opening the link shows the executed copy.

Legal shape (ESIGN/UETA click-to-sign): explicit consent language, signer
identity, audit trail, retained records for both parties. Not a substitute
for attorney review of the underlying terms.
"""
import hashlib
import hmac
import logging
import os
import secrets

from flask import Blueprint, Response, jsonify, request

from extensions import limiter
from models import db, Agreement, utcnow

logger = logging.getLogger(__name__)

agreements_bp = Blueprint("agreements", __name__)

SEVS_NOTIFY_EMAIL = "se7nz7@gmail.com"


def _passcode_ok(supplied):
    expected = os.environ.get("TRIXIE_ASSISTANT_PASSCODE", "")
    if not expected:
        return False  # fail closed
    return hmac.compare_digest(str(supplied or ""), str(expected))


def _client_ip():
    fwd = request.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() if fwd else request.remote_addr) or "unknown"


# ---------------------------------------------------------------------------
# Agreement document — commercial_v1
# Mirrors the Jul 2026 commercial rate card; keep the numbers in sync with
# BULK_MARGINAL_RATES / the B2B rate card when they change.
# ---------------------------------------------------------------------------
_DOC_CSS = """
:root{--ink:#1A1A1A;--red:#C52222;--red-deep:#9E1B1B;--paper:#FFF;--panel:#F6F4F0;--line:#DDD7CB;--muted:#6E675C}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;color:var(--ink);background:var(--panel);line-height:1.5;font-size:13.5px}
.sheet{max-width:820px;margin:16px auto;background:var(--paper);padding:44px 48px 36px;box-shadow:0 1px 30px rgba(26,26,26,.10)}
.mono{font-family:"SF Mono",Menlo,Consolas,monospace}
header{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:3px solid var(--ink);padding-bottom:18px;margin-bottom:22px}
header img{width:120px;height:auto}
.doc-meta{text-align:right;font-size:11.5px;color:var(--muted);line-height:1.7}
h1{font-size:24px;font-weight:800;letter-spacing:-.02em;margin-top:10px}
.parties{background:var(--panel);padding:16px 18px;margin:18px 0 6px;display:grid;grid-template-columns:1fr 1fr;gap:16px;font-size:13px}
.parties .lbl{font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--red);font-weight:700;margin-bottom:6px}
h2{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--red);font-weight:700;margin:20px 0 7px;padding-top:12px;border-top:1px solid var(--line)}
h2 .n{color:var(--muted);font-weight:600;margin-right:8px}
p{margin-bottom:8px}
ul{list-style:none;margin-bottom:8px}
li{padding:3px 0 3px 16px;position:relative}
li::before{content:"";position:absolute;left:0;top:11px;width:7px;height:2.5px;background:var(--red)}
table{width:100%;border-collapse:collapse;margin:10px 0 4px}
th{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);text-align:left;padding-bottom:6px;border-bottom:1.5px solid var(--ink)}
th.num,td.num{text-align:right}
td{padding:7px 0;border-bottom:1px solid var(--line)}
.executed{background:var(--panel);border-left:4px solid var(--red);padding:16px 18px;margin-top:26px}
.executed .lbl{font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--red);font-weight:700;margin-bottom:8px}
.executed img{max-height:64px;display:block;margin:8px 0}
.sign-panel{background:var(--panel);padding:22px;margin-top:26px}
.sign-panel h3{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--red);margin-bottom:12px}
.sign-panel label{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:12px 0 4px}
.sign-panel input[type=text]{width:100%;padding:10px;border:1.5px solid var(--ink);font-size:15px;background:#fff}
#sigpad{border:1.5px solid var(--ink);background:#fff;width:100%;height:120px;touch-action:none;display:block}
.sig-tools{font-size:12px;color:var(--muted);margin-top:4px}
.sig-tools a{color:var(--red);cursor:pointer}
.consent{display:flex;gap:10px;align-items:flex-start;margin:16px 0;font-size:12.5px}
.consent input{margin-top:3px;transform:scale(1.3)}
button.sign{width:100%;padding:14px;background:var(--red);color:#fff;border:0;font-size:16px;font-weight:700;letter-spacing:.04em;cursor:pointer}
button.sign:disabled{background:#c9c2b6;cursor:not-allowed}
.err{color:var(--red-deep);font-size:13px;margin-top:8px;display:none}
footer{margin-top:30px;padding-top:12px;border-top:3px solid var(--ink);font-size:11px;color:var(--muted);display:flex;justify-content:space-between}
@media(max-width:640px){.sheet{padding:26px 18px;margin:0}.parties{grid-template-columns:1fr}h1{font-size:21px}}
@media print{body{background:#fff}.sheet{box-shadow:none;margin:0;padding:24px 30px}.sign-panel{display:none}}
"""


def _doc_body(ag):
    """The agreement text with the client's details filled in."""
    effective = (ag.signed_at or ag.created_at)
    effective_str = effective.strftime("%B %d, %Y") if effective else ""
    phone = ag.client_phone or "—"
    return """
<header>
  <div>
    <img src="https://goumuve.com/logo-full.png" alt="Umuve">
    <h1>Commercial Services Agreement</h1>
  </div>
  <div class="doc-meta mono">DEBRIS REMOVAL &amp; CLEANOUT<br>PALM BEACH · BROWARD<br>goumuve.com · (561) 944-1636</div>
</header>

<div class="parties">
  <div>
    <div class="lbl">Provider</div>
    Umuve ("Umuve")<br>West Palm Beach, Florida<br>bookings@goumuve.com
  </div>
  <div>
    <div class="lbl">Client</div>
    Company: <b>{company}</b><br>
    Contact: <b>{name}</b><br>
    Email / phone: <b>{email}</b> · {phone}
  </div>
</div>
<p style="font-size:12.5px;color:var(--muted)">Effective date: <b>{effective}</b></p>

<h2><span class="n">1</span>Services</h2>
<p>Umuve provides non-hazardous debris removal — post-demolition and construction debris, property cleanouts, and junk removal — at job sites the Client designates within Palm Beach and Broward counties. Work is performed by Umuve's licensed and insured operator network. Every job includes loading, hauling, lawful disposal, and before/after photo documentation.</p>

<h2><span class="n">2</span>Scheduling</h2>
<p>Umuve targets next-business-day service with two-hour arrival windows. The Client may book by phone, text, email, or through the Umuve business portal (portal.goumuve.com), where job history and invoices are available at any time.</p>

<h2><span class="n">3</span>Pricing &amp; quotes</h2>
<p>Rates follow <b>Exhibit A</b>. Each job receives a written quote (from photos or a site visit) before work begins; the quoted price is binding. If site conditions differ materially from what was quoted, Umuve will present a revised price for approval <i>before</i> proceeding — work never continues past an unapproved change.</p>
<table>
  <tr><th>Exhibit A — C&amp;D per-load rates</th><th class="num">Rate</th></tr>
  <tr><td>Quarter load</td><td class="num mono">$445</td></tr>
  <tr><td>Half load</td><td class="num mono">$795</td></tr>
  <tr><td>Three-quarter load</td><td class="num mono">$995</td></tr>
  <tr><td>Full load (disposal incl. to 2 tons)</td><td class="num mono">$1,195</td></tr>
  <tr><td>Each additional full load, same visit</td><td class="num mono">$995</td></tr>
  <tr><td>Tonnage beyond included allowance</td><td class="num mono">$85 / ton</td></tr>
</table>
<p style="font-size:12px;color:var(--muted)">Dense material (concrete, dirt, tile, roofing) loads to half-bed by legal weight and is billed at the half-load rate per bed. Rates guaranteed 90 days from the effective date, then adjustable with 30 days' written notice.</p>

<h2><span class="n">4</span>Volume discount</h2>
<p>Three or more completed cleanouts in a calendar month earn a <b>10% discount on that month's invoices</b>, applied automatically.</p>

<h2><span class="n">5</span>Payment</h2>
<ul>
  <li>Payment is due on job completion by card on file or payment link.</li>
  <li>After three paid jobs, the Client may elect net-15 invoicing.</li>
  <li>Amounts 15+ days past due accrue 1.5% per month. Umuve may pause scheduling on accounts 30+ days past due.</li>
</ul>

<h2><span class="n">6</span>Excluded materials</h2>
<p>Umuve does not haul: asbestos or suspected asbestos-containing material, wet paint, solvents, chemicals, fuels, sealed or pressurized tanks, or regulated hazardous waste. <b>The Client warrants that debris presented for removal contains no such materials</b> and that any required demolition permits and abatement were the Client's responsibility and are complete.</p>

<h2><span class="n">7</span>Donation &amp; diversion</h2>
<p>Where materials are reusable, Umuve may donate them to local partner organizations rather than landfill them. Donation receipts and diversion documentation are available to the Client on request at no charge.</p>

<h2><span class="n">8</span>Insurance &amp; liability</h2>
<p>Operators carry commercial auto and general liability coverage; certificates of insurance are available on request. Property-damage claims must be reported within 48 hours of job completion. Except for gross negligence or willful misconduct, each party's total liability under this Agreement is capped at amounts paid or payable for the job giving rise to the claim.</p>

<h2><span class="n">9</span>Term &amp; electronic signature</h2>
<p>This Agreement runs month-to-month from the effective date. Either party may end it with 30 days' written notice. Jobs already scheduled are completed and paid under the terms above. This Agreement is governed by Florida law; venue is Palm Beach County. <b>The parties agree that this Agreement may be executed electronically</b> and that an electronic signature carries the same force as a handwritten one.</p>
""".format(
        company=ag.client_company,
        name=ag.client_name,
        email=ag.client_email,
        phone=phone,
        effective=effective_str,
    )


def _executed_block(ag):
    sig_img = (
        '<img src="{}" alt="signature">'.format(ag.signature_image)
        if ag.signature_image else ""
    )
    return """
<div class="executed">
  <div class="lbl">Signed electronically</div>
  {sig_img}
  <p><b>{signer}</b>{title} — on behalf of {company}</p>
  <p class="mono" style="font-size:11.5px;color:var(--muted)">
    {when} UTC · IP {ip}<br>Record SHA-256 {sha}
  </p>
  <p style="margin-top:8px">Accepted for Umuve by Shamar Donaldson, Founder.</p>
</div>
""".format(
        sig_img=sig_img,
        signer=ag.signer_name,
        title=", {}".format(ag.signer_title) if ag.signer_title else "",
        company=ag.client_company,
        when=ag.signed_at.strftime("%B %d, %Y %H:%M:%S") if ag.signed_at else "",
        ip=ag.signer_ip or "—",
        sha=(ag.document_sha256 or "")[:16] + "…",
    )


_SIGN_PANEL = """
<div class="sign-panel" id="signPanel">
  <h3>Sign this agreement</h3>
  <label for="signerName">Full legal name</label>
  <input type="text" id="signerName" autocomplete="name" placeholder="e.g. Marcos Rivera">
  <label for="signerTitle">Title (optional)</label>
  <input type="text" id="signerTitle" placeholder="e.g. Owner, General Contractor">
  <label>Draw your signature (optional)</label>
  <canvas id="sigpad"></canvas>
  <div class="sig-tools"><a id="sigClear">Clear signature</a></div>
  <div class="consent">
    <input type="checkbox" id="consent">
    <span>I agree to do business electronically and to sign this Agreement
    electronically. I have read the Agreement above and agree to its terms
    on behalf of the Client named in it.</span>
  </div>
  <button class="sign" id="signBtn" disabled>Sign agreement</button>
  <div class="err" id="signErr"></div>
</div>
<script>
(function(){
  var canvas=document.getElementById('sigpad'),ctx=canvas.getContext('2d'),drawn=false,drawing=false;
  function fit(){var r=canvas.getBoundingClientRect();canvas.width=r.width*2;canvas.height=240;
    ctx.scale(2,2);ctx.lineWidth=2;ctx.lineCap='round';ctx.strokeStyle='#1A1A1A';}
  fit();
  function pos(e){var r=canvas.getBoundingClientRect();
    return {x:e.clientX-r.left,y:e.clientY-r.top};}
  canvas.addEventListener('pointerdown',function(e){drawing=true;drawn=true;
    var p=pos(e);ctx.beginPath();ctx.moveTo(p.x,p.y);e.preventDefault();});
  canvas.addEventListener('pointermove',function(e){if(!drawing)return;
    var p=pos(e);ctx.lineTo(p.x,p.y);ctx.stroke();e.preventDefault();});
  ['pointerup','pointerleave'].forEach(function(ev){
    canvas.addEventListener(ev,function(){drawing=false;});});
  document.getElementById('sigClear').addEventListener('click',function(){
    ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,canvas.width,canvas.height);fit();drawn=false;});
  var name=document.getElementById('signerName'),consent=document.getElementById('consent'),
      btn=document.getElementById('signBtn'),err=document.getElementById('signErr');
  function gate(){btn.disabled=!(name.value.trim().length>1&&consent.checked);}
  name.addEventListener('input',gate);consent.addEventListener('change',gate);
  btn.addEventListener('click',function(){
    btn.disabled=true;btn.textContent='Signing…';err.style.display='none';
    fetch('/api/sign/'+window.__AG_TOKEN,{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({signer_name:name.value.trim(),
        signer_title:document.getElementById('signerTitle').value.trim(),
        signature_image:drawn?canvas.toDataURL('image/png'):null,
        consent:consent.checked})})
    .then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
    .then(function(res){
      if(res.ok){window.location.reload();}
      else{err.textContent=res.j.error||'Signing failed — try again.';
        err.style.display='block';btn.disabled=false;btn.textContent='Sign agreement';}})
    .catch(function(){err.textContent='Network error — try again.';
      err.style.display='block';btn.disabled=false;btn.textContent='Sign agreement';});
  });
})();
</script>
"""


def _page(title, inner, token=None):
    token_js = (
        '<script>window.__AG_TOKEN=%r;</script>' % token if token else ""
    )
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta name=\"robots\" content=\"noindex\">"
        "<title>{title}</title><style>{css}</style></head><body>"
        "{token_js}<div class=\"sheet\">{inner}"
        "<footer><div>Umuve — Hauling made simple.</div>"
        "<div class=\"mono\">UMUVE AGREEMENTS</div></footer>"
        "</div></body></html>"
    ).format(title=title, css=_DOC_CSS, token_js=token_js, inner=inner)


# ---------------------------------------------------------------------------
# Public: view + sign
# ---------------------------------------------------------------------------
@agreements_bp.route("/sign/<token>", methods=["GET"])
@limiter.limit("30 per minute")
def sign_page(token):
    ag = Agreement.query.filter_by(token=token).first()
    if ag is None or ag.status == "void":
        return Response(
            _page("Agreement not found",
                  "<h1>Agreement not found</h1><p>This signing link is invalid "
                  "or has been withdrawn. Contact bookings@goumuve.com.</p>"),
            status=404, mimetype="text/html")

    if ag.status == "signed" and ag.executed_html:
        return Response(ag.executed_html, mimetype="text/html")

    if ag.viewed_at is None:
        ag.viewed_at = utcnow()
        ag.status = "viewed"
        db.session.commit()

    inner = _doc_body(ag) + _SIGN_PANEL
    return Response(
        _page("Umuve — Sign your service agreement", inner, token=token),
        mimetype="text/html")


@agreements_bp.route("/api/sign/<token>", methods=["POST"])
@limiter.limit("10 per minute")
def sign_submit(token):
    ag = Agreement.query.filter_by(token=token).first()
    if ag is None or ag.status == "void":
        return jsonify({"error": "Agreement not found"}), 404
    if ag.status == "signed":
        return jsonify({"error": "This agreement has already been signed."}), 409

    data = request.get_json() or {}
    signer_name = (data.get("signer_name") or "").strip()
    if len(signer_name) < 2:
        return jsonify({"error": "Full legal name is required."}), 400
    if not data.get("consent"):
        return jsonify({"error": "You must agree to sign electronically."}), 400

    sig_img = data.get("signature_image")
    if sig_img and not str(sig_img).startswith("data:image/png;base64,"):
        sig_img = None  # only accept the canvas PNG format we generate

    ag.signer_name = signer_name[:120]
    ag.signer_title = (data.get("signer_title") or "").strip()[:120] or None
    ag.signature_image = sig_img
    ag.signer_ip = _client_ip()[:64]
    ag.signer_user_agent = (request.headers.get("User-Agent") or "")[:255]
    ag.signed_at = utcnow()
    ag.status = "signed"

    executed_inner = _doc_body(ag) + _executed_block(ag)
    # Hash the document + signer identity, then stamp the hash into the
    # snapshot (the snapshot therefore embeds a truncated copy of the hash;
    # the full hash lives on the row).
    ag.document_sha256 = hashlib.sha256(
        (executed_inner + "|" + ag.signer_name + "|" + ag.signed_at.isoformat())
        .encode("utf-8")).hexdigest()
    executed_inner = _doc_body(ag) + _executed_block(ag)
    ag.executed_html = _page(
        "Umuve — Executed service agreement ({})".format(ag.client_company),
        executed_inner)
    db.session.commit()

    # Email executed copies — best-effort, never blocks the signature.
    try:
        from email_service import send_email
        subject = "Executed: Umuve service agreement — {}".format(ag.client_company)
        send_email(to_email=ag.client_email, subject=subject,
                   html_content=ag.executed_html)
        send_email(to_email=SEVS_NOTIFY_EMAIL,
                   subject="SIGNED: {} ({})".format(ag.client_company, ag.signer_name),
                   html_content=ag.executed_html)
    except Exception:
        logger.exception("agreement %s: executed-copy email failed", ag.id)

    return jsonify({"success": True, "status": "signed"}), 200


# ---------------------------------------------------------------------------
# Console (passcode-gated, same code as the VA tool suite)
# ---------------------------------------------------------------------------
_CONSOLE_HTML = """
<header>
  <div><img src="https://goumuve.com/logo-full.png" alt="Umuve"><h1>Agreements</h1></div>
  <div class="doc-meta mono">SEND · TRACK · SIGNED COPIES</div>
</header>
<div class="sign-panel" style="margin-top:8px">
  <h3>New agreement</h3>
  <label>Access code</label><input type="text" id="pc" autocomplete="off">
  <label>Company</label><input type="text" id="company" placeholder="e.g. Rivera Demolition LLC">
  <label>Contact name</label><input type="text" id="cname" placeholder="e.g. Marcos Rivera">
  <label>Email</label><input type="text" id="cemail" placeholder="who receives the signing link">
  <label>Phone (optional)</label><input type="text" id="cphone">
  <button class="sign" id="createBtn" style="margin-top:14px">Create &amp; email signing link</button>
  <div class="err" id="createErr"></div>
  <div id="createOk" style="display:none;margin-top:12px;font-size:13px">
    <b>Link created and emailed.</b> Text it too:<br>
    <input type="text" id="linkOut" readonly onclick="this.select()">
  </div>
</div>
<div class="sign-panel" style="margin-top:16px">
  <h3>Recent</h3>
  <button class="sign" id="listBtn">Load recent agreements</button>
  <div id="listOut" style="margin-top:10px;font-size:13px"></div>
</div>
<script>
function v(id){return document.getElementById(id).value.trim();}
document.getElementById('createBtn').addEventListener('click',function(){
  var b=this;b.disabled=true;
  fetch('/api/agreements/create',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({passcode:v('pc'),client_company:v('company'),
      client_name:v('cname'),client_email:v('cemail'),client_phone:v('cphone')})})
  .then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
  .then(function(res){b.disabled=false;var err=document.getElementById('createErr');
    if(res.ok){err.style.display='none';
      document.getElementById('createOk').style.display='block';
      document.getElementById('linkOut').value=res.j.sign_url;}
    else{err.textContent=res.j.error||'Failed';err.style.display='block';}})
  .catch(function(){b.disabled=false;});
});
document.getElementById('listBtn').addEventListener('click',function(){
  fetch('/api/agreements/list',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({passcode:v('pc')})})
  .then(function(r){return r.json();})
  .then(function(j){
    var rows=(j.agreements||[]).map(function(a){
      return '<tr><td>'+a.client_company+'</td><td>'+a.client_name+'</td>'+
        '<td class="mono">'+a.status+'</td><td class="mono" style="font-size:11px">'+
        (a.signed_at||a.created_at||'').slice(0,10)+'</td></tr>';}).join('');
    document.getElementById('listOut').innerHTML=
      '<table><tr><th>Company</th><th>Contact</th><th>Status</th><th>Date</th></tr>'+rows+'</table>';});
});
</script>
"""


@agreements_bp.route("/agreements", methods=["GET"])
def console_page():
    return Response(_page("Umuve — Agreements", _CONSOLE_HTML),
                    mimetype="text/html")


@agreements_bp.route("/api/agreements/create", methods=["POST"])
@limiter.limit("10 per minute")
def create_agreement():
    data = request.get_json() or {}
    if not _passcode_ok(data.get("passcode")):
        return jsonify({"error": "Invalid access code"}), 403

    company = (data.get("client_company") or "").strip()
    name = (data.get("client_name") or "").strip()
    email = (data.get("client_email") or "").strip()
    if not company or not name or "@" not in email:
        return jsonify({"error": "Company, contact name, and a valid email are required."}), 400

    ag = Agreement(
        token=secrets.token_urlsafe(24),
        client_company=company[:200],
        client_name=name[:120],
        client_email=email[:255],
        client_phone=(data.get("client_phone") or "").strip()[:40] or None,
    )
    db.session.add(ag)
    db.session.commit()

    base = os.environ.get("PUBLIC_BASE_URL", "https://junkos-backend.onrender.com")
    sign_url = "{}/sign/{}".format(base.rstrip("/"), ag.token)

    try:
        from email_service import send_email
        send_email(
            to_email=ag.client_email,
            subject="Your Umuve service agreement is ready to sign",
            html_content=(
                '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;'
                'max-width:560px;margin:0 auto;padding:32px 24px">'
                '<p><img src="https://goumuve.com/logo-full.png" alt="Umuve" width="120"></p>'
                '<h2 style="color:#111">Hi {name},</h2>'
                '<p style="color:#444;line-height:1.6">Your Umuve commercial services '
                'agreement for <b>{company}</b> is ready. It takes about two minutes to '
                'review and sign — rates, terms, and everything we discussed are in it.</p>'
                '<p style="margin:24px 0"><a href="{url}" style="background:#C52222;'
                'color:#fff;padding:13px 26px;text-decoration:none;font-weight:700">'
                'Review &amp; sign</a></p>'
                '<p style="color:#888;font-size:13px">Questions? Just reply to this '
                'email or call (561) 944-1636.</p></div>'
            ).format(name=ag.client_name, company=ag.client_company, url=sign_url),
        )
    except Exception:
        logger.exception("agreement %s: signing-link email failed", ag.id)

    return jsonify({"success": True, "sign_url": sign_url,
                    "agreement": ag.to_dict()}), 201


@agreements_bp.route("/api/agreements/list", methods=["POST"])
@limiter.limit("20 per minute")
def list_agreements():
    data = request.get_json() or {}
    if not _passcode_ok(data.get("passcode")):
        return jsonify({"error": "Invalid access code"}), 403
    rows = (Agreement.query.order_by(Agreement.created_at.desc())
            .limit(50).all())
    return jsonify({"agreements": [a.to_dict() for a in rows]}), 200
