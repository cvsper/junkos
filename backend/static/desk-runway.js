/* Desk runway — how much phone line is left, across the top of the Call Desk.
   Reads /api/va/desk/capacity (units and days only, never a dollar figure),
   draws a rail at the top edge of the window and a small tag under it.
   Green when there's plenty; red and breathing when it's low; red and still
   when the line is off. Rechecks every five minutes, and right after the
   desk signs in. CSS in /static/desk-runway.css (the desk CSP is
   style-src 'self', so no inline styles here). */
(function(){
  "use strict";
  var JWT_KEY = "umuve_desk_jwt", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";
  var EVERY = 5 * 60 * 1000, RETRY = 30 * 1000;
  function ls(k){ try { return localStorage.getItem(k) || ""; } catch(e){ return ""; } }
  function signedIn(){ return !!(ls(JWT_KEY) || ls(KEY)); }

  var root, fill, dot, tag, timer = null, lastKey = "";

  function build(){
    if(root) return;
    root = document.createElement("div"); root.id = "rw"; root.className = "rw rw-unknown rw-f0";
    root.setAttribute("role", "status"); root.setAttribute("aria-live", "polite"); root.hidden = true;
    var rail = document.createElement("div"); rail.className = "rw-rail";
    fill = document.createElement("i"); fill.className = "rw-fill"; rail.appendChild(fill);
    tag = document.createElement("a"); tag.className = "rw-tag"; tag.href = "/va/manager"; tag.title = "Desk line runway";
    dot = document.createElement("span"); dot.className = "rw-dot"; tag.appendChild(dot);
    var txt = document.createElement("span"); txt.className = "rw-txt"; tag.appendChild(txt);
    root.appendChild(rail); root.appendChild(tag);
    document.body.appendChild(root);
  }

  function dayWord(d){
    if(d == null) return "";
    var n = Math.round(d * 10) / 10;
    if(n < 1) return "under a day of calling left";
    return "about " + (n % 1 === 0 ? n : n.toFixed(1)) + " day" + (n === 1 ? "" : "s") + " of calling left";
  }

  function paint(b){
    build();
    var state, text, sub = "";
    if(!b || b.line === "unknown"){
      state = "unknown"; text = "Desk line"; sub = "runway unknown";
    } else if(b.line === "off"){
      state = "off"; text = "Desk line is off"; sub = "nothing is going out — top up Twilio";
    } else if(b.level === "low"){
      state = "low"; text = "Desk line low"; sub = (dayWord(b.days) || (b.label || "").replace(/^≈ /, "")) + " — top up";
    } else {
      state = "ok"; text = "Desk line"; sub = dayWord(b.days) || (b.label || "").replace(/^≈ /, "");
    }
    var step = state === "off" ? 20 : Math.max(0, Math.min(20, Math.round((b && b.fill != null ? b.fill : 0) * 20)));
    if(state === "ok" && step === 0) step = 1;
    var key = state + ":" + step + ":" + sub;
    if(key === lastKey) return;
    lastKey = key;
    root.className = "rw rw-" + state + " rw-f" + step + " is-live";
    var txt = tag.querySelector(".rw-txt");
    txt.textContent = "";
    var b1 = document.createElement("b"); b1.textContent = text; txt.appendChild(b1);
    if(sub){ txt.appendChild(document.createTextNode(" ")); var s = document.createElement("small"); s.textContent = sub; txt.appendChild(s); }
    tag.title = state === "off"
      ? "Twilio isn't accepting calls or texts from the desk — usually a suspended or empty account. Top up at console.twilio.com."
      : state === "low" ? "The desk line is close to running out. Top up or turn on auto-recharge at console.twilio.com."
      : "Days of calling left on the desk line, from what the desk really spends per day. Texts and minutes share the same pot.";
    root.hidden = false;
  }

  function load(){
    if(!signedIn()){ schedule(RETRY); return; }
    var headers = {"Content-Type": "application/json"}, payload = {};
    if(ls(JWT_KEY)) headers["Authorization"] = "Bearer " + ls(JWT_KEY); else { payload.code = ls(KEY); payload.va_name = ls(VA_KEY); }
    fetch("/api/va/desk/capacity", {method: "POST", headers: headers, body: JSON.stringify(payload), credentials: "same-origin"})
      .then(function(r){ if(r.status === 401){ schedule(RETRY); return null; } return r.json(); })
      .then(function(b){ if(b){ paint(b); schedule(EVERY); } })
      .catch(function(){ schedule(RETRY); });
  }

  function schedule(ms){ if(timer) clearTimeout(timer); timer = setTimeout(load, ms); }

  // The gate hides and #tool appears when the desk signs in — repaint then.
  function watchGate(){
    var tool = document.getElementById("tool");
    if(!tool || !window.MutationObserver) return;
    new MutationObserver(function(){ if(!tool.hidden) load(); }).observe(tool, {attributes: true, attributeFilter: ["hidden", "class", "style"]});
  }

  function start(){ watchGate(); load(); }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
  window.__deskRunwayRefresh = load;
})();
