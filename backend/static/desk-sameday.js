/* Same-day dispatch on the intake card: capacity line under the zip, and after a
   booking a "Find a hauler now" panel with live replies. Also a standby count in
   the line-panel header. CSP-safe: no inline scripts, styles via CSSOM. */
(function(){
  var JWT_KEY = "umuve_desk_jwt", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";
  function jwt(){ return localStorage.getItem(JWT_KEY) || ""; }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { body.code = localStorage.getItem(KEY) || ""; body.va_name = localStorage.getItem(VA_KEY) || ""; }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }
  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  function css(rules){
    var s = document.createElement("style"); document.head.appendChild(s);
    rules.forEach(function(r){ try { s.sheet.insertRule(r, s.sheet.cssRules.length); } catch(e){} });
  }
  css([
    ".sd-cap{margin:6px 0 10px;padding:9px 12px;border-radius:10px;font-size:12.5px;line-height:1.45;border:1px solid var(--line);background:var(--raise);color:var(--muted)}",
    ".sd-cap.green{border-color:rgba(61,214,140,.5);color:var(--ink)}.sd-cap.amber{border-color:rgba(255,106,44,.5)}.sd-cap.red{border-color:rgba(255,122,92,.55);color:#FF7A5C}",
    ".sd-cap b{font-family:var(--display);font-weight:700}",
    ".sd-wave{margin:10px 0;padding:12px;border-radius:14px;border:1px solid rgba(61,214,140,.45);background:rgba(61,214,140,.06)}",
    ".sd-wave h4{margin:0 0 6px;font-family:var(--display);font-weight:800;font-size:14px;color:var(--ink)}",
    ".sd-btn{font-family:var(--display);font-weight:800;font-size:14px;color:#0B0E12;background:var(--ok);border:0;border-radius:12px;padding:12px 16px;cursor:pointer;width:100%}",
    ".sd-btn:disabled{opacity:.5;cursor:default}.sd-btn.alt{background:var(--raise);color:var(--ink);border:1px solid var(--line)}",
    ".sd-off{display:flex;justify-content:space-between;gap:8px;padding:7px 2px;border-bottom:1px solid var(--line);font-size:13px;color:var(--muted)}",
    ".sd-off b{color:var(--ink);font-family:var(--display)}.sd-off .acc{color:var(--ok);font-weight:700}.sd-off .dec{color:#FF7A5C}",
    ".sd-note{font-size:12px;color:var(--faint);margin:6px 0 0;line-height:1.45}",
    ".sd-standby{font-family:var(--display);font-weight:700;font-size:11px;color:var(--faint);margin-right:8px;white-space:nowrap}"
  ]);

  // ---- 1. capacity under the zip / address
  var capBox = null, capTimer = null, lastCapKey = "";
  function ensureCap(){
    var zip = document.getElementById("in-zip"); if(!zip) return null;
    if(capBox && document.body.contains(capBox)) return capBox;
    capBox = el("div", "sd-cap"); capBox.hidden = true;
    var host = zip.closest(".in-f") || zip.parentNode;
    host.parentNode.insertBefore(capBox, host.nextSibling);
    return capBox;
  }
  function checkCapacity(){
    var zip = document.getElementById("in-zip"), addr = document.getElementById("in-addr");
    if(!zip) return;
    var z = (zip.value || "").replace(/\D/g, "").slice(0, 5);
    var a = addr ? addr.value.trim() : "";
    var key = z.length === 5 ? z : (a.length > 8 ? a : "");
    if(!key || key === lastCapKey) return;
    lastCapKey = key;
    var box = ensureCap(); box.hidden = false; box.className = "sd-cap"; box.textContent = "Checking who can go today…";
    post("/api/va/sameday/capacity", z.length === 5 ? {zip: z} : {address: a}).then(function(r){
      if(r.status !== 200){ box.hidden = true; return; }
      var b = r.body;
      box.className = "sd-cap " + b.level;
      box.textContent = "";
      box.appendChild(el("b", null, b.level === "red" ? "Same day: none nearby. " : "Same day: OK. "));
      box.appendChild(document.createTextNode(b.note + (b.standby_total ? " · " + b.standby_total + " on standby" : "")));
    }).catch(function(){ box.hidden = true; });
  }
  document.addEventListener("input", function(e){
    if(e.target && (e.target.id === "in-zip" || e.target.id === "in-addr")){ clearTimeout(capTimer); capTimer = setTimeout(checkCapacity, 500); }
  }, true);

  // ---- 2. find a hauler now (after a booking)
  var waveBox = null, pollTimer = null, waveJob = null;
  function money(n){ return "$" + Math.round(n); }
  function renderStatus(st){
    if(!waveBox) return;
    var list = waveBox.querySelector(".sd-list"); list.textContent = "";
    (st.offers || []).forEach(function(o){
      var row = el("div", "sd-off");
      row.appendChild(el("b", null, o.name + (o.miles != null ? " · " + o.miles + " mi" : "")));
      var s = el("span", o.status === "accepted" ? "acc" : (o.status === "declined" || o.status === "expired" ? "dec" : ""),
        o.status === "accepted" ? "ACCEPTED" + (o.eta_minutes ? " · ~" + o.eta_minutes + " min out" : "") :
        o.status === "sent" ? "waiting…" : o.status);
      row.appendChild(s); list.appendChild(row);
    });
    var head = waveBox.querySelector("h4");
    if(st.accepted){
      head.textContent = st.accepted.name + " has it" + (st.accepted.eta_minutes ? " — about " + st.accepted.eta_minutes + " minutes out" : "") + ". Tell the customer.";
      clearInterval(pollTimer); pollTimer = null;
      waveBox.querySelector(".sd-btn.go").hidden = true; waveBox.querySelector(".sd-btn.alt").hidden = true;
    } else if((st.offers || []).length){
      head.textContent = "Offers out to " + st.offers.length + " hauler" + (st.offers.length === 1 ? "" : "s") + " — replies show here";
    }
  }
  function poll(){
    if(!waveJob) return;
    post("/api/va/sameday/status", {job_id: waveJob}).then(function(r){ if(r.status === 200) renderStatus(r.body); }).catch(function(){});
  }
  function showWave(job){
    var host = document.getElementById("intake"); if(!host) return;
    waveJob = job.id;
    if(waveBox && document.body.contains(waveBox)) waveBox.remove();
    waveBox = el("div", "sd-wave");
    waveBox.appendChild(el("h4", null, "Same-day: find a hauler now"));
    var go = el("button", "sd-btn go", "Text the 3 nearest haulers this job"); go.type = "button";
    var more = el("button", "sd-btn alt", "Widen to 3 more"); more.type = "button"; more.hidden = true; more.style.marginTop = "6px";
    var list = el("div", "sd-list");
    var note = el("p", "sd-note", "Each gets the price, area and window with a one-tap accept link. First to accept is assigned automatically and the customer gets a text. No reply in about 90 seconds: book tomorrow's first window and leave the offers running.");
    waveBox.appendChild(go); waveBox.appendChild(more); waveBox.appendChild(list); waveBox.appendChild(note);
    var status = document.getElementById("in-status");
    (status && status.parentNode ? status.parentNode : host).insertBefore(waveBox, status || null);
    function fire(btn){
      btn.disabled = true;
      post("/api/va/sameday/find", {job_id: waveJob, limit: 3}).then(function(r){
        btn.disabled = false;
        if(r.status !== 200){ waveBox.querySelector("h4").textContent = (r.body && r.body.error) || "Couldn't send offers."; return; }
        if(!r.body.sent.length){ waveBox.querySelector("h4").textContent = "Nobody eligible right now (" + (r.body.reason || "") + ") — book tomorrow's first window."; return; }
        go.hidden = true; more.hidden = false;
        renderStatus(r.body.status);
        clearInterval(pollTimer); pollTimer = setInterval(poll, 3000);
      }).catch(function(){ btn.disabled = false; });
    }
    go.addEventListener("click", function(){ fire(go); });
    more.addEventListener("click", function(){ fire(more); });
  }
  // the intake script exposes the last booking; watch for it
  var lastSeen = null;
  setInterval(function(){
    var j = window.__lastBookedJob;
    if(j && j.id && j.id !== lastSeen){ lastSeen = j.id; showWave(j); }
  }, 800);

  // ---- 3. standby count in the line-panel header
  function standbyChip(){
    var head = document.querySelector("#line .ln-head"); if(!head) return;
    var chip = document.getElementById("sd-standby");
    if(!chip){ chip = el("span", "sd-standby"); chip.id = "sd-standby"; chip.title = "Haulers who said they can take same-day jobs today"; head.insertBefore(chip, head.firstChild.nextSibling); }
    post("/api/va/sameday/standby", {}).then(function(r){
      if(r.status !== 200) return;
      chip.textContent = "Standby today: " + r.body.available + (r.body.online_now ? " · online: " + r.body.online_now : "");
    }).catch(function(){});
  }
  setTimeout(standbyChip, 2500); setInterval(standbyChip, 120000);
})();
