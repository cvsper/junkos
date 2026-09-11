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

  var st = document.createElement("style"); document.head.appendChild(st);
  [".dp-tab{position:fixed;right:14px;bottom:14px;z-index:60;font-family:var(--display);font-weight:800;font-size:13px;",
   "  color:#0B0E12;background:var(--ok);border:0;border-radius:999px;padding:12px 18px;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.35)}",
   ".dp-tab.live{background:#FF6A2C;color:#fff}",
   ".dp-wrap{position:fixed;inset:0;z-index:61;background:rgba(5,7,10,.72);display:flex;align-items:flex-end;justify-content:center}",
   ".dp-wrap[hidden]{display:none}",
   ".dp{width:100%;max-width:380px;background:var(--bg,#0F1319);border:1px solid var(--line);border-radius:18px 18px 0 0;",
   "  padding:16px 16px 20px;max-height:92vh;overflow:auto}",
   "@media(min-width:700px){.dp-wrap{align-items:center}.dp{border-radius:18px}}",
   ".dp-h{display:flex;justify-content:space-between;align-items:center;margin:0 0 10px}",
   ".dp-h h3{margin:0;font-family:var(--display);font-weight:800;font-size:16px;color:var(--ink)}",
   ".dp-x{background:transparent;border:0;color:var(--muted);font-size:22px;line-height:1;cursor:pointer;padding:0 4px}",
   ".dp-mode{font-size:12px;color:var(--faint);margin:0 0 10px;line-height:1.45}",
   ".dp-mode b{color:#FF6A2C;font-family:var(--display)}",
   ".dp-num{width:100%;font-family:var(--display);font-weight:800;font-size:26px;letter-spacing:.5px;text-align:center;",
   "  color:var(--ink);background:var(--raise);border:1px solid var(--line);border-radius:12px;padding:12px 10px;margin:0 0 4px}",
   ".dp-hint{font-size:11.5px;color:var(--faint);text-align:center;min-height:15px;margin:0 0 10px}",
   ".dp-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:0 0 12px}",
   ".dp-k{background:var(--raise);border:1px solid var(--line);border-radius:12px;padding:13px 0;cursor:pointer;color:var(--ink);",
   "  font-family:var(--display);font-weight:800;font-size:20px;line-height:1}",
   ".dp-k:active{background:var(--ok);color:#0B0E12}",
   ".dp-k small{display:block;font-size:9px;letter-spacing:1.5px;color:var(--faint);font-weight:600;margin-top:3px}",
   ".dp-k:active small{color:#0B0E12}",
   ".dp-row{display:flex;gap:8px}",
   ".dp-btn{flex:1;font-family:var(--display);font-weight:800;font-size:14px;color:#0B0E12;background:var(--ok);border:0;",
   "  border-radius:12px;padding:13px 10px;cursor:pointer}",
   ".dp-btn:disabled{opacity:.45;cursor:default}",
   ".dp-btn.alt{background:var(--raise);color:var(--ink);border:1px solid var(--line)}",
   ".dp-btn.end{background:#FF5A4E;color:#fff}",
   ".dp-note{font-size:12px;color:var(--muted);margin:12px 0 0;line-height:1.5}",
   ".dp-save{margin:12px 0 0;padding:12px;border:1px solid rgba(61,214,140,.45);background:rgba(61,214,140,.06);border-radius:12px}",
   ".dp-save h4{margin:0 0 8px;font-family:var(--display);font-weight:800;font-size:13px;color:var(--ink)}",
   ".dp-save input{width:100%;font:inherit;font-size:14px;color:var(--ink);background:var(--raise);border:1px solid var(--line);",
   "  border-radius:10px;padding:9px 10px;margin:0 0 8px}",
   ".dp-save .dp-btn{width:100%;flex:none}",
   ".dp-recent{margin:12px 0 0;border-top:1px solid var(--line);padding-top:10px}",
   ".dp-recent h4{margin:0 0 6px;font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:1px;color:var(--faint);text-transform:uppercase}",
   ".dp-r{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--line);font-size:13.5px;color:var(--ink);cursor:pointer}",
   ".dp-r span{color:var(--faint);font-size:12px}",
   ".dp-msg{font-size:12.5px;margin:8px 0 0;min-height:16px}",
   ".dp-msg.err{color:#FF7A5C}.dp-msg.ok{color:var(--ok)}"
  ].forEach(function(r){ try { st.sheet.insertRule(r, st.sheet.cssRules.length); } catch(e){} });

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
  var tab = el("button", "dp-tab", "Dialpad"); tab.type = "button";
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
                        r.height > 0 && r.height < window.innerHeight * 0.4 &&
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
  var display = el("div", "dp-num", "");
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
  var callBtn = el("button", "dp-btn", "Call"); callBtn.type = "button";
  var backBtn = el("button", "dp-btn alt", "Delete"); backBtn.type = "button";
  row.appendChild(backBtn); row.appendChild(callBtn);
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
      hint.textContent = sentDigits ? "sent to the call" : "each key goes down the line";
      callBtn.textContent = "Done";
      callBtn.className = "dp-btn alt";
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
    hint.textContent = raw ? "" : "type or paste a number";
    callBtn.textContent = "Call";
    callBtn.className = "dp-btn";
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
    if(live && !wasLive){ sentDigits = ""; tab.classList.add("live"); tab.textContent = "Keypad"; }
    if(!live && wasLive){ tab.classList.remove("live"); tab.textContent = "Dialpad"; }
    if(!wrap.hidden) render();
  });

  render();
})();
