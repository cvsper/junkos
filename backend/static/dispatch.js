/* Dispatch desk. Renders /api/va/dispatch/overview into the strip, the map,
   the roster, the board and the activity feed; opens a drawer for any job or
   hauler; books new jobs. Every route is POST JSON under /api/va/dispatch/.
   Styles: /static/dispatch.css. No server string is ever inserted as HTML. */
(function(){
  "use strict";
  var JWT_KEY = "umuve_desk_jwt", ME_KEY = "umuve_desk_me", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";
  var API = "/api/va/dispatch/";
  var REFRESH_MS = 60000, CONFIRM_MS = 4000;

  function ls(k){ try { return localStorage.getItem(k) || ""; } catch(e){ return ""; } }
  function me(){ try { return JSON.parse(ls(ME_KEY) || "null"); } catch(e){ return null; } }
  function vaName(){ var m = me(); return (m && m.name) || ls(VA_KEY) || ""; }
  function firstName(){ return (vaName().trim().split(/\s+/)[0] || ""); }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(ls(JWT_KEY)) headers["Authorization"] = "Bearer " + ls(JWT_KEY);
    else { body.code = ls(KEY); body.va_name = vaName(); }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().catch(function(){ return {}; }).then(function(j){ return {status: r.status, body: j || {}}; }); });
  }
  // api(name, body) resolves the JSON body on 2xx; rejects {status, body, message} otherwise. 401 shows the gate.
  function api(name, body){
    return post(API + name, body).then(function(r){
      if(r.status === 401){ showGate(ls(KEY) ? "That code didn't work." : ""); throw {status: 401, body: r.body, message: "Signed out"}; }
      if(r.status < 200 || r.status >= 300 || (r.body && r.body.ok === false && r.body.error)){
        var msg = (r.body && r.body.error) || ("The desk said no (" + r.status + ")");
        throw {status: r.status, body: r.body, message: msg};
      }
      return r.body;
    }, function(){ throw {status: 0, body: {}, message: "Couldn't reach the desk."}; });
  }
  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  function btn(cls, text, fn){ var b = el("button", cls, text); b.type = "button"; if(fn) b.addEventListener("click", fn); return b; }
  function svgEl(tag){ return document.createElementNS("http://www.w3.org/2000/svg", tag); }
  function clear(n){ while(n.firstChild) n.removeChild(n.firstChild); }
  function $(id){ return document.getElementById(id); }
  function num(v){ return v == null || isNaN(v) ? null : Number(v); }
  function money(v){ v = num(v); if(v == null) return "–"; var s = Math.abs(v) % 1 ? v.toFixed(2) : String(Math.round(v)); return (v < 0 ? "−$" : "$") + s.replace("-", ""); }
  function digits(s){ return String(s || "").replace(/\D/g, ""); }
  function fmtPhone(p){ var d = digits(p); if(d.length === 11 && d.charAt(0) === "1") d = d.slice(1); if(d.length === 10) return "(" + d.slice(0, 3) + ") " + d.slice(3, 6) + "-" + d.slice(6); return p || ""; }
  function telHref(p){ var d = digits(p); if(d.length === 10) d = "1" + d; return "+" + d; }
  function parseIso(iso){ if(!iso) return null; var d = new Date(iso.indexOf("Z") > 0 || /[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z"); return isNaN(d) ? null : d; }
  function when(iso){
    var d = parseIso(iso); if(!d) return "";
    var now = new Date();
    if(d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
    return d.toLocaleDateString([], {month: "short", day: "numeric"}) + " " + d.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
  }
  function ago(mins){
    mins = num(mins); if(mins == null) return "";
    if(mins < 1) return "just now"; if(mins < 60) return Math.round(mins) + "m ago";
    if(mins < 48 * 60) return Math.round(mins / 60) + "h ago"; return Math.round(mins / 1440) + "d ago";
  }
  function hoursHint(h){
    h = num(h); if(h == null) return null;
    var a = Math.abs(h), s = a < 1 ? Math.max(1, Math.round(a * 60)) + "m" : a < 48 ? Math.round(a) + "h" : Math.round(a / 24) + "d";
    if(h >= 0) return {text: "in " + s, cls: a < 2 ? "soon" : ""};
    return {text: s + " late", cls: "late"};
  }
  function todayIso(){ var d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function debounce(fn, ms){ var t; return function(){ var a = arguments, s = this; clearTimeout(t); t = setTimeout(function(){ fn.apply(s, a); }, ms); }; }
  function copyText(s){ try { return navigator.clipboard.writeText(s); } catch(e){ return Promise.reject(e); } }

  // ---------------------------------------------------------------- toast
  var toastTimer = null;
  function toast(msg, kind){
    var t = $("dp-toast"); t.textContent = msg || ""; t.className = "dk-toast" + (kind ? " " + kind : ""); t.hidden = false;
    requestAnimationFrame(function(){ t.classList.add("in"); });
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function(){ t.classList.remove("in"); setTimeout(function(){ t.hidden = true; }, 220); }, kind === "bad" ? 5000 : 3200);
  }
  function fail(e){ toast((e && e.message) || "Something went wrong.", "bad"); }

  // Two-tap confirm: the first tap arms the pill for 4s, the second runs it.
  function armed(b, armedLabel, fn){
    var label = b.textContent, t = null;
    b.addEventListener("click", function(ev){
      ev.stopPropagation();
      if(b.classList.contains("confirm")){ clearTimeout(t); b.classList.remove("confirm"); b.textContent = label; b.disabled = true; fn(b); return; }
      b.classList.add("confirm"); b.textContent = armedLabel || "Tap again to confirm";
      t = setTimeout(function(){ b.classList.remove("confirm"); b.textContent = label; }, CONFIRM_MS);
    });
    return b;
  }

  var gate = $("gate"), tool = $("tool");
  var DATA = null, CATALOG = null, BOARD_TAB = "open", ROSTER_FILTER = "live", SEL_HAULER = null, refreshTimer = null, loadedOnce = false;

  // ---------------------------------------------------------------- gate
  function showGate(msg){ tool.hidden = true; gate.hidden = false; var e = $("gate-err"); if(msg){ e.textContent = msg; e.hidden = false; } else { e.hidden = true; } }
  function showTool(){ gate.hidden = true; tool.hidden = false; }
  $("gate-form").addEventListener("submit", function(ev){
    ev.preventDefault();
    var name = $("va-name").value.trim(), code = $("code").value.trim();
    if(!name || !code){ showGate("Your first name and the access code, please."); return; }
    try { localStorage.setItem(KEY, code); localStorage.setItem(VA_KEY, name); } catch(e){}
    load();
  });

  // ---------------------------------------------------------------- load + refresh
  function load(){
    return api("overview", {}).then(function(d){
      DATA = d || {}; DATA.counts = DATA.counts || {}; DATA.jobs = DATA.jobs || {}; DATA.haulers = DATA.haulers || [];
      if(!loadedOnce){ showTool(); loadedOnce = true; }
      $("bar-sub").textContent = (DATA.va || vaName() || "") + " · updated " + new Date().toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
      renderStrip(); renderMap(); renderRoster(); renderBoard(); renderRecent(); refreshHaulerSelect();
      schedule();
    }).catch(function(e){ if(e && e.status === 401){ clearTimeout(refreshTimer); return; } if(!loadedOnce) showGate(e.message); else fail(e); schedule(); });
  }
  function schedule(){ clearTimeout(refreshTimer); refreshTimer = setTimeout(function(){ if(!document.hidden) load(); else schedule(); }, REFRESH_MS); }
  document.addEventListener("visibilitychange", function(){ if(!document.hidden && loadedOnce) load(); });

  // ---------------------------------------------------------------- helpers over the data
  function allJobs(){
    var out = [], J = DATA.jobs || {};
    ["open", "scheduled", "active", "done", "cancelled"].forEach(function(g){ (J[g] || []).forEach(function(j){ out.push({job: j, group: g}); }); });
    return out;
  }
  function findJob(id){ var hit = null; allJobs().forEach(function(x){ if(String(x.job.id) === String(id)) hit = x; }); return hit; }
  function groupOf(status){
    if(status === "cancelled") return "cancelled"; if(status === "completed") return "done";
    if(status === "en_route" || status === "arrived" || status === "started") return "active";
    if(status === "assigned" || status === "accepted" || status === "confirmed") return "scheduled";
    return "open";
  }
  function haulerState(h){ if(!h) return "offline"; if(h.live) return "live"; if(h.online) return "online"; if(h.standby) return "standby"; return "offline"; }
  function stateText(h){
    var s = haulerState(h), seen = h.seen_minutes != null ? ago(h.seen_minutes) : "";
    if(s === "live") return "Live" + (seen ? " · seen " + seen : "");
    if(s === "online") return "Online, unconfirmed" + (seen ? " · seen " + seen : "");
    if(s === "standby") return "Standby";
    return "Offline" + (seen ? " · seen " + seen : "");
  }
  function payInfo(p){
    p = p || {};
    if(p.status === "succeeded") return {text: "Paid", cls: "ok"};
    if(p.status === "refunded") return {text: "Refunded", cls: "warn"};
    if(p.status === "partially_refunded") return {text: "Partly refunded", cls: "warn"};
    if(p.status === "disputed") return {text: "Disputed", cls: "danger"};
    if(p.link_sent) return {text: "Pay link sent", cls: "info"};
    if(p.status === "none") return {text: "No payment on file", cls: ""};
    return {text: "Unpaid", cls: "warn"};
  }

  // ---------------------------------------------------------------- strip
  function renderStrip(){
    var c = DATA.counts || {}, cap = DATA.capacity;
    function put(id, v){ var b = $(id).querySelector("b"); b.textContent = v == null ? "–" : String(v); b.classList.toggle("dim", v == null); }
    put("dp-k-open", c.open); put("dp-k-scheduled", c.scheduled); put("dp-k-active", c.active); put("dp-k-done", c.done_today); put("dp-k-live", c.live);
    $("dp-k-live-sub").textContent = (c.online != null ? c.online + " online" : "") + (c.standby != null ? (c.online != null ? ", " : "") + c.standby + " on standby" : "");
    var pill = $("dp-cap-pill"), lvl = cap && String(cap.level || "").toLowerCase();
    pill.className = "dp-cap" + (lvl === "green" || lvl === "ok" || lvl === "good" ? " green" : lvl === "amber" || lvl === "yellow" || lvl === "tight" ? " amber" : lvl === "red" || lvl === "bad" || lvl === "none" ? " red" : "");
    pill.textContent = cap ? (cap.count != null ? cap.count + " " + (cap.count === 1 ? "truck" : "trucks") : (cap.level || "–")) : "–";
    $("dp-cap-note").textContent = cap ? (cap.note || (cap.unconfirmed ? cap.unconfirmed + " unconfirmed" : "")) : "no capacity read yet";
  }

  // ---------------------------------------------------------------- map
  function renderMap(){
    var svg = $("dp-map"); clear(svg);
    var W = 460, H = 560, pad = 26, area = DATA.area || {}, poly = (area.polygon || []).filter(function(p){ return p && num(p[0]) != null && num(p[1]) != null; });
    var haulers = DATA.haulers.filter(function(h){ return haulerState(h) !== "offline" && num(h.lat) != null && num(h.lng) != null; });
    var jobs = allJobs().filter(function(x){ return (x.group === "open" || x.group === "scheduled" || x.group === "active") && num(x.job.lat) != null && num(x.job.lng) != null; });
    var pts = poly.slice();
    haulers.forEach(function(h){ pts.push([h.lat, h.lng]); }); jobs.forEach(function(x){ pts.push([x.job.lat, x.job.lng]); });
    if(!pts.length){ var t0 = svgEl("text"); t0.setAttribute("x", 20); t0.setAttribute("y", 40); t0.setAttribute("class", "dp-mtext"); t0.textContent = "No area or positions to draw yet."; svg.appendChild(t0); $("dp-map-note").textContent = ""; return; }
    var b = area.bounds && num(area.bounds.north) != null ? {n: +area.bounds.north, s: +area.bounds.south, e: +area.bounds.east, w: +area.bounds.west} : {n: -90, s: 90, e: -180, w: 180};
    pts.forEach(function(p){ b.n = Math.max(b.n, +p[0]); b.s = Math.min(b.s, +p[0]); b.e = Math.max(b.e, +p[1]); b.w = Math.min(b.w, +p[1]); });
    if(b.n === b.s){ b.n += .05; b.s -= .05; } if(b.e === b.w){ b.e += .05; b.w -= .05; }
    var k = Math.cos((b.n + b.s) / 2 * Math.PI / 180) || 1;
    var s = Math.min((W - 2 * pad) / ((b.e - b.w) * k), (H - 2 * pad) / (b.n - b.s));
    var ox = (W - (b.e - b.w) * k * s) / 2, oy = (H - (b.n - b.s) * s) / 2;
    function X(lng){ return ox + (lng - b.w) * k * s; } function Y(lat){ return oy + (b.n - lat) * s; }
    if(poly.length > 2){
      var pg = svgEl("polygon"); pg.setAttribute("class", "dp-area");
      pg.setAttribute("points", poly.map(function(p){ return X(+p[1]).toFixed(1) + "," + Y(+p[0]).toFixed(1); }).join(" "));
      var tt = svgEl("title"); tt.textContent = "Service area" + ((area.counties || []).length ? ": " + area.counties.join(", ") : ""); pg.appendChild(tt); svg.appendChild(pg);
    }
    jobs.forEach(function(x){
      var j = x.job, p = svgEl("path"); p.setAttribute("class", "dp-mj " + x.group);
      p.setAttribute("d", "M0 0 L-6 -9 A7 7 0 1 1 6 -9 Z"); p.setAttribute("transform", "translate(" + X(+j.lng).toFixed(1) + " " + Y(+j.lat).toFixed(1) + ")");
      var t = svgEl("title"); t.textContent = (j.code || "Job") + " · " + (j.status_label || j.status || "") + (j.scheduled_human ? " · " + j.scheduled_human : "") + (j.address ? "\n" + j.address : ""); p.appendChild(t);
      p.addEventListener("click", function(){ openJob(j.id); }); svg.appendChild(p);
    });
    haulers.forEach(function(h){
      var c = svgEl("circle"), st = haulerState(h); c.setAttribute("class", "dp-mh " + st + (SEL_HAULER != null && String(h.id) === String(SEL_HAULER) ? " is-sel" : ""));
      c.setAttribute("cx", X(+h.lng).toFixed(1)); c.setAttribute("cy", Y(+h.lat).toFixed(1)); c.setAttribute("r", 6.5); c.dataset.id = h.id;
      var t = svgEl("title"); t.textContent = (h.name || "Hauler") + " · " + stateText(h) + (h.tier_label ? " · " + h.tier_label : ""); c.appendChild(t);
      c.addEventListener("click", function(){ selectHauler(h.id, true); }); svg.appendChild(c);
    });
    $("dp-map-note").textContent = haulers.length + (haulers.length === 1 ? " hauler" : " haulers") + " on the map, " + jobs.length + (jobs.length === 1 ? " job" : " jobs");
  }
  function selectHauler(id, scroll){
    SEL_HAULER = id;
    Array.prototype.forEach.call(document.querySelectorAll(".dp-mh"), function(c){ c.classList.toggle("is-sel", String(c.dataset.id) === String(id)); });
    var row = null;
    Array.prototype.forEach.call(document.querySelectorAll(".dp-hr"), function(r){ var on = String(r.dataset.id) === String(id); r.classList.toggle("is-sel", on); if(on) row = r; });
    if(!row && scroll){
      // the hauler is filtered out of the roster: widen the filter so the row exists
      ROSTER_FILTER = "all"; setTab("dp-roster-filter", "f", "all"); renderRoster();
      Array.prototype.forEach.call(document.querySelectorAll(".dp-hr"), function(r){ if(String(r.dataset.id) === String(id)) row = r; });
    }
    if(row && scroll){ row.scrollIntoView({block: "nearest", behavior: "smooth"}); }
  }
  function setTab(wrapId, attr, val){ Array.prototype.forEach.call($(wrapId).querySelectorAll("button"), function(b){ b.classList.toggle("on", b.dataset[attr] === val); }); }

  // ---------------------------------------------------------------- roster
  function renderRoster(){
    var box = $("dp-roster"); clear(box);
    var q = ($("dp-roster-q").value || "").trim().toLowerCase();
    var list = DATA.haulers.filter(function(h){
      var st = haulerState(h);
      if(ROSTER_FILTER === "live" && st !== "live") return false;
      if(ROSTER_FILTER === "online" && st === "offline") return false;
      if(q && [h.name, h.county, h.truck_type, h.tier_label, h.phone].join(" ").toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
    var order = {live: 0, online: 1, standby: 2, offline: 3};
    list.sort(function(a, b){ var d = order[haulerState(a)] - order[haulerState(b)]; if(d) return d; return (num(a.seen_minutes) == null ? 1e9 : a.seen_minutes) - (num(b.seen_minutes) == null ? 1e9 : b.seen_minutes); });
    $("dp-roster-note").textContent = list.length + " of " + DATA.haulers.length;
    if(!list.length){ box.appendChild(el("p", "dp-empty", ROSTER_FILTER === "live" ? "Nobody is live right now. Try Online or All." : q ? "No one matches that." : "No haulers yet.")); return; }
    list.forEach(function(h){
      var st = haulerState(h);
      var row = btn("dp-hr" + (SEL_HAULER != null && String(h.id) === String(SEL_HAULER) ? " is-sel" : ""), null, function(){ selectHauler(h.id, false); openHauler(h.id); });
      row.dataset.id = h.id;
      var n = el("div", "n", h.name || "Hauler"); if(h.tier_label) n.appendChild(el("span", "dp-tag", h.tier_label)); if(h.concierge) n.appendChild(el("span", "dp-tag info", "concierge")); row.appendChild(n);
      var s = el("div", "st " + st); s.appendChild(el("i", "dp-dot " + st)); s.appendChild(document.createTextNode(stateText(h))); row.appendChild(s);
      var meta = [];
      if(h.county) meta.push(h.county); if(h.truck_type) meta.push(h.truck_type);
      if(num(h.rating) != null) meta.push("★ " + Number(h.rating).toFixed(1));
      if(num(h.completed) != null) meta.push(h.completed + " done"); else if(num(h.total_jobs) != null) meta.push(h.total_jobs + " jobs");
      if(num(h.jobs_today) != null) meta.push(h.jobs_today + " today");
      row.appendChild(el("div", "m", meta.join(" · ")));
      box.appendChild(row);
    });
  }
  $("dp-roster-q").addEventListener("input", renderRoster);
  $("dp-roster-filter").addEventListener("click", function(e){ var b = e.target.closest("button[data-f]"); if(!b) return; ROSTER_FILTER = b.dataset.f; setTab("dp-roster-filter", "f", ROSTER_FILTER); renderRoster(); });

  // ---------------------------------------------------------------- drawer
  var DRAWER = {kind: null, id: null}, CAND_TOGGLE = null;
  function openDrawer(title, sub){
    CAND_TOGGLE = null;
    $("dp-dr-title").textContent = title || ""; $("dp-dr-sub").textContent = sub || ""; clear($("dp-dr-body"));
    $("dp-drawer").hidden = false; document.body.classList.add("dp-locked");
  }
  function closeDrawer(){ $("dp-drawer").hidden = true; document.body.classList.remove("dp-locked"); DRAWER = {kind: null, id: null}; clear($("dp-dr-body")); }
  $("dp-dr-x").addEventListener("click", closeDrawer);
  $("dp-drawer").addEventListener("click", function(e){ if(e.target === $("dp-drawer")) closeDrawer(); });
  document.addEventListener("keydown", function(e){ if(e.key === "Escape" && !$("dp-drawer").hidden) closeDrawer(); });
  function section(title, note){ var s = el("div", "dp-sec"); if(title) s.appendChild(el("h4", null, title)); if(note) s.appendChild(el("span", "dp-note", note)); return s; }
  function kv(pairs){ var dl = el("dl", "dp-kv"); pairs.forEach(function(p){ if(p[1] == null || p[1] === "") return; dl.appendChild(el("dt", null, p[0])); var dd = el("dd"); if(p[1] instanceof Node) dd.appendChild(p[1]); else dd.textContent = String(p[1]); dl.appendChild(dd); }); return dl; }
  function telLink(phone, sms){ var a = el("a", "dp-tel", fmtPhone(phone)); a.href = (sms ? "sms:" : "tel:") + telHref(phone); return a; }
  function contactLinks(phone){ var w = el("span"); if(!phone) return el("span", null, "no phone"); w.appendChild(telLink(phone)); w.appendChild(document.createTextNode("  ")); var s = el("a", "dp-lnk", "text"); s.href = "sms:" + telHref(phone); w.appendChild(s); return w; }

  // ---------------------------------------------------------------- hauler drawer
  function openHauler(id){
    DRAWER = {kind: "hauler", id: id};
    var base = null; DATA.haulers.forEach(function(h){ if(String(h.id) === String(id)) base = h; });
    openDrawer(base ? base.name : "Hauler", base ? stateText(base) : "");
    var body = $("dp-dr-body"); body.appendChild(el("p", "dp-empty", "Loading…"));
    api("hauler", {contractor_id: id}).then(function(d){
      if(DRAWER.kind !== "hauler" || String(DRAWER.id) !== String(id)) return;
      clear(body); var h = d.hauler || base || {}; renderHaulerDrawer(h);
    }).catch(function(e){ clear(body); body.appendChild(el("p", "dp-empty", e.message || "Couldn't load this hauler.")); });
  }
  function renderHaulerDrawer(h){
    var body = $("dp-dr-body"), st = haulerState(h);
    $("dp-dr-title").textContent = h.name || "Hauler";
    var sub = el("span"); sub.appendChild(el("i", "dp-dot " + st)); sub.appendChild(document.createTextNode(stateText(h) + (h.tier_label ? " · " + h.tier_label : "") + (h.county ? " · " + h.county : ""))); clear($("dp-dr-sub")); $("dp-dr-sub").appendChild(sub);

    var c = section("Contact");
    var docs = h.docs || {}, ver = docs.verification;
    c.appendChild(kv([
      ["Phone", h.phone ? contactLinks(h.phone) : null],
      ["Email", h.email ? (function(){ var a = el("a", "dp-lnk", h.email); a.href = "mailto:" + h.email; return a; })() : null],
      ["Works via", h.kind === "app" ? "the app" : h.kind === "text" ? "text messages" : h.kind === "operator" ? "operator account" : h.kind],
      ["Truck", h.truck_type], ["Approved", h.approved == null ? null : h.approved ? "yes" : "not yet"],
      ["Payouts", h.stripe == null ? null : (typeof h.stripe === "string" ? h.stripe : h.stripe ? "Stripe connected" : "no Stripe yet")],
      ["Insurance", docs.insurance_expiry ? "expires " + docs.insurance_expiry : null], ["License", docs.license_expiry ? "expires " + docs.license_expiry : null],
      ["Verification", ver == null ? null : (typeof ver === "string" ? ver : JSON.stringify(ver))]
    ]));
    body.appendChild(c);

    var s = h.stats || {}, stats = el("div", "dp-stats");
    [["offered", "Offered"], ["accepted", "Accepted"], ["completed", "Done"], ["no_shows", "No-shows"]].forEach(function(p){ var v = s[p[0]] != null ? s[p[0]] : h[p[0]]; var d = el("div", "dp-stat"); d.appendChild(el("b", null, v == null ? "–" : String(v))); d.appendChild(el("span", null, p[1])); stats.appendChild(d); });
    var ss = section("Track record", [num(h.rating) != null ? "★ " + Number(h.rating).toFixed(1) : "", num(h.jobs_today) != null ? h.jobs_today + " today" : "", s.last_completed_at ? "last finished " + when(s.last_completed_at) : ""].filter(Boolean).join(" · "));
    ss.appendChild(stats); body.appendChild(ss);

    var tx = section("Text from the desk", "Sent from the Umuve number, signed as you.");
    var ta = el("textarea"); ta.rows = 3; ta.value = "Hi " + (String(h.name || "").split(" ")[0] || "there") + ", it's " + (firstName() || "the desk") + " from Umuve — "; tx.appendChild(ta);
    var row = el("div", "dp-actions"); var send = btn("pill dark", "Send text", function(){
      var bodyTxt = ta.value.trim(); if(!bodyTxt){ toast("Write the text first.", "bad"); return; } send.disabled = true;
      api("hauler/text", {contractor_id: h.id, body: bodyTxt}).then(function(){ toast("Texted " + (h.name || "the hauler"), "good"); ta.value = ""; send.disabled = false; }).catch(function(e){ fail(e); send.disabled = false; });
    }); row.appendChild(send); tx.appendChild(row); body.appendChild(tx);

    var open = (DATA.jobs && DATA.jobs.open) || [];
    var as = section("Assign to a job", open.length ? "Jobs that still need a hauler." : "Nothing needs a hauler right now.");
    if(open.length){
      var sel = el("select"); sel.appendChild(el("option", null, "Pick a job")); sel.firstChild.value = "";
      open.forEach(function(j){ var o = el("option", null, (j.code || "Job") + " · " + (j.scheduled_human || "unscheduled") + " · " + (j.county || j.address || "")); o.value = j.id; sel.appendChild(o); });
      as.appendChild(sel);
      var ar = el("div", "dp-actions"), why = el("p", "dp-empty"); why.hidden = true;
      var ab = btn("pill dark", "Assign", function(){ if(!sel.value){ toast("Pick a job first.", "bad"); return; } doAssign(sel.value, h.id, false, ab, why, function(){ openHauler(h.id); }); });
      ar.appendChild(ab); as.appendChild(ar); as.appendChild(why);
    }
    body.appendChild(as);

    var rj = section("Recent jobs");
    rj.appendChild(jobHistory(h.recent_jobs || [])); body.appendChild(rj);
  }
  function jobHistory(list){
    var rows = el("div", "dp-rows");
    if(!list.length){ rows.appendChild(el("p", "dp-empty", "None yet.")); return rows; }
    list.forEach(function(j){
      var r = el("div", "dp-row"); r.appendChild(el("span", "t", j.when || "")); var w = el("div", "w"); w.appendChild(document.createTextNode((j.code || "") + (j.status ? " · " + j.status : "")));
      if(j.address) w.appendChild(el("span", null, j.address)); r.appendChild(w); r.appendChild(el("span", "amt", money(j.total))); rows.appendChild(r);
    });
    return rows;
  }
  // assign with a 409 fallback to "assign anyway"
  function doAssign(jobId, contractorId, force, b, whyBox, after){
    b.disabled = true; if(whyBox){ whyBox.hidden = true; clear(whyBox); }
    api("assign-hauler", {job_id: jobId, contractor_id: contractorId, force: !!force}).then(function(d){
      toast(d.message || "Assigned", "good"); b.disabled = false; load().then(after || function(){});
    }).catch(function(e){
      b.disabled = false;
      if(e.status === 409 && whyBox){
        clear(whyBox); whyBox.hidden = false; whyBox.className = "dp-inline";
        whyBox.appendChild(el("div", "bad", e.message || "Blocked"));
        ((e.body && e.body.reasons) || []).forEach(function(r){ whyBox.appendChild(el("div", "note", "· " + r)); });
        var row = el("div", "row"); row.appendChild(armed(btn("pill danger", "Assign anyway"), "Tap again to force it", function(x){ doAssign(jobId, contractorId, true, x, whyBox, after); })); whyBox.appendChild(row);
      } else fail(e);
    });
  }

  // ---------------------------------------------------------------- job cards
  function card(j, group, full){
    var c = el("div", "dp-card" + (full ? " is-full" : ""));
    if(!full) c.addEventListener("click", function(e){ if(e.target.closest("button, a, .dp-inline")) return; openJob(j.id); });
    var top = el("div", "top"); top.appendChild(el("span", "code", j.code || "—"));
    top.appendChild(el("span", "dp-tag " + (group === "open" ? "accent" : group === "active" ? "info" : group === "done" ? "ok" : group === "cancelled" ? "danger" : "dark"), j.status_label || j.status || group));
    var pi = payInfo(j.payment); top.appendChild(el("span", "dp-tag " + pi.cls, pi.text));
    if(j.confirmed) top.appendChild(el("span", "dp-tag ok", "✓ confirmed" + (j.confirmed_by ? " by " + j.confirmed_by : "")));
    c.appendChild(top);
    var w = el("div", "when", (j.scheduled_human || "No time set") + (j.window ? " · " + j.window : "")); var hh = group === "done" || group === "cancelled" ? null : hoursHint(j.hours_out); if(hh) w.appendChild(el("span", "hint " + hh.cls, hh.text)); c.appendChild(w);
    var ad = el("div", "addr", j.address || "No address"); if(j.county) ad.appendChild(el("span", null, " · " + j.county)); c.appendChild(ad);
    var items = j.items || [], names = items.slice(0, 3).map(function(i){ return (i.qty > 1 ? i.qty + "× " : "") + (i.name || ""); });
    c.appendChild(el("div", "items", names.length ? names.join(", ") + (items.length > 3 ? " +" + (items.length - 3) : "") : (j.items_text || (j.item_count ? j.item_count + " items" : "No items listed"))));
    var m = el("div", "money"); m.appendChild(el("b", null, money(j.total))); if(num(j.disposal_fee)) m.appendChild(el("span", null, "incl. " + money(j.disposal_fee) + " dump fee")); if(num(j.service_fee)) m.appendChild(el("span", null, money(j.service_fee) + " service")); c.appendChild(m);
    var who = el("div", "who"), cu = j.customer || {}, cl = el("div"); cl.appendChild(document.createTextNode((cu.name || "Customer") + " ")); if(cu.phone) cl.appendChild(telLink(cu.phone)); if(num(cu.prior_jobs)) cl.appendChild(el("span", null, " · " + cu.prior_jobs + " prior")); who.appendChild(cl);
    var hl = el("div"); if(j.hauler){ hl.appendChild(document.createTextNode("Hauler: " + (j.hauler.name || "") + " ")); if(j.hauler.tier_label) hl.appendChild(el("span", "dp-tag", j.hauler.tier_label)); if(j.hauler.phone){ hl.appendChild(document.createTextNode(" ")); hl.appendChild(telLink(j.hauler.phone)); } } else hl.appendChild(el("span", "none", group === "open" ? "No hauler yet" : "—")); who.appendChild(hl); c.appendChild(who);
    if(full && j.notes) c.appendChild(el("div", "notes", j.notes));
    if(j.lead_source) c.appendChild(el("div", "src", "via " + j.lead_source));
    var acts = actions(j, group, c); if(acts) c.appendChild(acts);
    return c;
  }

  // Inline editor host: one open at a time per card.
  function inline(host){ var old = host.querySelector(".dp-inline"); if(old) old.remove(); var box = el("div", "dp-inline"); box.addEventListener("click", function(e){ e.stopPropagation(); }); host.appendChild(box); return box; }
  function closeInline(host){ var old = host.querySelector(".dp-inline"); if(old) old.remove(); }
  function afterAction(j, msg){ toast(msg || "Done", "good"); return load().then(function(){ if(DRAWER.kind === "job" && String(DRAWER.id) === String(j.id)) openJob(j.id); }); }

  function actions(j, group, host){
    var row = el("div", "dp-actions"), cu = j.customer || {}, h = j.hauler;
    function textEditor(to){
      var box = inline(host), name = to === "customer" ? (String(cu.name || "").split(" ")[0] || "there") : (h ? String(h.name || "").split(" ")[0] || "there" : "there");
      box.appendChild(el("div", "lbl", "Text the " + to + (to === "customer" ? (cu.phone ? " · " + fmtPhone(cu.phone) : "") : (h && h.phone ? " · " + fmtPhone(h.phone) : ""))));
      var ta = el("textarea"); ta.value = "Hi " + name + ", it's " + (firstName() || "the desk") + " from Umuve — " + (to === "customer" ? "about your pickup " + (j.scheduled_human ? j.scheduled_human + (j.window ? " (" + j.window + ")" : "") : "") + ". " : "about job " + (j.code || "") + (j.scheduled_human ? " on " + j.scheduled_human : "") + ". "); box.appendChild(ta);
      var r = el("div", "row"); var send = btn("pill dark", "Send text", function(){ var t = ta.value.trim(); if(!t){ toast("Write the text first.", "bad"); return; } send.disabled = true; api("job/text", {job_id: j.id, to: to, body: t}).then(function(){ closeInline(host); toast("Texted the " + to, "good"); }).catch(function(e){ fail(e); send.disabled = false; }); });
      r.appendChild(send); r.appendChild(btn("pill", "Never mind", function(){ closeInline(host); })); box.appendChild(r); ta.focus();
    }
    function rescheduleEditor(){
      var box = inline(host); box.appendChild(el("div", "lbl", "Move this job"));
      var r1 = el("div", "row"); var date = el("input"); date.type = "date"; var d0 = parseIso(j.scheduled_at); date.value = d0 ? d0.getFullYear() + "-" + String(d0.getMonth() + 1).padStart(2, "0") + "-" + String(d0.getDate()).padStart(2, "0") : todayIso();
      var slot = el("select"); slot.appendChild(el("option", null, "Loading windows…")); r1.appendChild(date); r1.appendChild(slot); box.appendChild(r1);
      var notify = el("label", "bk-check"); var cb = el("input"); cb.type = "checkbox"; cb.checked = true; notify.appendChild(cb); notify.appendChild(document.createTextNode(" Text the customer the new time")); box.appendChild(notify);
      function loadSlots(){ fillSlots(slot, date.value, j.lat, j.lng); }
      date.addEventListener("change", loadSlots); loadSlots();
      var r2 = el("div", "row"); var save = btn("pill dark", "Save new time", function(){ if(!slot.value){ toast("Pick an arrival window.", "bad"); return; } save.disabled = true; api("job/reschedule", {job_id: j.id, scheduled_date: date.value, scheduled_time: slot.value, notify: cb.checked}).then(function(){ afterAction(j, "Moved " + (j.code || "the job")); }).catch(function(e){ fail(e); save.disabled = false; }); });
      r2.appendChild(save); r2.appendChild(btn("pill", "Never mind", function(){ closeInline(host); })); box.appendChild(r2);
    }
    function cancelEditor(){
      var box = inline(host); box.appendChild(el("div", "lbl", "Why is it cancelled?"));
      var reason = el("input"); reason.type = "text"; reason.placeholder = "Customer changed their mind, no answer, duplicate…"; box.appendChild(reason);
      var r = el("div", "row"); r.appendChild(armed(btn("pill danger", "Cancel this job"), "Tap again to cancel it", function(b){ api("job/cancel", {job_id: j.id, reason: reason.value.trim()}).then(function(){ afterAction(j, "Cancelled " + (j.code || "the job")); }).catch(function(e){ fail(e); b.disabled = false; }); }));
      r.appendChild(btn("pill", "Keep it", function(){ closeInline(host); })); box.appendChild(r); reason.focus();
    }
    function cantMake(){
      var box = inline(host); box.appendChild(el("div", "lbl", "What happened?"));
      var note = el("input"); note.type = "text"; note.placeholder = "Truck down, running late, no answer…"; box.appendChild(note);
      var r = el("div", "row"); r.appendChild(armed(btn("pill danger", "Hauler can't make it"), "Tap again to release the job", function(b){ api("job/confirm", {job_id: j.id, confirmed: false, note: note.value.trim()}).then(function(d){ afterAction(j, d.released ? "Released back to the board" : "Noted"); }).catch(function(e){ fail(e); b.disabled = false; }); }));
      r.appendChild(btn("pill", "Never mind", function(){ closeInline(host); })); box.appendChild(r);
    }
    function transition(label, status){
      return armed(btn("pill dark", label), "Tap again: " + label.toLowerCase(), function(b){ api("job/transition", {job_id: j.id, status: status, reason: "desk"}).then(function(){ afterAction(j, label.replace(/^Mark /, "Marked ") + " · " + (j.code || "")); }).catch(function(e){ fail(e); b.disabled = false; }); });
    }
    function payLink(){ return btn("pill", j.payment && j.payment.link_sent ? "Resend pay link" : "Send pay link", function(){ this.disabled = true; var b = this; api("job/paylink", {job_id: j.id, send: true}).then(function(d){ toast(d.texted ? "Pay link texted to the customer" : "Pay link ready" + (d.url ? " — copied" : ""), "good"); if(!d.texted && d.url) copyText(d.url).catch(function(){}); b.disabled = false; load(); }).catch(function(e){ fail(e); b.disabled = false; }); }); }
    function assignBtn(label){ return btn("pill dark", label, function(){ if(DRAWER.kind === "job" && String(DRAWER.id) === String(j.id) && CAND_TOGGLE) CAND_TOGGLE(); else openJob(j.id, "candidates"); }); }

    if(group === "open"){
      row.appendChild(assignBtn("Assign"));
      row.appendChild(btn("pill", "Broadcast", function(){ this.disabled = true; var b = this; api("job/broadcast", {job_id: j.id}).then(function(d){ toast(d.message || ("Offered to " + (d.offers || 0) + " haulers"), "good"); b.disabled = false; load(); }).catch(function(e){ fail(e); b.disabled = false; }); }));
      row.appendChild(payLink());
      row.appendChild(btn("pill", "Text customer", function(){ textEditor("customer"); }));
      row.appendChild(btn("pill", "Reschedule", rescheduleEditor));
      row.appendChild(btn("pill danger", "Cancel", cancelEditor));
    } else if(group === "scheduled"){
      if(!j.confirmed) row.appendChild(btn("pill dark", "✓ Hauler confirmed", function(){ this.disabled = true; var b = this; api("job/confirm", {job_id: j.id, confirmed: true, note: ""}).then(function(){ afterAction(j, "Confirmed " + (h ? h.name : "the hauler")); }).catch(function(e){ fail(e); b.disabled = false; }); }));
      row.appendChild(btn("pill", "Can't make it", cantMake));
      row.appendChild(assignBtn("Reassign"));
      row.appendChild(transition("Mark en route", "en_route"));
      row.appendChild(btn("pill", "Text hauler", function(){ textEditor("hauler"); }));
      row.appendChild(btn("pill", "Text customer", function(){ textEditor("customer"); }));
      row.appendChild(btn("pill", "Reschedule", rescheduleEditor));
      row.appendChild(btn("pill danger", "Cancel", cancelEditor));
    } else if(group === "active"){
      if(j.status === "en_route") row.appendChild(transition("Mark arrived", "arrived"));
      else if(j.status === "arrived") row.appendChild(transition("Mark started", "started"));
      else if(j.status === "started") row.appendChild(transition("Mark completed", "completed"));
      row.appendChild(btn("pill", "Text hauler", function(){ textEditor("hauler"); }));
      row.appendChild(btn("pill", "Text customer", function(){ textEditor("customer"); }));
    } else {
      if(!host.classList.contains("is-full")) row.appendChild(btn("pill", "Open", function(){ openJob(j.id); }));
      else return null;
    }
    return row;
  }

  // ---------------------------------------------------------------- board
  function renderBoard(){
    var J = DATA.jobs || {}, c = DATA.counts || {};
    $("dp-t-open").textContent = String((J.open || []).length); $("dp-t-scheduled").textContent = String((J.scheduled || []).length); $("dp-t-active").textContent = String((J.active || []).length);
    $("dp-t-done").textContent = String((J.done || []).length); $("dp-t-cancelled").textContent = String((J.cancelled || []).length || c.cancelled_today || 0);
    var box = $("dp-board");
    if(box.querySelector(".dp-inline")) return;   // someone is mid-edit; leave the board alone this refresh
    clear(box);
    var list = J[BOARD_TAB] || [];
    if(!list.length){ var msgs = {open: "Nothing waiting on a hauler.", scheduled: "Nothing scheduled with a hauler yet.", active: "No trucks rolling right now.", done: "Nothing finished today yet.", cancelled: "No cancellations today."}; box.appendChild(el("p", "dp-empty", msgs[BOARD_TAB] || "Nothing here.")); return; }
    list.forEach(function(j){ box.appendChild(card(j, BOARD_TAB, false)); });
  }
  $("dp-board-tabs").addEventListener("click", function(e){ var b = e.target.closest("button[data-t]"); if(!b) return; BOARD_TAB = b.dataset.t; setTab("dp-board-tabs", "t", BOARD_TAB); closeInline($("dp-board")); renderBoard(); });

  // ---------------------------------------------------------------- job drawer
  function openJob(id, focus){
    DRAWER = {kind: "job", id: id};
    var known = findJob(id);
    openDrawer(known ? known.job.code || "Job" : "Job", known ? (known.job.status_label || "") : "");
    var body = $("dp-dr-body"); body.appendChild(el("p", "dp-empty", "Loading…"));
    api("job", {job_id: id}).then(function(d){
      if(DRAWER.kind !== "job" || String(DRAWER.id) !== String(id)) return;
      clear(body); renderJobDrawer(d, focus);
    }).catch(function(e){ clear(body); body.appendChild(el("p", "dp-empty", e.message || "Couldn't load this job.")); });
  }
  function renderJobDrawer(d, focus){
    var body = $("dp-dr-body"), j = d.job || {}, group = groupOf(j.status);
    $("dp-dr-title").textContent = (j.code || "Job") + (j.customer && j.customer.name ? " · " + j.customer.name : "");
    $("dp-dr-sub").textContent = [j.status_label || j.status, j.scheduled_human, j.county].filter(Boolean).join(" · ");
    body.appendChild(card(j, group, true));

    var cand = section("Find a hauler", "Best match first. Blocked haulers show why."); cand.hidden = true;
    var candBox = el("div", "dp-rows"); cand.appendChild(candBox); body.appendChild(cand);
    if(group === "open" || group === "scheduled"){
      CAND_TOGGLE = function(){ cand.hidden = false; loadCandidates(); cand.scrollIntoView({block: "nearest", behavior: "smooth"}); };
    }
    function loadCandidates(){
      clear(candBox); candBox.appendChild(el("p", "dp-empty", "Looking…"));
      api("candidates", {job_id: j.id}).then(function(r){
        clear(candBox); var list = r.haulers || [];
        if(!list.length){ candBox.appendChild(el("p", "dp-empty", "No approved haulers to offer this to.")); return; }
        list.forEach(function(h){
          var row = el("div", "dp-cand"); var n = el("div", "n", h.name || "Hauler"); if(h.tier_label) n.appendChild(el("span", "dp-tag", h.tier_label)); row.appendChild(n);
          var meta = [num(h.distance_miles) != null ? Number(h.distance_miles).toFixed(1) + " mi" : null, stateText(h), h.truck_type, num(h.jobs_today) != null ? h.jobs_today + " today" : null].filter(Boolean);
          var m = el("div", "m"); m.appendChild(el("i", "dp-dot " + haulerState(h))); m.appendChild(document.createTextNode(meta.join(" · "))); row.appendChild(m);
          var act = el("div", "act"), why = el("div"); why.hidden = true;
          if(h.ok){ var ab = btn("pill dark", "Assign", function(){ doAssign(j.id, h.id, false, ab, why, function(){ openJob(j.id); }); }); act.appendChild(ab); }
          else { act.appendChild(armed(btn("pill danger", "Assign anyway"), "Tap again to force it", function(b){ doAssign(j.id, h.id, true, b, why, function(){ openJob(j.id); }); })); }
          row.appendChild(act);
          if((h.reasons || []).length){ var ul = el("ul", "why"); h.reasons.forEach(function(x){ ul.appendChild(el("li", null, x)); }); row.appendChild(ul); }
          if((h.warnings || []).length){ var wl = el("ul", "warnl"); h.warnings.forEach(function(x){ wl.appendChild(el("li", null, x)); }); row.appendChild(wl); }
          row.appendChild(why);
          candBox.appendChild(row);
        });
      }).catch(function(e){ clear(candBox); candBox.appendChild(el("p", "dp-empty", e.message || "Couldn't load candidates.")); });
    }
    if(focus === "candidates" && (group === "open" || group === "scheduled")){ cand.hidden = false; loadCandidates(); }

    if(j.tracking_url){
      var tl = section("Customer tracking link"); var cp = el("div", "dp-copy"); var inp = el("input"); inp.type = "text"; inp.readOnly = true; inp.value = j.tracking_url; cp.appendChild(inp);
      var cb = btn("pill", "Copy", function(){ copyText(j.tracking_url).then(function(){ cb.textContent = "Copied"; setTimeout(function(){ cb.textContent = "Copy"; }, 1200); }).catch(function(){ inp.select(); }); }); cp.appendChild(cb);
      var op = el("a", "pill", "Open"); op.href = j.tracking_url; op.target = "_blank"; op.rel = "noopener"; cp.appendChild(op); tl.appendChild(cp); body.appendChild(tl);
    }

    if(d.dump){
      var dm = section("Dump suggestion"); var box = el("div", "dp-dump");
      box.appendChild(el("b", null, d.dump.facility || "Nearest facility"));
      box.appendChild(el("span", null, [num(d.dump.miles) != null ? Number(d.dump.miles).toFixed(1) + " mi" : null, num(d.dump.minutes) != null ? Math.round(d.dump.minutes) + " min" : null, num(d.dump.rate_per_ton) != null ? money(d.dump.rate_per_ton) + "/ton" : null, num(d.dump.est_tip) != null ? "est. tip " + money(d.dump.est_tip) : null].filter(Boolean).join(" · ")));
      (d.dump.reasons || []).forEach(function(r){ box.appendChild(el("span", null, r)); }); dm.appendChild(box); body.appendChild(dm);
    }

    var ev = section("What's happened", (d.events || []).length ? null : "Nothing logged yet."); var tlst = el("div", "dp-rows dp-timeline");
    (d.events || []).forEach(function(e){ var r = el("div", "dp-row"); r.appendChild(el("span", "t", when(e.at))); var w = el("div", "w"); w.appendChild(document.createTextNode((e.type || "").replace(/_/g, " ") + (e.actor ? " · " + e.actor : ""))); if(e.detail) w.appendChild(el("span", null, typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail))); r.appendChild(w); tlst.appendChild(r); });
    ev.appendChild(tlst); body.appendChild(ev);

    var cj = section("This customer's other jobs"); cj.appendChild(jobHistory((d.customer_jobs || []).filter(function(x){ return x.code !== j.code; }))); body.appendChild(cj);
  }

  // ---------------------------------------------------------------- recent
  function renderRecent(){
    var box = $("dp-recent"); clear(box); var list = DATA.recent || [];
    if(!list.length){ box.appendChild(el("p", "dp-empty", "Quiet so far.")); return; }
    list.forEach(function(r){
      var row = el("div", "dp-row"); row.appendChild(el("span", "t", when(r.at)));
      var w = el("div", "w"); if(r.who) w.appendChild(el("span", "who", r.who)); w.appendChild(document.createTextNode((r.who ? " " : "") + (r.action || "")));
      if(r.job_code){ var cb = btn("code", r.job_code, function(){ var found = null; allJobs().forEach(function(x){ if(x.job.code === r.job_code) found = x.job; }); if(found) openJob(found.id); else toast("That job isn't on today's board.", ""); }); w.appendChild(cb); }
      if(r.detail) w.appendChild(el("span", null, r.detail)); row.appendChild(w); box.appendChild(row);
    });
  }

  // ---------------------------------------------------------------- new booking
  var BK = {items: {}, addons: {}, load: null, geo: null, pay: "link", hauler: "open", customer_id: null};
  var bookOpen = false;
  function openBook(){
    bookOpen = true; $("dp-book").hidden = false; resetBook();
    ensureCatalog().then(renderItems).catch(fail);
    $("bk-date").value = todayIso(); loadBookSlots(); refreshHaulerSelect();
    $("dp-book").scrollIntoView({block: "start", behavior: "smooth"}); setTimeout(function(){ $("bk-phone").focus(); }, 300);
  }
  function closeBook(){ bookOpen = false; $("dp-book").hidden = true; }
  function resetBook(){
    BK = {items: {}, addons: {}, load: null, geo: null, pay: "link", hauler: "open", customer_id: null};
    ["bk-phone", "bk-name", "bk-email", "bk-address", "bk-notes", "bk-items-q"].forEach(function(id){ $(id).value = ""; });
    $("bk-matches").hidden = true; clear($("bk-matches")); $("bk-geo").hidden = true; $("bk-err").hidden = true; $("bk-sendtext").checked = true;
    setTab("bk-pay", "v", "link"); setTab("bk-hauler", "v", "open"); $("bk-hauler-sel").hidden = true;
    clear($("bk-est")); $("bk-est").appendChild(el("p", "dp-empty", "Add items to see a price."));
    if(CATALOG) renderItems();
  }
  $("dp-new").addEventListener("click", function(){ if(bookOpen) closeBook(); else openBook(); });
  $("bk-close").addEventListener("click", closeBook); $("bk-cancel").addEventListener("click", closeBook);
  function ensureCatalog(){ if(CATALOG) return Promise.resolve(CATALOG); return api("catalog", {}).then(function(c){ CATALOG = c || {}; CATALOG.items = CATALOG.items || []; CATALOG.addons = CATALOG.addons || []; CATALOG.loads = CATALOG.loads || []; return CATALOG; }); }

  function stepper(get, set, max){
    var w = el("div", "bk-step"), minus = btn(null, "−"), out = el("output"), plus = btn(null, "+");
    function paint(){ var v = get(); out.textContent = String(v); minus.disabled = v <= 0; plus.disabled = v >= (max || 20); w.classList.toggle("is-on", v > 0); }
    minus.addEventListener("click", function(){ set(Math.max(0, get() - 1)); paint(); }); plus.addEventListener("click", function(){ set(Math.min(max || 20, get() + 1)); paint(); });
    w.appendChild(minus); w.appendChild(out); w.appendChild(plus); paint(); return w;
  }
  function renderItems(){
    var box = $("bk-items"); clear(box); var q = ($("bk-items-q").value || "").trim().toLowerCase(), lastGroup = null, n = 0;
    CATALOG.items.forEach(function(it){
      if(q && String(it.name || "").toLowerCase().indexOf(q) < 0 && String(it.group || "").toLowerCase().indexOf(q) < 0) return;
      if(it.group && it.group !== lastGroup && !q){ var g = el("div", "bk-item"); g.appendChild(el("div", "bk-group", it.group)); box.appendChild(g); lastGroup = it.group; }
      var st = BK.items[it.key] || {qty: 0, size: it.sizes ? "medium" : null};
      var row = el("div", "bk-item" + (st.qty > 0 ? " is-on" : "")); var name = el("div", "n", it.name || it.key); row.appendChild(name);
      var price = it.sizes && it.sizes[st.size] != null ? it.sizes[st.size] : it.price; row.appendChild(el("div", "p", money(price)));
      row.appendChild(stepper(function(){ return (BK.items[it.key] || st).qty; }, function(v){ st.qty = v; BK.items[it.key] = st; row.classList.toggle("is-on", v > 0); if(v > 0 && BK.load){ BK.load = null; paintLoads(); } estimateSoon(); }));
      if(it.sizes){
        var sel = el("select"); ["small", "medium", "large"].forEach(function(s){ if(it.sizes[s] == null) return; var o = el("option", null, s.charAt(0).toUpperCase() + s.slice(1) + " · " + money(it.sizes[s])); o.value = s; if(s === st.size) o.selected = true; sel.appendChild(o); });
        sel.addEventListener("change", function(){ st.size = sel.value; BK.items[it.key] = st; row.querySelector(".p").textContent = money(it.sizes[st.size]); estimateSoon(); }); row.appendChild(sel);
      }
      box.appendChild(row); n++;
    });
    if(!n) box.appendChild(el("p", "dp-empty", CATALOG.items.length ? "Nothing matches that." : "The catalog is empty."));
    // loads + addons render once
    var lw = $("bk-loads-wrap"), lb = $("bk-loads"); if(CATALOG.loads.length){ lw.hidden = false; if(!lb.childElementCount) CATALOG.loads.forEach(function(l){ var p = btn("pill", (l.label || l.key) + " · " + money(l.price), function(){ BK.load = BK.load === l.key ? null : l.key; if(BK.load){ BK.items = {}; renderItems(); } paintLoads(); estimateSoon(); }); p.dataset.key = l.key; lb.appendChild(p); }); paintLoads(); }
    var aw = $("bk-addons-wrap"), ab = $("bk-addons"); if(CATALOG.addons.length){ aw.hidden = false; if(!ab.childElementCount) CATALOG.addons.forEach(function(a){ var r = el("div", "bk-addon"); var l = el("div", null, a.label || a.key); if(num(a.price) != null) l.appendChild(el("span", null, money(a.price) + " each")); r.appendChild(l); r.appendChild(stepper(function(){ return BK.addons[a.key] || 0; }, function(v){ BK.addons[a.key] = v; estimateSoon(); })); ab.appendChild(r); }); }
  }
  function paintLoads(){ Array.prototype.forEach.call($("bk-loads").querySelectorAll(".pill"), function(p){ p.classList.toggle("on", p.dataset.key === BK.load); }); }
  $("bk-items-q").addEventListener("input", function(){ if(CATALOG) renderItems(); });

  function bookItems(){
    var out = [];
    Object.keys(BK.items).forEach(function(k){ var s = BK.items[k]; if(s.qty > 0){ var o = {category: k, quantity: s.qty}; if(s.size) o.size = s.size; out.push(o); } });
    if(BK.load) out.push({category: BK.load, quantity: 1});
    return out;
  }
  function bookAddons(){ var a = {}; Object.keys(BK.addons).forEach(function(k){ if(BK.addons[k] > 0) a[k] = BK.addons[k]; }); return a; }
  var estimateSoon = debounce(function(){
    var items = bookItems(), box = $("bk-est");
    if(!items.length){ clear(box); box.appendChild(el("p", "dp-empty", "Add items to see a price.")); return; }
    box.classList.add("is-stale");
    api("estimate", {items: items, addons: bookAddons(), scheduled_date: $("bk-date").value || todayIso(), lat: BK.geo ? BK.geo.lat : null, lng: BK.geo ? BK.geo.lng : null}).then(function(r){
      box.classList.remove("is-stale"); clear(box); var e = r.estimate || r;
      function ln(label, v, cls){ if(v == null) return; var d = el("div", "ln" + (cls ? " " + cls : "")); d.appendChild(el("span", null, label)); d.appendChild(el("b", null, typeof v === "number" ? money(v) : String(v))); box.appendChild(d); }
      (e.items || []).forEach(function(i){ ln((i.quantity > 1 ? i.quantity + "× " : "") + (i.name || i.category || ""), num(i.line_total)); });
      if(num(e.volume_discount)) ln(e.volume_discount_label || "Volume discount", -Math.abs(e.volume_discount), "disc");
      if(num(e.surge_amount)) ln("Surge" + ((e.surge_reasons || []).length ? " · " + e.surge_reasons.join(", ") : ""), e.surge_amount, "surge");
      if(num(e.addons_total)) ln("Extras", e.addons_total);
      if(num(e.service_fee)) ln("Service fee", e.service_fee);
      if(num(e.recycling_fees)) ln("Recycling", e.recycling_fees);
      if(num(e.disposal_fee)) ln("Dump fee", e.disposal_fee);
      var tot = el("div", "tot"); tot.appendChild(el("b", null, money(e.total))); tot.appendChild(el("span", null, "all-in")); box.appendChild(tot);
      if(e.minimum_applied) box.appendChild(el("div", "fine min", "Job minimum applied" + (CATALOG && num(CATALOG.minimum) ? " (" + money(CATALOG.minimum) + ")" : "")));
      var fine = [e.estimated_duration ? "about " + (typeof e.estimated_duration === "number" ? e.estimated_duration + " min" : e.estimated_duration) : null, e.truck_size ? e.truck_size + " truck" : null].filter(Boolean).join(" · "); if(fine) box.appendChild(el("div", "fine", fine));
    }).catch(function(err){ box.classList.remove("is-stale"); clear(box); box.appendChild(el("p", "dp-empty", err.message || "Couldn't price that.")); });
  }, 400);

  // customer lookup as they type
  var lookup = debounce(function(){
    var d = digits($("bk-phone").value), box = $("bk-matches");
    if(d.length < 3){ box.hidden = true; clear(box); return; }
    api("customer", {q: d}).then(function(r){
      clear(box); var list = r.customers || []; if(!list.length){ box.hidden = true; return; }
      list.slice(0, 6).forEach(function(c){
        var b = btn(null, (c.name || "Unnamed") + " · " + fmtPhone(c.phone)); var lj = c.last_job;
        b.appendChild(el("span", null, (num(c.prior_jobs) ? c.prior_jobs + " prior job" + (c.prior_jobs === 1 ? "" : "s") : "no jobs yet") + (lj ? " · last " + (lj.when || "") + " " + (lj.code || "") + " " + money(lj.total) : "") + (c.email ? " · " + c.email : "")));
        b.addEventListener("click", function(){ $("bk-phone").value = fmtPhone(c.phone); if(c.name) $("bk-name").value = c.name; if(c.email) $("bk-email").value = c.email; BK.customer_id = c.id; box.hidden = true; clear(box); $("bk-address").focus(); });
        box.appendChild(b);
      });
      box.hidden = false;
    }).catch(function(){ box.hidden = true; });
  }, 300);
  $("bk-phone").addEventListener("input", function(){ var d = digits(this.value).slice(0, 11); if(d.length === 11 && d.charAt(0) === "1") d = d.slice(1); this.value = d.length === 10 ? fmtPhone(d) : d; BK.customer_id = null; lookup(); });

  function geocode(){
    var addr = $("bk-address").value.trim(), msg = $("bk-geo"); if(!addr){ msg.hidden = false; msg.className = "bk-geo bad"; msg.textContent = "Type the address first."; return; }
    msg.hidden = false; msg.className = "bk-geo"; msg.textContent = "Looking it up…"; $("bk-find").disabled = true;
    api("geocode", {address: addr}).then(function(r){
      $("bk-find").disabled = false;
      if(!r.ok || num(r.lat) == null){ BK.geo = null; msg.className = "bk-geo bad"; msg.textContent = r.message || "Couldn't find that address. Add the city or ZIP."; return; }
      BK.geo = {lat: r.lat, lng: r.lng, in_area: !!r.in_area, county: r.county || null};
      msg.className = "bk-geo" + (r.in_area ? "" : " bad");
      msg.textContent = r.in_area ? "Found · " + (r.county ? r.county + " County · " : "") + "in the service area" + (r.message ? " · " + r.message : "") : (r.message || "That address is outside the service area.") + (r.county ? " (" + r.county + ")" : "");
      loadBookSlots(); estimateSoon();
    }).catch(function(e){ $("bk-find").disabled = false; BK.geo = null; msg.className = "bk-geo bad"; msg.textContent = e.message || "Couldn't look that up."; });
  }
  $("bk-find").addEventListener("click", geocode);
  $("bk-address").addEventListener("keydown", function(e){ if(e.key === "Enter"){ e.preventDefault(); geocode(); } });
  $("bk-address").addEventListener("input", function(){ BK.geo = null; $("bk-geo").hidden = true; });

  function fillSlots(sel, date, lat, lng){
    clear(sel); sel.appendChild(el("option", null, "Loading windows…")); sel.firstChild.value = "";
    if(!date){ clear(sel); sel.appendChild(el("option", null, "Pick a date first")); sel.firstChild.value = ""; return Promise.resolve(); }
    return api("slots", {date: date, lat: lat == null ? null : lat, lng: lng == null ? null : lng}).then(function(r){
      clear(sel); var list = r.slots || [], first = null;
      if(!list.length){ sel.appendChild(el("option", null, "No windows that day")); sel.firstChild.value = ""; return; }
      var ph = el("option", null, "Pick a window"); ph.value = ""; sel.appendChild(ph);
      list.forEach(function(s){ var o = el("option", null, (s.label || s.slot || "") + (s.available === false && s.reason ? " · " + s.reason : s.available === false ? " · unavailable" : "")); o.value = s.slot || ""; o.disabled = s.available === false; if(!o.disabled && !first) first = o; sel.appendChild(o); });
      if(first) first.selected = true;
    }).catch(function(e){ clear(sel); sel.appendChild(el("option", null, e.message || "Couldn't load windows")); sel.firstChild.value = ""; });
  }
  function loadBookSlots(){ return fillSlots($("bk-slot"), $("bk-date").value, BK.geo ? BK.geo.lat : null, BK.geo ? BK.geo.lng : null); }
  $("bk-date").addEventListener("change", function(){ loadBookSlots(); estimateSoon(); });

  $("bk-pay").addEventListener("click", function(e){ var b = e.target.closest("button[data-v]"); if(!b) return; BK.pay = b.dataset.v; setTab("bk-pay", "v", BK.pay); });
  $("bk-hauler").addEventListener("click", function(e){ var b = e.target.closest("button[data-v]"); if(!b) return; BK.hauler = b.dataset.v; setTab("bk-hauler", "v", BK.hauler); $("bk-hauler-sel").hidden = BK.hauler !== "assign"; if(BK.hauler === "assign") refreshHaulerSelect(); });
  function refreshHaulerSelect(){
    var sel = $("bk-hauler-sel"), keep = sel.value; clear(sel);
    var live = (DATA && DATA.haulers || []).filter(function(h){ return haulerState(h) !== "offline"; });
    live.sort(function(a, b){ var o = {live: 0, online: 1, standby: 2}; return o[haulerState(a)] - o[haulerState(b)]; });
    var ph = el("option", null, live.length ? "Pick a hauler" : "Nobody is on right now"); ph.value = ""; sel.appendChild(ph);
    live.forEach(function(h){ var o = el("option", null, (h.name || "Hauler") + " · " + stateText(h) + (h.county ? " · " + h.county : "")); o.value = h.id; if(String(h.id) === keep) o.selected = true; sel.appendChild(o); });
  }

  $("bk-form").addEventListener("submit", function(ev){
    ev.preventDefault(); var err = $("bk-err"); err.hidden = true;
    function bad(m){ err.textContent = m; err.hidden = false; toast(m, "bad"); }
    var phone = digits($("bk-phone").value), name = $("bk-name").value.trim(), items = bookItems();
    if(phone.length !== 10) return bad("The phone needs 10 digits.");
    if(!name) return bad("Who is the customer?");
    if(!$("bk-address").value.trim()) return bad("Add the pickup address.");
    if(!BK.geo) return bad("Tap Find so we can place the address.");
    if(!BK.geo.in_area) return bad("That address is outside the service area — we can't book it.");
    if(!items.length) return bad("Add at least one item or a truck load.");
    if(!$("bk-date").value) return bad("Pick a date.");
    if(!$("bk-slot").value) return bad("Pick an arrival window.");
    if(BK.hauler === "assign" && !$("bk-hauler-sel").value) return bad("Pick the hauler to assign, or leave it open.");
    var payload = {name: name, phone: phone, email: $("bk-email").value.trim() || null, address: $("bk-address").value.trim(), lat: BK.geo.lat, lng: BK.geo.lng,
      items: items, addons: bookAddons(), scheduled_date: $("bk-date").value, scheduled_time: $("bk-slot").value, notes: $("bk-notes").value.trim(),
      payment: BK.pay, send_text: $("bk-sendtext").checked};
    if(BK.hauler === "assign") payload.contractor_id = $("bk-hauler-sel").value;
    if(BK.hauler === "broadcast") payload.broadcast = true;
    var sb = $("bk-submit"); sb.disabled = true;
    api("book", payload).then(function(r){
      sb.disabled = false; toast(r.message || ("Booked " + (r.job && r.job.code ? r.job.code : "")), "good"); closeBook();
      return load().then(function(){ if(r.job && r.job.id != null) openJob(r.job.id); });
    }).catch(function(e){ sb.disabled = false; bad(e.message || "Couldn't book that."); });
  });

  // ---------------------------------------------------------------- boot
  if(ls(JWT_KEY) || ls(KEY)) load(); else showGate();
})();
