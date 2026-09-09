/* Call Desk — compliance layer (Phase 2). Loads BEFORE /va/calls.js.
 *
 * Adds, without touching the desk's own script:
 *   - a "They asked not to be called" outcome → POST /api/va/compliance/dnc
 *   - a red DO NOT CALL chip on the card when the number is on the list
 *   - a calling-hours banner in the line panel + a click guard on the dial
 *     targets (#c-tel, #c-direct, #desk-call-btn) while the window is closed
 *   - a one-line recording/consent note under the Power/Copilot bar
 *
 * It watches the desk's own card traffic (a thin fetch wrapper on
 * /api/va/calls/*) so it never makes an extra request per card.
 *
 * Globals it publishes:
 *   window.__deskCallsBlocked   true while the calling window is closed
 *   "desk:refresh" (window)     dispatched after a DNC so calls.js can deal
 *                               the next card (calls.js should listen:
 *                               window.addEventListener("desk:refresh", fetchNext)).
 *                               Until that listener exists we fall back to reload.
 */
(function(){
  "use strict";
  var JWT_KEY = "umuve_desk_jwt", CODE_KEY = "umuve_coach_code", VA_KEY = "umuve_va_name", ME_KEY = "umuve_desk_me";
  var lastCard = null;       // the card the desk is showing, from its own API responses
  var windowState = null;    // last calling-window payload
  window.__deskCallsBlocked = false;

  function ls(k){ try { return localStorage.getItem(k) || ""; } catch(e){ return ""; } }
  function jwt(){ return ls(JWT_KEY); }
  function code(){ return ls(CODE_KEY); }
  function me(){ try { return JSON.parse(ls(ME_KEY) || "null"); } catch(e){ return null; } }
  function vaName(){ var m = me(); return (m && m.name) || ls(VA_KEY) || ""; }
  function signedIn(){ return !!jwt() || !!code(); }
  function $(id){ return document.getElementById(id); }
  function el(tag, cls, text){
    var n = document.createElement(tag);
    if(cls) n.className = cls;
    if(text != null) n.textContent = text;
    return n;
  }
  function digitsOf(s){ var d = String(s || "").replace(/\D/g, ""); return d.length >= 10 ? d.slice(-10) : d; }
  function cardDigits(){ var ph = $("c-phone"); return ph ? digitsOf(ph.textContent) : ""; }

  var realFetch = window.fetch;
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { body.code = code(); body.va_name = vaName(); }
    return realFetch.call(window, path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }

  // ---- stylesheet: CSP is style-src 'self', so no inline styles — link ours
  function loadCss(){
    if(document.querySelector('link[href^="/static/desk-compliance.css"]')) return;
    var l = document.createElement("link");
    l.rel = "stylesheet"; l.href = "/static/desk-compliance.css?v=1";
    document.head.appendChild(l);
  }

  // ---- toast (our own element so we never fight the desk's timer)
  var toastEl = null, toastTimer = null;
  function toast(msg){
    if(!toastEl){ toastEl = el("p", "cmp-toast"); toastEl.id = "cmp-toast"; toastEl.setAttribute("role", "status"); toastEl.hidden = true; document.body.appendChild(toastEl); }
    toastEl.textContent = msg; toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function(){ toastEl.hidden = true; }, 4500);
  }

  // ---- watch the desk's own card traffic
  if(realFetch){
    window.fetch = function(input, init){
      var url = typeof input === "string" ? input : ((input && input.url) || "");
      var p = realFetch.apply(this, arguments);
      if(/^\/api\/va\/calls\//.test(url)){
        p.then(function(r){
          if(!r || !r.ok) return;
          try { r.clone().json().then(onDeskResponse, function(){}); } catch(e){}
        }, function(){});
      }
      return p;
    };
  }
  function onDeskResponse(body){
    if(!body || typeof body !== "object") return;
    if(body.card){ lastCard = body.card; applyCard(body.card); }
    else if(body.empty){ lastCard = null; applyCard(null); }
  }

  // ---- DO NOT CALL chip on the card
  function ensureChip(){
    var chip = $("c-dnc"); if(chip) return chip;
    var tier = $("c-tier"); if(!tier) return null;
    chip = el("span", "chip dncchip", "DO NOT CALL"); chip.id = "c-dnc"; chip.hidden = true;
    tier.insertAdjacentElement("afterend", chip);
    return chip;
  }
  function applyCard(card){
    var chip = ensureChip();
    var c = card && card.compliance ? card.compliance : null;
    var dnc = !!(c && c.dnc);
    if(chip) chip.hidden = !dnc;
    var btn = $("oc-dnc"); if(btn) btn.hidden = dnc;   // already on the list — nothing to add
    if(c && typeof c.window_open === "boolean"){ applyWindow({open: c.window_open, note: c.window_note}); }
  }

  // ---- "They asked not to be called" outcome
  function setBusy(b){ document.querySelectorAll("#outcomes button").forEach(function(x){ x.disabled = b; }); }
  function ensureDncButton(){
    var box = $("outcomes"); if(!box || $("oc-dnc")) return;
    var btn = el("button", "oc oc-bad oc-dnc", "They asked not to be called");
    btn.id = "oc-dnc"; btn.type = "button"; btn.setAttribute("data-cmp", "dnc");
    btn.title = "Blocks this number for calls and texts, closes the card, and deals the next one.";
    box.insertBefore(btn, box.querySelector(".oc-skip") || null);
    // Stop here: the desk's own #outcomes handler must not see this click.
    btn.addEventListener("click", function(e){ e.preventDefault(); e.stopPropagation(); markDoNotCall(btn); });
  }
  function markDoNotCall(btn){
    if(btn.disabled) return;
    var digits = cardDigits();
    if(digits.length !== 10){ toast("No card on the desk to mark."); return; }
    var note = ($("note") && $("note").value || "").trim();
    var body = {phone: digits, note: note, source: "call_request"};
    if(lastCard && digitsOf(lastCard.phone) === digits) body.prospect_id = lastCard.id;
    setBusy(true);
    post("/api/va/compliance/dnc", body).then(function(r){
      setBusy(false);
      if(r.status === 401){ toast("Please sign in again."); return; }
      if(r.status !== 200){ toast((r.body && r.body.error) || "Couldn't save that — try again."); return; }
      var chip = ensureChip(); if(chip) chip.hidden = false;
      if(lastCard && lastCard.compliance) lastCard.compliance.dnc = true;
      toast("Done — they won't be called or texted again.");
      advance(digits);
    }).catch(function(){ setBusy(false); toast("No connection — check your internet and try again."); });
  }
  function advance(digits){
    // The desk owns rendering. Ask it for the next card; if nothing picks the
    // event up yet (calls.js listener not wired), fall back to a reload.
    var before = $("c-company") ? $("c-company").textContent : "";
    try { window.dispatchEvent(new CustomEvent("desk:refresh", {detail: {reason: "dnc", phone: digits}})); } catch(e){}
    setTimeout(function(){
      var card = $("card");
      var same = card && !card.hidden && cardDigits() === digits && $("c-company").textContent === before;
      if(same) location.reload();
    }, 1200);
  }

  // ---- calling-hours window
  var banner = null;
  function ensureBanner(){
    if(banner) return banner;
    var line = $("line"); var head = line && line.querySelector(".ln-head");
    if(!head) return null;
    banner = el("div", "cw-banner"); banner.id = "cw-banner"; banner.hidden = true; banner.setAttribute("role", "status");
    head.insertAdjacentElement("afterend", banner);
    return banner;
  }
  function applyWindow(w){
    windowState = w || null;
    var blocked = !!(w && w.open === false);
    window.__deskCallsBlocked = blocked;
    document.body.classList.toggle("calls-closed", blocked);
    var b = ensureBanner(); if(!b) return;
    b.textContent = (w && w.note) || "Calling window is closed — texting still works.";
    b.hidden = !blocked;
  }
  function refreshWindow(){
    if(!signedIn()) return;
    post("/api/va/compliance/window", {}).then(function(r){ if(r.status === 200) applyWindow(r.body); }).catch(function(){});
  }
  function guard(e, msg){ e.preventDefault(); e.stopImmediatePropagation(); toast(msg); }
  document.addEventListener("click", function(e){
    var t = e.target && e.target.closest ? e.target.closest("#c-tel, #c-direct, #desk-call-btn") : null;
    if(!t) return;
    var onList = !!(lastCard && lastCard.compliance && lastCard.compliance.dnc && digitsOf(lastCard.phone) === cardDigits());
    if(onList){ guard(e, "This number is on the do-not-call list."); return; }
    if(window.__deskCallsBlocked){ guard(e, (windowState && windowState.note) || "Calling window is closed — texting still works."); }
  }, true);

  // ---- recording / consent note under the Power/Copilot bar
  function ensurePolicyNote(pol){
    var cp = $("cp-toggle"), pd = $("pdbar");
    if(!cp || !pd) return;
    var note = $("cp-policy");
    if(!note){
      note = el("p", "cmp-note"); note.id = "cp-policy";
      pd.insertAdjacentElement("afterend", note);
      // Only meaningful while Copilot is offered (the desk unhides #cp-toggle itself).
      var sync = function(){ note.hidden = cp.hidden; };
      sync();
      try { new MutationObserver(sync).observe(cp, {attributes: true, attributeFilter: ["hidden"]}); } catch(e){}
    }
    note.textContent = (pol && pol.desk_note) || "Copilot records the call — the other party hears a recording notice first.";
  }
  function loadPolicy(){
    if(!signedIn() || $("cp-policy")) return;
    post("/api/va/compliance/policy", {}).then(function(r){ if(r.status === 200) ensurePolicyNote(r.body); }).catch(function(){});
  }

  // ---- boot
  function boot(){
    loadCss(); ensureChip(); ensureDncButton(); ensureBanner();
    if(signedIn()){ refreshWindow(); loadPolicy(); }
    setInterval(refreshWindow, 60000);
    var tool = $("tool");   // sign-in happens after boot: watch the desk open
    if(tool){
      try { new MutationObserver(function(){ if(!tool.hidden){ refreshWindow(); loadPolicy(); } })
              .observe(tool, {attributes: true, attributeFilter: ["hidden"]}); } catch(e){}
    }
  }
  if($("outcomes")) boot(); else document.addEventListener("DOMContentLoaded", boot);
})();
