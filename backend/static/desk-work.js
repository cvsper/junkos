/* Work queue — one list of what needs a human, and who has it.
 *
 * The desk already detected trouble. What it never had was a place where
 * "this needs a person" became "this is mine", which is how a $307 job sat
 * assigned for eighteen days and a hauler finished work and went unpaid.
 *
 * Rules this panel tries to hold to:
 *   - the count is on screen whether or not the panel is open, because a queue
 *     you have to go looking for is a queue nobody reads;
 *   - the worst thing is always at the top, and age pushes items up, so
 *     nothing rots quietly at the bottom;
 *   - claiming shows your name to everyone else, and expires on its own so a
 *     forgotten claim can't hide work forever;
 *   - finishing something asks what you did, because "done" with no word about
 *     what happened is how a thing gets lost twice.
 *
 * CSP-safe: no inline script, styles via CSSOM.
 */
(function(){
  "use strict";
  var JWT_KEY = "umuve_desk_jwt", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";

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
  function age(h){
    if(h == null) return "";
    if(h < 1) return Math.max(1, Math.round(h * 60)) + " min";
    if(h < 48) return Math.round(h) + "h";
    return Math.round(h / 24) + " days";
  }

  var st = document.createElement("style"); document.head.appendChild(st);
  [".wq-tab{position:fixed;left:14px;bottom:14px;z-index:60;font-family:var(--display);font-weight:800;font-size:13px;",
   "  color:var(--ink);background:var(--raise);border:1px solid var(--line);border-radius:999px;padding:11px 16px;",
   "  cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.35);display:flex;align-items:center;gap:8px}",
   ".wq-tab.hot{background:#FF6A2C;color:#fff;border-color:#FF6A2C}",
   ".wq-tab .n{font-size:12px;background:rgba(0,0,0,.28);border-radius:999px;padding:2px 7px}",
   ".wq-wrap{position:fixed;inset:0;z-index:61;background:rgba(5,7,10,.72);display:flex;align-items:flex-end;justify-content:center}",
   ".wq-wrap[hidden]{display:none}",
   ".wq{width:100%;max-width:520px;background:var(--bg,#0F1319);border:1px solid var(--line);",
   "  border-radius:18px 18px 0 0;padding:16px 16px 20px;max-height:92vh;overflow:auto}",
   "@media(min-width:700px){.wq-wrap{align-items:center}.wq{border-radius:18px}}",
   ".wq-h{display:flex;justify-content:space-between;align-items:center;margin:0 0 4px}",
   ".wq-h h3{margin:0;font-family:var(--display);font-weight:800;font-size:17px;color:var(--ink)}",
   ".wq-x{background:transparent;border:0;color:var(--muted);font-size:22px;line-height:1;cursor:pointer;padding:0 4px}",
   ".wq-sub{font-size:12px;color:var(--faint);margin:0 0 12px}",
   ".wq-i{border-top:1px solid var(--line);padding:12px 0}",
   ".wq-i:first-of-type{border-top:0}",
   ".wq-i.mine{background:rgba(61,214,140,.05);margin:0 -8px;padding-left:8px;padding-right:8px;border-radius:10px}",
   ".wq-top{display:flex;justify-content:space-between;gap:10px;align-items:baseline}",
   ".wq-t{font-family:var(--display);font-weight:800;font-size:14.5px;color:var(--ink)}",
   ".wq-age{font-size:11.5px;color:var(--faint);white-space:nowrap}",
   ".wq-age.old{color:#FF7A5C}",
   ".wq-d{font-size:13px;color:var(--muted);margin:3px 0 0}",
   ".wq-why{font-size:12px;color:var(--faint);margin:4px 0 0;line-height:1.45}",
   ".wq-who{font-size:11.5px;color:var(--ok);font-family:var(--display);font-weight:700;margin:5px 0 0}",
   ".wq-who.stale{color:#F5B301}",
   ".wq-act{display:flex;gap:6px;flex-wrap:wrap;margin:9px 0 0}",
   ".wq-b{font-family:var(--display);font-weight:800;font-size:12.5px;border-radius:9px;padding:8px 12px;cursor:pointer;",
   "  background:var(--raise);color:var(--ink);border:1px solid var(--line);white-space:nowrap}",
   ".wq-b.go{background:var(--ok);color:#0B0E12;border-color:var(--ok)}",
   ".wq-b:disabled{opacity:.45;cursor:default}",
   ".wq-note{width:100%;font:inherit;font-size:13px;color:var(--ink);background:var(--raise);border:1px solid var(--line);",
   "  border-radius:9px;padding:8px 10px;margin:8px 0 0}",
   ".wq-empty{padding:22px 4px;text-align:center;font-size:14px;color:var(--muted)}",
   ".wq-empty b{display:block;font-family:var(--display);font-size:16px;color:var(--ok);margin:0 0 4px}",
   ".wq-msg{font-size:12.5px;margin:8px 0 0;min-height:16px}",
   ".wq-msg.err{color:#FF7A5C}.wq-msg.ok{color:var(--ok)}",
   ".wq-warn{font-size:11.5px;color:#F5B301;margin:6px 0 0}"
  ].forEach(function(r){ try { st.sheet.insertRule(r, st.sheet.cssRules.length); } catch(e){} });

  var tab = el("button", "wq-tab"); tab.type = "button";
  tab.appendChild(el("span", null, "Work"));
  var badge = el("span", "n", "0"); tab.appendChild(badge);
  tab.title = "Everything waiting on a person right now";
  document.body.appendChild(tab);

  var wrap = el("div", "wq-wrap"); wrap.hidden = true;
  var panel = el("div", "wq");
  var head = el("div", "wq-h");
  head.appendChild(el("h3", null, "Needs a person"));
  var close = el("button", "wq-x", "×"); close.type = "button"; close.setAttribute("aria-label", "Close");
  head.appendChild(close);
  var sub = el("p", "wq-sub");
  var list = el("div");
  var msg = el("p", "wq-msg");
  [head, sub, list, msg].forEach(function(n){ panel.appendChild(n); });
  wrap.appendChild(panel);
  document.body.appendChild(wrap);

  var queue = null, busy = false;

  function say(t, kind){ msg.textContent = t || ""; msg.className = "wq-msg" + (kind ? " " + kind : ""); }

  function placeTab(){
    var line = document.getElementById("line");
    var h = 0;
    if(line && !line.hidden){
      var r = line.getBoundingClientRect();
      var isBottomBar = r.bottom >= window.innerHeight - 2 && r.height > 0 &&
                        r.height < window.innerHeight * 0.4 && r.width > window.innerWidth * 0.6;
      if(isBottomBar) h = r.height;
    }
    tab.style.bottom = (h + 14) + "px";
  }

  function paint(){
    badge.textContent = queue ? String(queue.total) : "0";
    tab.classList.toggle("hot", !!(queue && queue.unclaimed > 0));
    if(wrap.hidden) return;
    list.textContent = "";
    if(!queue){ sub.textContent = "Loading…"; return; }
    sub.textContent = queue.total === 0
      ? ""
      : queue.total + " waiting · " + queue.unclaimed + " unclaimed" +
        (queue.mine ? " · " + queue.mine + " yours" : "");
    if(queue.sources_failed && queue.sources_failed.length){
      sub.appendChild(el("span", "wq-warn", " · couldn't check: " + queue.sources_failed.join(", ")));
    }
    if(!queue.items.length){
      var e = el("div", "wq-empty");
      e.appendChild(el("b", null, "Nothing waiting."));
      e.appendChild(document.createTextNode("No unpaid haulers, no stuck jobs, no missed calls."));
      list.appendChild(e);
      return;
    }
    queue.items.forEach(function(it){ list.appendChild(row(it)); });
  }

  function row(it){
    var box = el("div", "wq-i" + (it.mine ? " mine" : ""));
    var top = el("div", "wq-top");
    top.appendChild(el("div", "wq-t", it.title));
    var a = el("span", "wq-age" + (it.age_hours > 48 ? " old" : ""), age(it.age_hours));
    top.appendChild(a);
    box.appendChild(top);
    if(it.detail) box.appendChild(el("p", "wq-d", it.detail));
    if(it.why) box.appendChild(el("p", "wq-why", it.why));
    if(it.claimed_by){
      box.appendChild(el("p", "wq-who", it.mine ? "Yours" : it.claimed_by + " has this"));
    } else if(it.claim_stale){
      box.appendChild(el("p", "wq-who stale", "Claim expired — back in the pool"));
    }

    var act = el("div", "wq-act");
    if(it.phone){
      var callBtn = el("button", "wq-b go", "Call " + it.phone); callBtn.type = "button";
      callBtn.addEventListener("click", function(){ dial(it.phone); });
      act.appendChild(callBtn);
    }
    if(!it.claimed_by){
      var take = el("button", "wq-b" + (it.phone ? "" : " go"), "I'll take it"); take.type = "button";
      take.addEventListener("click", function(){ act2("/api/va/work/claim", it, {}, take); });
      act.appendChild(take);
    } else if(it.mine){
      var drop = el("button", "wq-b", "Give it back"); drop.type = "button";
      drop.addEventListener("click", function(){ act2("/api/va/work/release", it, {}, drop); });
      act.appendChild(drop);
    }
    var doneBtn = el("button", "wq-b", "Done"); doneBtn.type = "button";
    var snooze = el("button", "wq-b", "Later"); snooze.type = "button";
    snooze.title = "Hide it for an hour";
    snooze.addEventListener("click", function(){ act2("/api/va/work/snooze", it, {minutes: 60}, snooze); });
    act.appendChild(doneBtn); act.appendChild(snooze);
    box.appendChild(act);

    var note = el("input", "wq-note"); note.type = "text";
    note.placeholder = "What did you do? (needed to close it)";
    note.hidden = true;
    box.appendChild(note);
    doneBtn.addEventListener("click", function(){
      if(note.hidden){ note.hidden = false; note.focus(); doneBtn.textContent = "Close it"; return; }
      if(!note.value.trim()){ say("Say what you did, so the next person knows.", "err"); note.focus(); return; }
      act2("/api/va/work/done", it, {note: note.value.trim()}, doneBtn);
    });
    note.addEventListener("keydown", function(e){ if(e.key === "Enter") doneBtn.click(); });
    return box;
  }

  function dial(pretty){
    var digits = (pretty || "").replace(/\D/g, "");
    if(digits.length === 11 && digits.charAt(0) === "1") digits = digits.slice(1);
    if(digits.length !== 10){ say("That number doesn't look dialable.", "err"); return; }
    if(window.__deskCallsBlocked){ say("The calling window is closed right now.", "err"); return; }
    var dev = window.__deskDevice;
    if(dev && typeof dev.connect === "function"){
      dev.connect({params: {To: "+1" + digits, va_name: vaName()}})
        .then(function(){ shut(); })
        .catch(function(){ say("Couldn't start the call — check the microphone.", "err"); });
      return;
    }
    var a = document.createElement("a"); a.href = "tel:+1" + digits; a.style.display = "none";
    document.body.appendChild(a); a.click(); a.remove();
  }

  function act2(path, it, extra, btn){
    if(busy) return;
    busy = true; if(btn) btn.disabled = true;
    var body = {kind: it.kind, ref_id: it.ref_id};
    Object.keys(extra || {}).forEach(function(k){ body[k] = extra[k]; });
    post(path, body).then(function(r){
      busy = false; if(btn) btn.disabled = false;
      if(r.status !== 200){ say((r.body && r.body.error) || "That didn't work.", "err"); return; }
      say("");
      queue = r.body.queue || queue;
      paint();
    }).catch(function(){
      busy = false; if(btn) btn.disabled = false;
      say("No connection — try again.", "err");
    });
  }

  function load(){
    post("/api/va/work/list", {}).then(function(r){
      if(r.status !== 200){ if(!wrap.hidden) say((r.body && r.body.error) || "Couldn't load.", "err"); return; }
      queue = r.body;
      paint();
    }).catch(function(){});
  }

  function open(){ wrap.hidden = false; paint(); load(); }
  function shut(){ wrap.hidden = true; say(""); }
  tab.addEventListener("click", open);
  close.addEventListener("click", shut);
  wrap.addEventListener("click", function(e){ if(e.target === wrap) shut(); });
  document.addEventListener("keydown", function(e){ if(e.key === "Escape" && !wrap.hidden) shut(); });

  placeTab();
  window.addEventListener("resize", placeTab);
  setInterval(placeTab, 1500);
  setTimeout(load, 1800);
  setInterval(load, 60000);
})();
