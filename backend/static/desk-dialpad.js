/* Dialpad — reach the decision maker.
 *
 * Tracy's request (Slack, 11 Sep): "Could you please include a tab where I
 * could dial numbers? So I'll be able to reach the decision makers."
 *
 * The queue dials the number on the card. It could not dial anything else, so
 * the moment a gatekeeper said "he's on extension 214" or read out a direct
 * cell, the desk was useless and the number went onto paper.
 *
 * Three things, in the order they happen on a real call:
 *   1. Keypad WHILE connected — sends DTMF through the live call, so a phone
 *      tree or an extension is dialled without hanging up. This is the one
 *      that actually gets you past a switchboard.
 *   2. Dial any number — type or paste, call it from the browser like any
 *      card. Recent numbers are kept for redial.
 *   3. Save who you reached — writes the name and direct line onto the open
 *      card, so next time the decision maker is one tap from the queue
 *      instead of being rediscovered.
 *
 * CSP-safe: no inline script, styles injected via CSSOM.
 */
(function(){
  "use strict";
  var JWT_KEY = "umuve_desk_jwt", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";
  var RECENT_KEY = "umuve_dialpad_recent";

  function jwt(){ try { return localStorage.getItem(JWT_KEY) || ""; } catch(e){ return ""; } }
  function vaName(){ try { return localStorage.getItem(VA_KEY) || ""; } catch(e){ return ""; } }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { try { body.code = localStorage.getItem(KEY) || ""; body.va_name = vaName(); } catch(e){} }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }
  function el(tag, cls, text){
    var e = document.createElement(tag);
    if(cls) e.className = cls;
    if(text != null) e.textContent = text;
    return e;
  }

    (function(){ if(document.querySelector('link[href^="/static/desk-dialpad.css"]')) return; var l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/static/desk-dialpad.css?v=2"; document.head.appendChild(l); })();

  // ---- state
  var raw = "";                 // digits typed for a new call
  var live = false;             // a call is connected right now
  var sentDigits = "";          // DTMF sent during this call

  function digitsOf(s){ return (s || "").replace(/\D/g, ""); }
  function pretty(d){
    d = digitsOf(d);
    if(d.length === 11 && d.charAt(0) === "1") d = d.slice(1);
    if(d.length <= 3) return d;
    if(d.length <= 6) return "(" + d.slice(0, 3) + ") " + d.slice(3);
    return "(" + d.slice(0, 3) + ") " + d.slice(3, 6) + "-" + d.slice(6, 10) + (d.length > 10 ? " x" + d.slice(10) : "");
  }
  function recent(){
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch(e){ return []; }
  }
  function remember(d){
    try {
      var list = recent().filter(function(x){ return x.d !== d; });
      list.unshift({d: d, at: Date.now()});
      localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 6)));
    } catch(e){}
  }

  // ---- build the panel
  var PHONE_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25c1.1.37 2.3.57 3.6.57a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1L6.6 10.8z"/></svg>';
  var tab = el("button", "dp-tab"); tab.type = "button";
  tab.innerHTML = PHONE_SVG;
  var tabLabel = el("span", null, "Dial"); tab.appendChild(tabLabel);
  tab.title = "Dial any number, or send an extension while you're connected";
  document.body.appendChild(tab);

  // The line panel is pinned to the bottom and holds real buttons (Replies,
  // the collapse chevron). A fixed tab at bottom:14px sat on top of them, so
  // ride above whatever height that panel currently is.
  function placeTab(){
    var line = document.getElementById("line");
    var h = 0;
    if(line && !line.hidden){
      var r = line.getBoundingClientRect();
      // only a genuine bottom BAR displaces the tab — on wide screens the same
      // element is a full-height side column, and offsetting by that pushed
      // the tab off the top of the window.
      var isBottomBar = r.bottom >= window.innerHeight - 2 &&
                        r.height > 0 && r.height < window.innerHeight * 0.65 &&
                        r.width > window.innerWidth * 0.6;
      if(isBottomBar) h = r.height;
      else if(r.width && r.left > window.innerWidth * 0.4 && r.right >= window.innerWidth - 80){
        // side column on wide screens: sit beside it, not on top of the thread
        tab.style.right = Math.round(window.innerWidth - r.left + 14) + "px";
        tab.style.bottom = "14px";
        return;
      }
    }
    tab.style.right = "14px";
    tab.style.bottom = (h + 14) + "px";
  }
  placeTab();
  window.addEventListener("resize", placeTab);
  setInterval(placeTab, 1500);

  var wrap = el("div", "dp-wrap"); wrap.hidden = true;
  var panel = el("div", "dp");
  var head = el("div", "dp-h");
  var title = el("h3", null, "Dialpad");
  var close = el("button", "dp-x", "×"); close.type = "button"; close.setAttribute("aria-label", "Close");
  head.appendChild(title); head.appendChild(close);
  var mode = el("p", "dp-mode");
  var display = el("div", "dp-num", ""); display.setAttribute("data-placeholder", "Enter a number");
  var hint = el("p", "dp-hint", "");
  var grid = el("div", "dp-grid");
  var letters = {"2": "ABC", "3": "DEF", "4": "GHI", "5": "JKL", "6": "MNO", "7": "PQRS", "8": "TUV", "9": "WXYZ"};
  ["1","2","3","4","5","6","7","8","9","*","0","#"].forEach(function(k){
    var b = el("button", "dp-k"); b.type = "button";
    b.appendChild(document.createTextNode(k));
    if(letters[k]) b.appendChild(el("small", null, letters[k]));
    b.addEventListener("click", function(){ press(k); });
    grid.appendChild(b);
  });
  var row = el("div", "dp-row");
  var callBtn = el("button", "dp-btn dp-call"); callBtn.type = "button"; callBtn.setAttribute("aria-label", "Call");
  callBtn.innerHTML = PHONE_SVG;
  var backBtn = el("button", "dp-del", "\u232B"); backBtn.type = "button"; backBtn.setAttribute("aria-label", "Delete");
  backBtn.title = "Delete";
  row.appendChild(callBtn); row.appendChild(backBtn);
  var msg = el("p", "dp-msg");
  var note = el("p", "dp-note");

  // save-the-decision-maker block
  var save = el("div", "dp-save"); save.hidden = true;
  save.appendChild(el("h4", null, "Save this decision maker to the card"));
  var nameIn = el("input"); nameIn.type = "text"; nameIn.placeholder = "Name (who to ask for)";
  var phoneIn = el("input"); phoneIn.type = "tel"; phoneIn.placeholder = "Direct line";
  var saveBtn = el("button", "dp-btn", "Save to card"); saveBtn.type = "button";
  save.appendChild(nameIn); save.appendChild(phoneIn); save.appendChild(saveBtn);

  var recentBox = el("div", "dp-recent"); recentBox.hidden = true;
  recentBox.appendChild(el("h4", null, "Recent"));
  var recentList = el("div");
  recentBox.appendChild(recentList);

  [head, mode, display, hint, grid, row, msg, note, save, recentBox].forEach(function(n){ panel.appendChild(n); });
  wrap.appendChild(panel);
  document.body.appendChild(wrap);

  function say(text, kind){ msg.textContent = text || ""; msg.className = "dp-msg" + (kind ? " " + kind : ""); }

  function press(k){
    if(live){
      var call = window.__deskActiveCall;
      if(!call || typeof call.sendDigits !== "function"){ say("Can't send tones on this call.", "err"); return; }
      try {
        call.sendDigits(k);
        sentDigits += k;
        display.textContent = sentDigits;
        hint.textContent = "sent to the call";
        say("");
      } catch(e){ say("Couldn't send that tone.", "err"); }
      return;
    }
    if(digitsOf(raw).length >= 15) return;
    raw += k;
    render();
  }

  function render(){
    if(live){
      title.textContent = "On a call";
      mode.textContent = "";
      mode.appendChild(el("b", null, "Connected. "));
      mode.appendChild(document.createTextNode(
        "Tap through the menu — \u201cpress 2 for sales\u201d, an extension, whatever it asks for. " +
        "Every key goes down the line. No need to hang up."));
      display.textContent = sentDigits || "";
      display.className = "dp-num tones"; display.setAttribute("data-placeholder", "Tap the menu");
      hint.textContent = sentDigits ? "sent to the call" : "each key goes down the line";
      callBtn.textContent = "Done"; callBtn.setAttribute("aria-label", "Done");
      callBtn.className = "dp-btn dp-call alt";
      callBtn.disabled = false;
      backBtn.hidden = true;
      note.textContent = "";
      recentBox.hidden = true;
      save.hidden = !currentProspectId();
      return;
    }
    title.textContent = "Dialpad";
    mode.textContent = "Dial any number. Once you're connected, these keys work the menu — " +
      "press 2 for sales, an extension, anything the system asks for.";
    display.textContent = pretty(raw) || "";
    display.className = "dp-num"; display.setAttribute("data-placeholder", "Enter a number");
    hint.textContent = raw ? "" : "type, paste, or tap the keys";
    callBtn.innerHTML = PHONE_SVG; callBtn.setAttribute("aria-label", "Call");
    callBtn.className = "dp-btn dp-call";
    callBtn.disabled = digitsOf(raw).length < 10;
    backBtn.hidden = false;
    note.textContent = "Calls go out on the desk line, so they show in your history like any other call.";
    var list = recent();
    recentBox.hidden = !list.length;
    recentList.textContent = "";
    list.forEach(function(item){
      var r = el("div", "dp-r");
      r.appendChild(document.createTextNode(pretty(item.d)));
      r.appendChild(el("span", null, "redial"));
      r.addEventListener("click", function(){ raw = item.d; render(); });
      recentList.appendChild(r);
    });
    save.hidden = true;
  }

  function currentProspectId(){
    // calls.js keeps the dealt card's id on the call button's dataset when present
    var node = document.getElementById("c-company");
    return (node && node.getAttribute("data-prospect-id")) || window.__deskProspectId || null;
  }

  function open(){
    wrap.hidden = false;
    if(live && !nameIn.value) phoneIn.value = phoneIn.value || "";
    render();
  }
  function shut(){ wrap.hidden = true; say(""); }

  tab.addEventListener("click", open);

  // The call strip is what she's looking at while a call is connected, and an
  // IVR ("press 2 for sales") gives you a couple of seconds. Opening the
  // keypad from there beats hunting for a corner tab.
  var stripKey = document.getElementById("cs-keypad");
  if(stripKey) stripKey.addEventListener("click", function(e){ e.preventDefault(); open(); });
  close.addEventListener("click", shut);
  wrap.addEventListener("click", function(e){ if(e.target === wrap) shut(); });
  backBtn.addEventListener("click", function(){
    if(live) return;
    raw = raw.slice(0, -1); render();
  });

  // typing and pasting straight into the panel
  document.addEventListener("keydown", function(e){
    if(wrap.hidden) return;
    if(e.key === "Escape"){ shut(); return; }
    if(/^[0-9*#]$/.test(e.key)){ press(e.key); e.preventDefault(); return; }
    if(e.key === "Backspace" && !live){ raw = raw.slice(0, -1); render(); e.preventDefault(); }
    if(e.key === "Enter" && !live && !callBtn.disabled){ callBtn.click(); }
  });
  wrap.addEventListener("paste", function(e){
    if(live) return;
    var text = (e.clipboardData || window.clipboardData).getData("text") || "";
    var d = digitsOf(text);
    if(d){ raw = d; render(); e.preventDefault(); }
  });

  callBtn.addEventListener("click", function(){
    if(live){ shut(); return; }
    var d = digitsOf(raw);
    if(d.length === 11 && d.charAt(0) === "1") d = d.slice(1);
    if(d.length < 10){ say("That number is too short.", "err"); return; }
    if(window.__deskCallsBlocked){ say("The calling window is closed right now.", "err"); return; }
    var dev = window.__deskDevice;
    if(!dev || typeof dev.connect !== "function"){
      say("The browser dialer isn't ready — reload the desk, then try again.", "err");
      return;
    }
    say("Calling " + pretty(d) + "…");
    callBtn.disabled = true;
    dev.connect({params: {To: "+1" + d, va_name: vaName()}}).then(function(){
      remember(d);
      phoneIn.value = pretty(d);
      say("");
      shut();
    }).catch(function(){
      callBtn.disabled = false;
      say("Couldn't start the call. Check the microphone permission and try again.", "err");
    });
  });

  saveBtn.addEventListener("click", function(){
    var pid = currentProspectId();
    if(!pid){ say("Open a card first, then save the contact to it.", "err"); return; }
    var body = {prospect_id: pid};
    if(nameIn.value.trim()) body.contact_name = nameIn.value.trim();
    if(phoneIn.value.trim()) body.direct_phone = phoneIn.value.trim();
    if(!body.contact_name && !body.direct_phone){ say("Add a name or a direct line first.", "err"); return; }
    saveBtn.disabled = true;
    post("/api/va/calls/contact", body).then(function(r){
      saveBtn.disabled = false;
      if(r.status !== 200){ say((r.body && r.body.error) || "Couldn't save that.", "err"); return; }
      say("Saved to the card — it'll be there next time.", "ok");
      nameIn.value = "";
    }).catch(function(){ saveBtn.disabled = false; say("No connection — couldn't save.", "err"); });
  });

  // follow the desk's call state
  window.addEventListener("desk:call", function(e){
    var wasLive = live;
    live = !!(e.detail && e.detail.live);
    if(live && !wasLive){ sentDigits = ""; tab.classList.add("live"); tabLabel.textContent = "Keypad"; }
    if(!live && wasLive){ tab.classList.remove("live"); tabLabel.textContent = "Dial"; }
    if(!wrap.hidden) render();
  });

  render();
})();
