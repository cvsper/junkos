/* Dispatch desk — map first. Renders /api/va/dispatch/overview onto a Leaflet
   map (tiles from our own backend), a floating card for the selected job, a
   bottom dock (selection + capacity + open + today) and slide-over panels for
   the board, the roster, recent activity and a new booking. Opens a drawer for
   any job or hauler. Every route is POST JSON under /api/va/dispatch/.
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
  // great-circle miles between two points (client-side "nearest" hints only)
  function haversine(lat1, lng1, lat2, lng2){
    var r = Math.PI / 180, dLat = (lat2 - lat1) * r, dLng = (lng2 - lng1) * r;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 3958.8 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }
  var PHONE_MQ = window.matchMedia("(max-width:959px)");
  function isPhone(){ return PHONE_MQ.matches; }

  // Authored glyphs only — never a server string. Stroke icons, 24-box.
  var ICON = {
    map: '<path d="M9 18l-6 3V6l6-3 6 3 6-3v15l-6 3-6-3z"/><path d="M9 3v15M15 6v15"/>',
    board: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16M15 4v16"/>',
    truck: '<path d="M2 7h11v9H2zM13 10h4l3 3v3h-7z"/><circle cx="6" cy="17.5" r="1.8"/><circle cx="16.5" cy="17.5" r="1.8"/>',
    activity: '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
    target: '<circle cx="12" cy="12" r="6"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
    dump: '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/><path d="M10 11v6M14 11v6"/>'
  };
  function svgIcon(name, cls){ var s = el("span", "dm-ico" + (cls ? " " + cls : "")); s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ICON[name] || "") + "</svg>"; return s; }
  Array.prototype.forEach.call(document.querySelectorAll("i[data-ico]"), function(i){ i.parentNode.replaceChild(svgIcon(i.dataset.ico), i); });
  (function(){
    var top = $("dm-top"); if(!top) return;
    var m = el("button", "dm-menu"); m.type = "button"; m.setAttribute("aria-label", "Menu");
    m.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>';
    m.addEventListener("click", function(){ document.body.classList.add("sh-open"); });
    top.insertBefore(m, top.firstChild);
    var dock = $("dm-dock"); if(!dock) return;
    var h = el("button", "dm-handle"); h.type = "button"; h.setAttribute("aria-label", "Expand");
    h.addEventListener("click", function(){ dock.classList.toggle("is-up"); document.body.classList.toggle("dm-dock-up", dock.classList.contains("is-up")); });
    dock.insertBefore(h, dock.firstChild);
    window.__dockUp = function(v){ dock.classList.toggle("is-up", !!v); document.body.classList.toggle("dm-dock-up", !!v); };
  })();

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
  var DATA = null, CATALOG = null, BOARD_TAB = "open", ROSTER_FILTER = "live", SEL_HAULER = null, SEL_JOB = null, refreshTimer = null, loadedOnce = false;
  var SEL_DUMP = null, DUMP_FILTER = "all", DUMP_RANK = {}, DUMPS_ON = true;
  try { DUMPS_ON = localStorage.getItem("umuve_dispatch_dumps") !== "0"; } catch(e){}

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
    $("dm-refresh").classList.add("is-busy");
    return api("overview", {}).then(function(d){
      DATA = d || {}; DATA.counts = DATA.counts || {}; DATA.jobs = DATA.jobs || {}; DATA.haulers = DATA.haulers || [];
      if(!loadedOnce){
        showTool(); loadedOnce = true;
        // the universal New booking button lands here with ?book=1
        if(/[?&]book=1/.test(location.search)){ setTimeout(openBook, 150); try { history.replaceState(null, "", location.pathname); } catch(e){} }
      }
      $("bar-sub").textContent = (DATA.va || vaName() || "") + " · updated " + new Date().toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
      if(SEL_JOB != null && !findJob(SEL_JOB)) SEL_JOB = null;
      if(SEL_DUMP != null && !findDump(SEL_DUMP)) SEL_DUMP = null;
      renderTop(); renderMap(); renderDock(false); renderFloatCard(); renderRoster(); renderBoard(); renderRecent(); renderDumps(); refreshHaulerSelect();
      schedule();
    }).catch(function(e){ if(e && e.status === 401){ clearTimeout(refreshTimer); return; } if(!loadedOnce) showGate(e.message); else fail(e); schedule(); })
      .then(function(){ $("dm-refresh").classList.remove("is-busy"); });
  }
  function schedule(){ clearTimeout(refreshTimer); refreshTimer = setTimeout(function(){ if(!document.hidden) load(); else schedule(); }, REFRESH_MS); }
  document.addEventListener("visibilitychange", function(){ if(!document.hidden && loadedOnce) load(); });
  $("dm-refresh").addEventListener("click", function(){ if(loadedOnce) load(); });

  // ---------------------------------------------------------------- helpers over the data
  function allJobs(){
    var out = [], J = DATA.jobs || {};
    ["open", "scheduled", "active", "done", "cancelled"].forEach(function(g){ (J[g] || []).forEach(function(j){ out.push({job: j, group: g}); }); });
    return out;
  }
  function findJob(id){ var hit = null; allJobs().forEach(function(x){ if(String(x.job.id) === String(id)) hit = x; }); return hit; }
  function findHauler(id){ var hit = null; (DATA.haulers || []).forEach(function(h){ if(String(h.id) === String(id)) hit = h; }); return hit; }
  function findDump(id){ var hit = null; (DATA.dumps || []).forEach(function(f){ if(String(f.id) === String(id)) hit = f; }); return hit; }
  function groupOf(status){
    if(status === "cancelled") return "cancelled"; if(status === "completed") return "done";
    if(status === "en_route" || status === "arrived" || status === "started") return "active";
    if(status === "assigned" || status === "accepted" || status === "confirmed") return "scheduled";
    return "open";
  }
  function groupTag(group){ return group === "open" ? "accent" : group === "active" ? "info" : group === "done" ? "ok" : group === "cancelled" ? "danger" : "dark"; }
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
  // how far along a job is, for the ring on the floating card
  function progressOf(status){ var m = {pending: 20, confirmed: 20, broadcasting: 20, assigned: 40, accepted: 40, en_route: 60, arrived: 80, started: 90, completed: 100, cancelled: 0}; return m[status] != null ? m[status] : 20; }
  function itemsText(j){
    var items = j.items || [], names = items.slice(0, 3).map(function(i){ return (i.qty > 1 ? i.qty + "× " : "") + (i.name || ""); });
    return names.length ? names.join(", ") + (items.length > 3 ? " +" + (items.length - 3) : "") : (j.items_text || (j.item_count ? j.item_count + " items" : "No items listed"));
  }
  function upcoming(n){
    var list = allJobs().filter(function(x){ return x.group === "open" || x.group === "scheduled" || x.group === "active"; });
    list.sort(function(a, b){ var ha = num(a.job.hours_out), hb = num(b.job.hours_out); return (ha == null ? 1e9 : ha) - (hb == null ? 1e9 : hb); });
    return n ? list.slice(0, n) : list;
  }

  // ---------------------------------------------------------------- top row
  function renderTop(){
    var c = DATA.counts || {}, J = DATA.jobs || {};
    var open = c.open != null ? c.open : (J.open || []).length, live = c.live != null ? c.live : DATA.haulers.filter(function(h){ return h.live; }).length;
    var bb = $("dm-b-board"); bb.textContent = String(open); bb.hidden = !open;
    var bh = $("dm-b-haulers"); bh.textContent = String(live); bh.hidden = !live;
    $("dm-avatar").textContent = ((String(DATA.va || vaName() || "").trim().charAt(0)) || "U").toUpperCase();
  }

  // ---------------------------------------------------------------- map (Leaflet, tiles from our backend)
  var MAP = null, AREA_LAYER = null, MARK_LAYER = null, MARKS = {haulers: {}, jobs: {}, dumps: {}}, FITTED = false;
  function ensureMap(){
    if(MAP) return MAP;
    if(typeof L === "undefined"){ $("dp-map-note").textContent = "The map library didn't load."; return null; }
    MAP = L.map("dp-map", {zoomControl: false, minZoom: 7, maxZoom: 17, attributionControl: true, zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false});
    L.tileLayer("/api/va/dispatch/tile/{z}/{x}/{y}.png", {minZoom: 7, maxZoom: 17, attribution: "© OpenStreetMap contributors"}).addTo(MAP);
    MAP.attributionControl.setPrefix(false);
    MARK_LAYER = L.layerGroup().addTo(MAP);
    MAP.on("click", function(){ if(SEL_JOB != null || SEL_HAULER != null) clearSelection(); });
    var bump = debounce(function(){ if(MAP) MAP.invalidateSize(); }, 120);
    window.addEventListener("resize", bump);
    if(window.ResizeObserver){ new ResizeObserver(bump).observe($("dp-map")); }
    return MAP;
  }
  function fitOpts(){ return isPhone() ? {paddingTopLeft: [24, 64], paddingBottomRight: [24, 24], maxZoom: 14} : {paddingTopLeft: [40, 96], paddingBottomRight: [40, 270], maxZoom: 14}; }
  function positioned(){
    var haulers = DATA.haulers.filter(function(h){ return haulerState(h) !== "offline" && num(h.lat) != null && num(h.lng) != null; });
    var jobs = allJobs().filter(function(x){ return (x.group === "open" || x.group === "scheduled" || x.group === "active") && num(x.job.lat) != null && num(x.job.lng) != null; });
    return {haulers: haulers, jobs: jobs};
  }
  function recenter(animate){
    var map = ensureMap(); if(!map) return;
    var b = DATA.area && DATA.area.bounds, p = positioned(), pts = [];
    p.haulers.forEach(function(h){ pts.push([+h.lat, +h.lng]); }); p.jobs.forEach(function(x){ pts.push([+x.job.lat, +x.job.lng]); });
    var hasBounds = b && num(b.north) != null && num(b.south) != null && num(b.east) != null && num(b.west) != null;
    if(hasBounds) map.fitBounds([[+b.south, +b.west], [+b.north, +b.east]], {animate: false, padding: [20, 20]});
    if(pts.length){ var o = fitOpts(); o.animate = !!animate; map.fitBounds(L.latLngBounds(pts), o); }
    else if(!hasBounds) map.setView([26.6, -80.2], 8);
  }
  $("dm-recenter").addEventListener("click", function(){ if(DATA) recenter(true); });
  function tipEl(lines){ var t = el("div", "dm-tip-in"); lines.filter(Boolean).forEach(function(s, i){ t.appendChild(el(i ? "span" : "b", null, s)); }); return t; }
  function haulerIcon(h, st, dx, dy){
    var w = el("div", "dm-mk " + st); w.appendChild(svgIcon("truck"));
    return L.divIcon({className: "dm-mkwrap" + (SEL_HAULER != null && String(h.id) === String(SEL_HAULER) ? " is-sel" : ""), html: w, iconSize: [28, 28], iconAnchor: [14 - dx, 14 - dy]});
  }
  function jobIcon(x){
    var w = el("div", "dm-pin " + x.group); w.appendChild(el("i"));
    return L.divIcon({className: "dm-mkwrap" + (SEL_JOB != null && String(x.job.id) === String(SEL_JOB) ? " is-sel" : ""), html: w, iconSize: [32, 32], iconAnchor: [16, 16]});
  }
  function renderMap(){
    var map = ensureMap(); if(!map) return;
    var area = DATA.area || {}, poly = (area.polygon || []).filter(function(p){ return p && num(p[0]) != null && num(p[1]) != null; });
    var p = positioned(), haulers = p.haulers, jobs = p.jobs;
    if(AREA_LAYER){ map.removeLayer(AREA_LAYER); AREA_LAYER = null; }
    if(poly.length > 2){
      AREA_LAYER = L.polygon(poly.map(function(q){ return [+q[0], +q[1]]; }), {color: "#26272C", weight: 1, opacity: .35, fillOpacity: .04, interactive: false}).addTo(map);
    }
    MARK_LAYER.clearLayers(); MARKS = {haulers: {}, jobs: {}, dumps: {}};
    jobs.forEach(function(x){
      var j = x.job, m = L.marker([+j.lat, +j.lng], {icon: jobIcon(x), keyboard: true, zIndexOffset: x.group === "open" ? 300 : 200});
      m.bindTooltip(tipEl([(j.code || "Job") + " · " + (j.status_label || j.status || ""), j.scheduled_human ? j.scheduled_human + (j.window ? " · " + j.window : "") : "", j.address || ""]), {direction: "top", offset: [0, -14], opacity: 1, className: "dm-tip"});
      m.on("click", function(){ selectJob(j.id); });
      m.addTo(MARK_LAYER); MARKS.jobs[String(j.id)] = m;
    });
    var seen = {};
    haulers.forEach(function(h){
      var st = haulerState(h), key = (+h.lat).toFixed(3) + "," + (+h.lng).toFixed(3), n = (seen[key] = (seen[key] || 0) + 1) - 1;
      var ang = n * 2.399963, rad = n ? 18 + 10 * Math.floor(Math.sqrt(n)) : 0;   // sunflower spread for trucks sharing a spot (screen px)
      var dx = rad * Math.cos(ang), dy = rad * Math.sin(ang);
      var m = L.marker([+h.lat, +h.lng], {icon: haulerIcon(h, st, dx, dy), keyboard: true, zIndexOffset: 100});
      m.bindTooltip(tipEl([h.name || "Hauler", stateText(h) + (h.tier_label ? " · " + h.tier_label : ""), [h.county, h.truck_type].filter(Boolean).join(" · ")]), {direction: "top", offset: [dx, dy - 12], opacity: 1, className: "dm-tip"});
      m.on("click", function(){ selectHauler(h.id, true); });
      m.addTo(MARK_LAYER); MARKS.haulers[String(h.id)] = m;
    });
    var dumps = DUMPS_ON ? (DATA.dumps || []).filter(function(f){ return num(f.lat) != null && num(f.lng) != null; }) : [];
    var best = SEL_JOB != null && DUMP_RANK[String(SEL_JOB)] ? bestDump(DUMP_RANK[String(SEL_JOB)]) : null;
    dumps.forEach(function(f){
      var m = L.marker([+f.lat, +f.lng], {icon: dumpIcon(f, best && String(best.id) === String(f.id)), keyboard: true, zIndexOffset: 50});
      m.bindTooltip(tipEl([f.name, dumpStatus(f), [f.type_label, f.county_label].filter(Boolean).join(" · ")]), {direction: "top", offset: [0, -12], opacity: 1, className: "dm-tip"});
      m.on("click", function(){ selectDump(f.id, false); });
      m.addTo(MARK_LAYER); MARKS.dumps[String(f.id)] = m;
    });
    $("dp-map-note").textContent = haulers.length + (haulers.length === 1 ? " hauler" : " haulers") + " on the map · " + jobs.length + (jobs.length === 1 ? " job" : " jobs") + (dumps.length ? " · " + dumps.length + " dump sites" : "");
    // the shell re-mounts the page right after first paint, so size and fit on the next tick
    setTimeout(function(){ map.invalidateSize({animate: false}); if(!FITTED){ FITTED = true; recenter(false); } }, 80);
  }
  function paintSelection(){
    function paint(set, sel){ Object.keys(set).forEach(function(k){ var m = set[k], e = m.getElement(), on = sel != null && k === String(sel); if(e) e.classList.toggle("is-sel", on); m.setZIndexOffset(on ? 1000 : (set === MARKS.haulers ? 100 : 200)); }); }
    paint(MARKS.haulers, SEL_HAULER); paint(MARKS.jobs, SEL_JOB); paint(MARKS.dumps, SEL_DUMP);
  }
  function revealMarker(m){ if(!m || !MAP) return; var ll = m.getLatLng(); if(!MAP.getBounds().pad(-.15).contains(ll)) MAP.panTo(ll); }
  function selectJob(id, reveal){
    if(window.innerWidth < 960 && window.__dockUp) window.__dockUp(true);
    SEL_JOB = id; SEL_HAULER = null; SEL_DUMP = null;
    paintSelection(); renderFloatCard(); renderDock(true);
    Array.prototype.forEach.call(document.querySelectorAll(".dp-hr"), function(r){ r.classList.remove("is-sel"); });
    if(reveal) revealMarker(MARKS.jobs[String(id)]);
    rankDumpsFor(id); if(PANEL === "dumps") renderDumps();
  }
  function selectHauler(id, scroll){
    if(window.innerWidth < 960 && window.__dockUp) window.__dockUp(true);
    SEL_HAULER = id; SEL_JOB = null; SEL_DUMP = null;
    paintSelection(); renderFloatCard(); renderDock(true);
    var row = null;
    Array.prototype.forEach.call(document.querySelectorAll(".dp-hr"), function(r){ var on = String(r.dataset.id) === String(id); r.classList.toggle("is-sel", on); if(on) row = r; });
    if(!row && scroll){
      // the hauler is filtered out of the roster: widen the filter so the row exists
      ROSTER_FILTER = "all"; setTab("dp-roster-filter", "f", "all"); renderRoster();
      Array.prototype.forEach.call(document.querySelectorAll(".dp-hr"), function(r){ if(String(r.dataset.id) === String(id)) row = r; });
    }
    if(row && scroll && PANEL === "haulers"){ row.scrollIntoView({block: "nearest", behavior: "smooth"}); }
    if(!scroll) revealMarker(MARKS.haulers[String(id)]);
  }
  function clearSelection(){
    SEL_JOB = null; SEL_HAULER = null; SEL_DUMP = null; paintSelection(); renderFloatCard(); renderDock(true);
    Array.prototype.forEach.call(document.querySelectorAll(".dp-hr"), function(r){ r.classList.remove("is-sel"); });
  }
  function setTab(wrapId, attr, val){ Array.prototype.forEach.call($(wrapId).querySelectorAll("button"), function(b){ b.classList.toggle("on", b.dataset[attr] === val); }); }

  // ---------------------------------------------------------------- floating job card
  function ring(pct, cls, size){
    size = size || 44; var r = (size - 6) / 2, c = 2 * Math.PI * r;
    var s = svgEl("svg"); s.setAttribute("viewBox", "0 0 " + size + " " + size); s.setAttribute("class", "dm-ring " + (cls || "")); s.setAttribute("aria-hidden", "true");
    var t = svgEl("circle"); t.setAttribute("cx", size / 2); t.setAttribute("cy", size / 2); t.setAttribute("r", r); t.setAttribute("class", "track"); s.appendChild(t);
    var f = svgEl("circle"); f.setAttribute("cx", size / 2); f.setAttribute("cy", size / 2); f.setAttribute("r", r); f.setAttribute("class", "fill");
    f.setAttribute("stroke-dasharray", c.toFixed(2)); f.setAttribute("stroke-dashoffset", (c * (1 - Math.max(0, Math.min(100, pct)) / 100)).toFixed(2)); f.setAttribute("transform", "rotate(-90 " + size / 2 + " " + size / 2 + ")"); s.appendChild(f);
    var x = svgEl("text"); x.setAttribute("x", size / 2); x.setAttribute("y", size / 2); x.setAttribute("class", "pct"); x.setAttribute("text-anchor", "middle"); x.setAttribute("dominant-baseline", "central"); x.textContent = Math.round(pct) + "%"; s.appendChild(x);
    return s;
  }
  function renderFloatCard(){
    var box = $("dm-card"); clear(box);
    if(SEL_DUMP != null){ var f = findDump(SEL_DUMP); if(f){ box.hidden = false; renderDumpCard(box, f); return; } }
    var hit = SEL_JOB != null ? findJob(SEL_JOB) : null;
    if(!hit){ box.hidden = true; return; }
    box.hidden = false;
    var j = hit.job, g = hit.group;
    var head = el("div", "dm-card-h"); head.appendChild(el("span", "code", j.code || "—")); head.appendChild(el("span", "dp-tag " + groupTag(g), j.status_label || j.status || g));
    head.appendChild(btn("dp-x sm", "×", clearSelection)); box.appendChild(head);
    var ad = el("div", "addr", j.address || "No address"); if(j.county) ad.appendChild(el("span", null, " · " + j.county)); box.appendChild(ad);
    var pr = el("div", "dm-prog"); pr.appendChild(ring(progressOf(j.status), g));
    var pt = el("div", "t"); pt.appendChild(el("b", null, (j.scheduled_human || "No time set") + (j.window ? " · " + j.window : "")));
    var hh = g === "done" || g === "cancelled" ? null : hoursHint(j.hours_out);
    pt.appendChild(el("span", "hint " + (hh ? hh.cls : ""), hh ? hh.text : (j.hauler ? "with " + j.hauler.name : "nobody on it yet"))); pr.appendChild(pt); box.appendChild(pr);

    var nx = el("div", "dm-next");
    if(j.hauler && j.hauler.id != null){
      nx.appendChild(el("h5", null, "Next for " + (String(j.hauler.name || "the hauler").split(" ")[0])));
      var others = allJobs().filter(function(x){ return x.job.hauler && String(x.job.hauler.id) === String(j.hauler.id) && String(x.job.id) !== String(j.id) && x.group !== "cancelled"; });
      others.sort(function(a, b){ return (num(a.job.hours_out) == null ? 1e9 : a.job.hours_out) - (num(b.job.hours_out) == null ? 1e9 : b.job.hours_out); });
      if(!others.length) nx.appendChild(el("p", "dp-empty", "Nothing else on the plate today."));
      others.slice(0, 3).forEach(function(x){
        var r = btn("dm-next-row", null, function(){ selectJob(x.job.id, true); });
        r.appendChild(el("span", "t", x.job.scheduled_human || when(x.job.scheduled_at) || "—")); r.appendChild(el("span", "w", (x.job.code || "") + (x.job.county ? " · " + x.job.county : "")));
        r.appendChild(el("span", "dp-tag " + groupTag(x.group), x.job.status_label || x.job.status || "")); nx.appendChild(r);
      });
    } else {
      nx.appendChild(el("h5", null, "Nearest live trucks"));
      var near = [];
      if(num(j.lat) != null && num(j.lng) != null) DATA.haulers.forEach(function(h){ if(h.live && num(h.lat) != null && num(h.lng) != null) near.push({h: h, d: haversine(+j.lat, +j.lng, +h.lat, +h.lng)}); });
      near.sort(function(a, b){ return a.d - b.d; });
      if(!near.length) nx.appendChild(el("p", "dp-empty", num(j.lat) == null ? "This job has no pin yet." : "No live trucks with a position right now."));
      near.slice(0, 2).forEach(function(x){
        var r = btn("dm-next-row", null, function(){ selectHauler(x.h.id, false); });
        r.appendChild(el("span", "t", x.d.toFixed(1) + " mi")); var w = el("span", "w", x.h.name || "Hauler"); if(x.h.tier_label) w.appendChild(el("span", "dp-tag", x.h.tier_label)); r.appendChild(w);
        r.appendChild(el("span", "dm-mini", (num(x.h.jobs_today) || 0) + " today")); nx.appendChild(r);
      });
    }
    box.appendChild(nx);
    var bd = bestDumpRow(j); if(bd) box.appendChild(bd);
    var foot = el("div", "dp-actions"); foot.appendChild(btn("pill dark", "Open", function(){ openJob(j.id); }));
    if(g === "open" || g === "scheduled") foot.appendChild(btn("pill", g === "open" ? "Find a hauler" : "Reassign", function(){ openJob(j.id, "candidates"); }));
    box.appendChild(foot);
  }

  // ---------------------------------------------------------------- bottom dock
  function label(text){ return el("div", "dm-label", text); }
  function big(v, dim){ var b = el("b", "dm-big" + (v == null || dim ? " dim" : ""), v == null ? "–" : String(v)); return b; }
  function facts(pairs){ var dl = el("dl", "dm-facts"); pairs.forEach(function(p){ if(p[1] == null || p[1] === "") return; dl.appendChild(el("dt", null, p[0])); var dd = el("dd"); if(p[1] instanceof Node) dd.appendChild(p[1]); else dd.textContent = String(p[1]); dl.appendChild(dd); }); return dl; }
  function renderDock(force){
    var c = DATA.counts || {}, cap = DATA.capacity, J = DATA.jobs || {};
    var sel = $("dm-sel");
    if(force || !sel.querySelector(".dp-inline")){
      clear(sel);
      var jh = SEL_JOB != null ? findJob(SEL_JOB) : null, hh = SEL_HAULER != null ? findHauler(SEL_HAULER) : null;
      var dh = SEL_DUMP != null ? findDump(SEL_DUMP) : null;
      if(dh) dockDump(sel, dh); else if(jh) dockJob(sel, jh.job, jh.group); else if(hh) dockHauler(sel, hh); else dockIdle(sel);
    }
    // capacity
    var cp = $("dm-cap"); clear(cp);
    var live = num(c.live), online = num(c.online), standby = num(c.standby), lvl = cap && String(cap.level || "").toLowerCase();
    var lc = lvl === "green" || lvl === "ok" || lvl === "good" ? "ok" : lvl === "amber" || lvl === "yellow" || lvl === "tight" ? "warn" : lvl === "red" || lvl === "bad" || lvl === "none" ? "danger" : "";
    cp.appendChild(label("Capacity"));
    var cr = el("div", "dm-cap-row"); var cl = el("div"); cl.appendChild(big(live)); cl.appendChild(el("div", "dm-sub", [online != null ? online + " online" : null, standby != null ? standby + " standby" : null].filter(Boolean).join(" · ") || "live trucks")); cr.appendChild(cl);
    var unconf = cap && num(cap.unconfirmed) != null ? cap.unconfirmed : Math.max(0, (online || 0) - (live || 0));
    var total = (live || 0) + unconf, frac = total ? (live || 0) / total : 0;
    cr.appendChild(gauge(frac, lc)); cp.appendChild(cr);
    cp.appendChild(el("div", "dm-note " + lc, cap ? (cap.note || (cap.count != null ? cap.count + (cap.count === 1 ? " truck" : " trucks") + (unconf ? " · " + unconf + " unconfirmed" : "") : "")) : "no capacity read yet"));
    // needs a hauler
    var op = $("dm-open"); clear(op);
    op.appendChild(label("Needs a hauler"));
    op.appendChild(big(c.open)); op.appendChild(el("div", "dm-sub", (c.scheduled != null ? c.scheduled + " scheduled" : "") + (c.active != null ? (c.scheduled != null ? " · " : "") + c.active + " in progress" : "")));
    op.appendChild(dots(J.open || []));
    // today
    var td = $("dm-today"); clear(td);
    td.appendChild(label("Today"));
    var tr = el("div", "dm-today-row"); var tl = el("div"); tl.appendChild(big(c.done_today)); tl.appendChild(el("div", "dm-sub", "done · " + (c.cancelled_today != null ? c.cancelled_today : 0) + " cancelled")); tr.appendChild(tl); td.appendChild(tr);
    td.appendChild(breakdown([
      {k: "open", name: "Needs a hauler", v: num(c.open) || 0},
      {k: "scheduled", name: "Scheduled", v: num(c.scheduled) || 0},
      {k: "active", name: "In progress", v: num(c.active) || 0},
      {k: "done", name: "Done today", v: num(c.done_today) || 0}
    ]));
  }
  function gauge(frac, cls){
    var W = 96, H = 54, r = 40, cx = 48, cy = 48, C = Math.PI * r;
    var s = svgEl("svg"); s.setAttribute("viewBox", "0 0 " + W + " " + H); s.setAttribute("class", "dm-gauge " + (cls || "")); s.setAttribute("aria-hidden", "true");
    var d = "M " + (cx - r) + " " + cy + " A " + r + " " + r + " 0 0 1 " + (cx + r) + " " + cy;
    var t = svgEl("path"); t.setAttribute("d", d); t.setAttribute("class", "track"); s.appendChild(t);
    var f = svgEl("path"); f.setAttribute("d", d); f.setAttribute("class", "fill"); f.setAttribute("stroke-dasharray", C.toFixed(2)); f.setAttribute("stroke-dashoffset", (C * (1 - Math.max(0, Math.min(1, frac)))).toFixed(2)); s.appendChild(f);
    var x = svgEl("text"); x.setAttribute("x", cx); x.setAttribute("y", cy - 4); x.setAttribute("class", "pct"); x.setAttribute("text-anchor", "middle"); x.textContent = Math.round(frac * 100) + "%"; s.appendChild(x);
    return s;
  }
  // the next open jobs as dots on a 24h track; late ones pile up at the left in the accent
  function dots(list){
    var w = el("div", "dm-dots"); var track = el("div", "track");
    list.slice().sort(function(a, b){ return (num(a.hours_out) == null ? 1e9 : a.hours_out) - (num(b.hours_out) == null ? 1e9 : b.hours_out); }).slice(0, 14).forEach(function(j){
      var h = num(j.hours_out); if(h == null) return;
      var d = btn("dot" + (h < 0 ? " late" : h < 2 ? " soon" : ""), null, function(){ selectJob(j.id, true); });
      d.style.setProperty("--x", (Math.max(0, Math.min(24, h)) / 24 * 100).toFixed(1) + "%");   // CSSOM, not a style attribute: fine under style-src 'self'
      d.title = (j.code || "Job") + " · " + (j.scheduled_human || "") + (h < 0 ? " · late" : ""); d.setAttribute("aria-label", d.title);
      track.appendChild(d);
    });
    w.appendChild(track);
    var ax = el("div", "axis"); ax.appendChild(el("span", null, "now")); ax.appendChild(el("span", null, "next 24h")); w.appendChild(ax);
    if(!list.length) w.classList.add("is-empty");
    return w;
  }
  function breakdown(parts){
    var total = parts.reduce(function(s, p){ return s + p.v; }, 0), w = el("div", "dm-break" + (total ? "" : " is-empty"));
    var labels = el("div", "labels"), bar = el("div", "bar"), legend = el("div", "legend");
    parts.forEach(function(p){
      var pct = total ? p.v / total * 100 : 25;
      var l = el("span", "l " + p.k, total ? Math.round(pct) + "%" : "–"); l.style.setProperty("--w", pct.toFixed(2) + "%"); labels.appendChild(l);
      var s = el("i", "s " + p.k); s.style.setProperty("--w", pct.toFixed(2) + "%"); s.title = p.name + " · " + p.v; bar.appendChild(s);
      var g = el("span", "g"); g.appendChild(el("i", "k " + p.k)); g.appendChild(document.createTextNode(p.name)); legend.appendChild(g);
    });
    w.appendChild(labels); w.appendChild(bar); w.appendChild(legend);
    return w;
  }
  function dockIdle(host){
    host.appendChild(label("Selected"));
    host.appendChild(el("p", "dm-hint", "Tap a pin or a truck on the map."));
    var list = upcoming(3);
    if(!list.length){ host.appendChild(el("p", "dp-empty", "Nothing on the board yet. Book something from the top row.")); return; }
    var rows = el("div", "dm-up"); rows.appendChild(el("h5", null, "Coming up"));
    list.forEach(function(x){
      var j = x.job, r = btn("dm-next-row", null, function(){ selectJob(j.id, true); });
      var hh = hoursHint(j.hours_out); r.appendChild(el("span", "t" + (hh ? " " + hh.cls : ""), hh ? hh.text : (j.scheduled_human || "—")));
      var w = el("span", "w", (j.code || "") + " · " + (j.address || j.county || "")); r.appendChild(w);
      r.appendChild(el("span", "dp-tag " + groupTag(x.group), j.status_label || j.status || "")); rows.appendChild(r);
    });
    host.appendChild(rows);
  }
  function dockJob(host, j, group){
    var head = el("div", "dm-sel-h"); head.appendChild(el("span", "code", j.code || "—"));
    head.appendChild(el("span", "dp-tag " + groupTag(group), j.status_label || j.status || group));
    var pi = payInfo(j.payment); head.appendChild(el("span", "dp-tag " + pi.cls, pi.text));
    if(j.confirmed) head.appendChild(el("span", "dp-tag ok", "✓ confirmed" + (j.confirmed_by ? " by " + j.confirmed_by : "")));
    var hr = el("span", "dm-sel-r"); hr.appendChild(btn("pill", "Open", function(){ openJob(j.id); })); hr.appendChild(btn("dp-x sm", "×", clearSelection)); head.appendChild(hr); host.appendChild(head);
    var whenEl = el("span", null, (j.scheduled_human || "No time set") + (j.window ? " · " + j.window : "")); var hh = group === "done" || group === "cancelled" ? null : hoursHint(j.hours_out); if(hh) whenEl.appendChild(el("span", "hint " + hh.cls, " " + hh.text));
    var cu = j.customer || {}, cust = el("span", null, (cu.name || "Customer") + " "); if(cu.phone){ cust.appendChild(telLink(cu.phone)); cust.appendChild(document.createTextNode(" ")); var s = el("a", "dp-lnk", "text"); s.href = "sms:" + telHref(cu.phone); cust.appendChild(s); } if(num(cu.prior_jobs)) cust.appendChild(el("span", "dm-mini", " · " + cu.prior_jobs + " prior"));
    var tot = el("span"); tot.appendChild(el("b", "dm-money", money(j.total))); if(num(j.disposal_fee)) tot.appendChild(el("span", "dm-mini", " incl. " + money(j.disposal_fee) + " dump fee")); if(num(j.service_fee)) tot.appendChild(el("span", "dm-mini", " · " + money(j.service_fee) + " service"));
    var who = el("span"); if(j.hauler){ who.appendChild(document.createTextNode((j.hauler.name || "") + " ")); if(j.hauler.tier_label) who.appendChild(el("span", "dp-tag", j.hauler.tier_label)); if(j.hauler.phone){ who.appendChild(document.createTextNode(" ")); who.appendChild(telLink(j.hauler.phone)); } } else who.appendChild(el("span", "none", group === "open" ? "No hauler yet" : "—"));
    host.appendChild(facts([["When", whenEl], ["Customer", cust], ["Items", itemsText(j)], ["Total", tot], ["Hauler", who], ["Address", (j.address || "No address") + (j.county ? " · " + j.county : "")], ["Confirmed", j.confirmed ? "yes" + (j.confirmed_at ? " · " + when(j.confirmed_at) : "") : (group === "scheduled" ? "not yet" : null)]]));
    if(group !== "done" && group !== "cancelled"){ var acts = actions(j, group, host); if(acts) host.appendChild(acts); }
  }
  function dockDump(host, f){
    var head = el("div", "dm-sel-h"); head.appendChild(el("span", "code", f.name || "Dump site")); if(f.type_label) head.appendChild(el("span", "dp-tag", f.type_label)); if(!f.walk_in) head.appendChild(el("span", "dp-tag warn", f.access_label || "restricted"));
    var st = el("span", "dm-state " + (f.open_now ? "live" : "offline")); st.appendChild(el("i", "dp-dot " + (f.open_now ? "live" : "offline"))); st.appendChild(document.createTextNode(dumpStatus(f))); head.appendChild(st);
    var hr = el("span", "dm-sel-r"); hr.appendChild(btn("dp-x sm", "×", clearSelection)); head.appendChild(hr); host.appendChild(head);
    var jh = SEL_JOB != null ? findJob(SEL_JOB) : null, rank = SEL_JOB != null ? DUMP_RANK[String(SEL_JOB)] : null, mine = null;
    if(rank && !rank.pending) (rank.ranked || []).forEach(function(r){ if(String(r.id) === String(f.id)) mine = r; });
    var fee = (f.fees || []).slice(0, 4).map(function(x){ return x.label + " " + money(x.amount); }).join(" · ");
    host.appendChild(facts([["Address", f.address], ["Phone", f.phone ? contactLinks(f.phone) : null], ["Hours", hoursText(f.hours)],
      ["Per ton", fee || (f.accepts && f.accepts.length ? "quote at the scale" : null)],
      ["This job", mine && jh ? (mine.eligible ? [num(mine.miles) != null ? Number(mine.miles).toFixed(1) + " mi" : null, num(mine.est_tip) != null ? "about " + money(mine.est_tip) + " tip" : null].filter(Boolean).join(" · ") : (mine.blockers || []).join(" · ")) : null]]));
    if(f.notes) host.appendChild(el("p", "dm-note-small", f.notes));
    var row = el("div", "dp-actions");
    if(jh && jh.job.hauler && jh.job.hauler.id != null) row.appendChild(btn("pill dark", "Text to " + String(jh.job.hauler.name || "hauler").split(" ")[0], function(){ textDumpToHauler(this, jh, f); }));
    row.appendChild(btn("pill", "Center map", function(){ var m = MARKS.dumps[String(f.id)]; if(m && MAP) MAP.setView(m.getLatLng(), Math.max(MAP.getZoom(), 12)); if(window.__dockUp) window.__dockUp(false); }));
    host.appendChild(row);
  }
  function dockHauler(host, h){
    var st = haulerState(h);
    var head = el("div", "dm-sel-h"); head.appendChild(el("span", "code", h.name || "Hauler")); if(h.tier_label) head.appendChild(el("span", "dp-tag", h.tier_label)); if(h.concierge) head.appendChild(el("span", "dp-tag info", "concierge"));
    var s = el("span", "dm-state " + st); s.appendChild(el("i", "dp-dot " + st)); s.appendChild(document.createTextNode(stateText(h))); head.appendChild(s);
    var hr = el("span", "dm-sel-r"); hr.appendChild(btn("pill", "Open", function(){ openHauler(h.id); })); hr.appendChild(btn("dp-x sm", "×", clearSelection)); head.appendChild(hr); host.appendChild(head);
    host.appendChild(facts([["County", h.county], ["Truck", h.truck_type], ["Rating", num(h.rating) != null ? "★ " + Number(h.rating).toFixed(1) : null], ["Today", num(h.jobs_today) != null ? h.jobs_today + (h.jobs_today === 1 ? " job" : " jobs") : null],
      ["Done", num(h.completed) != null ? String(h.completed) + (num(h.no_shows) ? " · " + h.no_shows + " no-shows" : "") : null], ["Phone", h.phone ? contactLinks(h.phone) : "no phone"]]));
    var open = (DATA.jobs && DATA.jobs.open) || [], row = el("div", "dp-actions dm-assign");
    if(open.length){
      var sel = el("select"); var ph = el("option", null, "Assign to…"); ph.value = ""; sel.appendChild(ph);
      open.forEach(function(j){ var o = el("option", null, (j.code || "Job") + " · " + (j.scheduled_human || "unscheduled") + " · " + (j.county || j.address || "")); o.value = j.id; sel.appendChild(o); });
      row.appendChild(sel);
      var why = el("p", "dp-empty"); why.hidden = true;
      var ab = btn("pill dark", "Assign", function(){ if(!sel.value){ toast("Pick a job first.", "bad"); return; } doAssign(sel.value, h.id, false, ab, why, function(){ selectJob(sel.value, true); }); });
      row.appendChild(ab); host.appendChild(row); host.appendChild(why);
    } else { row.appendChild(el("span", "dm-mini", "Nothing needs a hauler right now.")); host.appendChild(row); }
  }

  // ---------------------------------------------------------------- roster
  var FILTER_TOUCHED = false;
  function autoFilter(){
    if(FILTER_TOUCHED || !DATA) return;
    var states = DATA.haulers.map(haulerState);
    var want = states.indexOf("live") >= 0 ? "live" : states.some(function(s){ return s !== "offline"; }) ? "online" : "all";
    if(want !== ROSTER_FILTER){ ROSTER_FILTER = want; setTab("dp-roster-filter", "f", want); }
  }
  function renderRoster(){
    autoFilter();
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
  $("dp-roster-filter").addEventListener("click", function(e){ var b = e.target.closest("button[data-f]"); if(!b) return; FILTER_TOUCHED = true; ROSTER_FILTER = b.dataset.f; setTab("dp-roster-filter", "f", ROSTER_FILTER); renderRoster(); });

  // ---------------------------------------------------------------- dump sites
  function dumpStatus(f){
    if(f.open_now) return "Open" + (f.closes_at ? " · closes " + f.closes_at : "");
    return "Closed" + (f.next_open ? " · opens " + f.next_open : "");
  }
  function dumpIcon(f, best){
    var w = el("div", "dm-dump" + (f.open_now ? "" : " closed") + (f.walk_in ? "" : " gated") + (best ? " best" : "")); w.appendChild(svgIcon("dump"));
    return L.divIcon({className: "dm-mkwrap" + (SEL_DUMP != null && String(f.id) === String(SEL_DUMP) ? " is-sel" : ""), html: w, iconSize: [26, 26], iconAnchor: [13, 13]});
  }
  function selectDump(id, scroll){
    if(window.innerWidth < 960 && window.__dockUp) window.__dockUp(true);
    SEL_DUMP = id; SEL_HAULER = null;
    paintSelection(); renderFloatCard(); renderDock(true);
    Array.prototype.forEach.call(document.querySelectorAll(".dp-hr"), function(r){ r.classList.toggle("is-sel", r.dataset.dump != null && String(r.dataset.dump) === String(id)); });
    var m = MARKS.dumps[String(id)];
    if(!m && !DUMPS_ON){ DUMPS_ON = true; $("dp-dumps-map").checked = true; try { localStorage.setItem("umuve_dispatch_dumps", "1"); } catch(e){} renderMap(); m = MARKS.dumps[String(id)]; }
    revealMarker(m);
    if(scroll && PANEL === "dumps"){ var row = document.querySelector('.dp-hr[data-dump="' + String(id).replace(/"/g, "") + '"]'); if(row) row.scrollIntoView({block: "nearest", behavior: "smooth"}); }
  }
  function hoursGroups(hours){
    var out = [];
    (hours || []).forEach(function(d){
      var txt = d.open ? d.open + "–" + d.close : "closed", last = out[out.length - 1];
      if(last && last.txt === txt){ last.to = d.day; } else out.push({from: d.day, to: d.day, txt: txt});
    });
    return out.map(function(g){ return {days: g.from === g.to ? g.from : g.from + "–" + g.to, txt: g.txt, off: g.txt === "closed"}; });
  }
  function hoursText(hours){ return hoursGroups(hours).map(function(g){ return g.days + " " + g.txt; }).join(" · ") || null; }
  function textDumpToHauler(b, jh, f){
    b.disabled = true;
    var body = "Dump for " + (jh.job.code || "your job") + ": " + f.name + ", " + (f.address || "") + ". " + dumpStatus(f) + (f.phone ? ". " + fmtPhone(f.phone) : "") + ".";
    api("job/text", {job_id: jh.job.id, to: "hauler", body: body}).then(function(){ toast("Sent to " + jh.job.hauler.name, "good"); b.disabled = false; }).catch(function(e){ fail(e); b.disabled = false; });
  }
  function bestDump(rank){ var hit = null; (rank.ranked || []).forEach(function(r){ if(!hit && r.eligible) hit = r; }); return hit; }
  function rankDumpsFor(jobId){
    var key = String(jobId); if(DUMP_RANK[key]) return;
    var hit = findJob(jobId); if(!hit || num(hit.job.lat) == null) return;
    DUMP_RANK[key] = {ranked: [], pending: true};
    api("dumps", {job_id: jobId}).then(function(d){
      DUMP_RANK[key] = d || {ranked: []};
      if(String(SEL_JOB) === key){ renderFloatCard(); if(PANEL === "dumps") renderDumps(); if(DUMPS_ON) renderMap(); }
    }).catch(function(){ delete DUMP_RANK[key]; });
  }
  function bestDumpRow(j){
    var rank = DUMP_RANK[String(j.id)]; if(!rank || rank.pending) return null;
    var b = bestDump(rank); if(!b) return null;
    var r = btn("dm-best", null, function(){ selectDump(b.id, true); });
    r.appendChild(svgIcon("dump")); var t = el("span"); t.appendChild(el("b", null, "Dump here: ")); t.appendChild(document.createTextNode(b.name)); r.appendChild(t);
    r.appendChild(el("span", "m", [num(b.miles) != null ? Number(b.miles).toFixed(1) + " mi" : null, num(b.est_tip) != null ? "~" + money(b.est_tip) + " tip" : null].filter(Boolean).join(" · ")));
    return r;
  }
  function renderDumpCard(box, f){
    var head = el("div", "dm-card-h"); head.appendChild(el("span", "code", f.name || "Dump site"));
    head.appendChild(btn("dp-x sm", "×", clearSelection)); box.appendChild(head);
    var tags = el("div", "dm-card-h");
    tags.appendChild(el("span", "dp-tag " + (f.open_now ? "ok" : ""), dumpStatus(f)));
    if(f.type_label) tags.appendChild(el("span", "dp-tag", f.type_label));
    tags.appendChild(el("span", "dp-tag " + (f.walk_in ? "" : "warn"), f.access_label || (f.walk_in ? "Walk-in" : "Restricted")));
    box.appendChild(tags);
    var fac = el("div", "dm-fac");
    function row(k, v, cls){ if(v == null || v === "") return; var r = el("div", "row"); r.appendChild(el("span", "k", k)); var vv = el("span", "v " + (cls || "")); if(v instanceof Node) vv.appendChild(v); else vv.textContent = String(v); r.appendChild(vv); fac.appendChild(r); }
    row("Address", f.address);
    if(f.phone){ var a = el("a", null, fmtPhone(f.phone)); a.href = "tel:" + f.phone; row("Phone", a); }
    row("Operator", f.operator, "faint");
    if(f.origin_county_label) row("Takes", "Loads from " + f.origin_county_label + " County only", "warn");
    var rank = SEL_JOB != null ? DUMP_RANK[String(SEL_JOB)] : null, mine = null;
    if(rank && !rank.pending) (rank.ranked || []).forEach(function(r){ if(String(r.id) === String(f.id)) mine = r; });
    var jh = SEL_JOB != null ? findJob(SEL_JOB) : null;
    if(mine && jh){
      var line = [num(mine.miles) != null ? Number(mine.miles).toFixed(1) + " mi from " + (jh.job.code || "the job") : null, num(mine.minutes) != null ? "~" + Math.round(mine.minutes) + " min" : null, num(mine.est_tip) != null ? "about " + money(mine.est_tip) + " tip" : null].filter(Boolean).join(" · ");
      row("This job", line, mine.eligible ? "ok" : "warn");
      if(!mine.eligible && mine.blockers.length) row("", mine.blockers.join(" · "), "warn");
    }
    box.appendChild(fac);
    if(f.fees && f.fees.length){
      var nx = el("div", "dm-next"); nx.appendChild(el("h5", null, "Gate fees per ton"));
      var fl = el("div", "dm-fees"); f.fees.slice(0, 8).forEach(function(x){ var d = el("div"); d.appendChild(el("span", null, x.label)); d.appendChild(el("b", null, money(x.amount))); fl.appendChild(d); }); nx.appendChild(fl); box.appendChild(nx);
    } else if(f.accepts && f.accepts.length){
      box.appendChild(el("p", "dm-note-small", "No published rates — they quote at the scale. Takes " + f.accepts.map(function(a){ return a.label; }).join(", ") + "."));
    }
    if(f.hours && f.hours.length){
      var hx = el("div", "dm-next"); hx.appendChild(el("h5", null, "Hours"));
      var hg = el("div", "dm-hours");
      hoursGroups(f.hours).forEach(function(g){ var c = el("div", g.off ? "off" : ""); c.appendChild(el("b", null, g.days)); c.appendChild(el("span", null, g.txt)); hg.appendChild(c); });
      hx.appendChild(hg); box.appendChild(hx);
    }
    if(f.notes) box.appendChild(el("p", "dm-note-small", f.notes));
    var foot = el("div", "dp-actions");
    if(jh && jh.job.hauler && jh.job.hauler.id != null){
      foot.appendChild(btn("pill dark", "Text to " + String(jh.job.hauler.name || "hauler").split(" ")[0], function(){ textDumpToHauler(this, jh, f); }));
    }
    foot.appendChild(btn("pill", "Center map", function(){ var m = MARKS.dumps[String(f.id)]; if(m && MAP) MAP.setView(m.getLatLng(), Math.max(MAP.getZoom(), 12)); }));
    box.appendChild(foot);
  }
  function renderDumps(){
    var box = $("dp-dumps"); if(!box || !DATA) return; clear(box);
    var q = ($("dp-dumps-q").value || "").trim().toLowerCase(), all = DATA.dumps || [];
    var rank = SEL_JOB != null ? DUMP_RANK[String(SEL_JOB)] : null, byId = {};
    if(rank && !rank.pending) (rank.ranked || []).forEach(function(r, i){ byId[String(r.id)] = r; r._i = i; });
    var jh = SEL_JOB != null ? findJob(SEL_JOB) : null;
    var list = all.filter(function(f){
      if(DUMP_FILTER === "open" && !f.open_now) return false;
      if(DUMP_FILTER === "walkin" && !f.walk_in) return false;
      if(q && [f.name, f.county_label, f.type_label, f.operator, f.address].concat((f.accepts || []).map(function(a){ return a.label; })).join(" ").toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
    if(rank && !rank.pending){
      list.sort(function(a, b){ var ra = byId[String(a.id)], rb = byId[String(b.id)]; return (ra ? ra._i : 1e9) - (rb ? rb._i : 1e9); });
    } else {
      list.sort(function(a, b){ if(a.open_now !== b.open_now) return a.open_now ? -1 : 1; return String(a.county_label || "").localeCompare(String(b.county_label || "")) || String(a.name).localeCompare(String(b.name)); });
    }
    $("dp-dumps-note").textContent = (jh && rank && !rank.pending ? "ranked for " + (jh.job.code || "the job") + " · " + (rank["for"] && rank["for"].category_label ? rank["for"].category_label + " · " : "") : "") + list.length + " of " + all.length;
    if(!list.length){ box.appendChild(el("p", "dp-empty", !all.length ? "No dump sites loaded yet." : DUMP_FILTER === "open" ? "Nothing is open right now. Try All." : q ? "No site matches that." : "Nothing here.")); return; }
    list.forEach(function(f){
      var row = btn("dp-hr" + (SEL_DUMP != null && String(f.id) === String(SEL_DUMP) ? " is-sel" : ""), null, function(){ selectDump(f.id, false); if(isPhone()) closePanel(); });
      row.dataset.dump = f.id;
      var n = el("div", "n", f.name || "Dump site"); if(f.type_label) n.appendChild(el("span", "dp-tag", f.type_label)); if(!f.walk_in) n.appendChild(el("span", "dp-tag warn", f.access_label || "restricted")); row.appendChild(n);
      var s = el("div", "st " + (f.open_now ? "open" : "closed")); s.appendChild(el("i", "dp-dot " + (f.open_now ? "live" : "offline"))); s.appendChild(document.createTextNode(dumpStatus(f))); row.appendChild(s);
      row.appendChild(el("div", "m", [f.county_label, f.address].filter(Boolean).join(" · ")));
      var r = byId[String(f.id)];
      if(r){
        var rk = el("div", "rank" + (r.eligible ? "" : " no"));
        rk.textContent = r.eligible ? [num(r.miles) != null ? Number(r.miles).toFixed(1) + " mi" : null, num(r.minutes) != null ? "~" + Math.round(r.minutes) + " min" : null, num(r.est_tip) != null ? "about " + money(r.est_tip) + " tip" : "quote at the gate"].filter(Boolean).join(" · ") : (r.blockers || []).join(" · ");
        row.appendChild(rk);
      } else if(f.fees && f.fees.length){
        var fe = el("div", "fees"); f.fees.slice(0, 3).forEach(function(x){ var sp = el("span"); sp.appendChild(document.createTextNode(x.label + " ")); sp.appendChild(el("b", null, money(x.amount))); fe.appendChild(sp); }); row.appendChild(fe);
      }
      box.appendChild(row);
    });
  }
  $("dp-dumps-q").addEventListener("input", renderDumps);
  $("dp-dumps-filter").addEventListener("click", function(e){ var b = e.target.closest("button[data-f]"); if(!b) return; DUMP_FILTER = b.dataset.f; setTab("dp-dumps-filter", "f", DUMP_FILTER); renderDumps(); });
  $("dp-dumps-map").checked = DUMPS_ON;
  $("dp-dumps-map").addEventListener("change", function(){ DUMPS_ON = !!this.checked; try { localStorage.setItem("umuve_dispatch_dumps", DUMPS_ON ? "1" : "0"); } catch(e){} if(!DUMPS_ON && SEL_DUMP != null) clearSelection(); renderMap(); });

  // ---------------------------------------------------------------- slide-over panels
  var PANEL = null, PANELS = {board: "dm-p-board", haulers: "dm-p-haulers", dumps: "dm-p-dumps", activity: "dm-p-activity", book: "dp-book"};
  function paintTabs(){ Array.prototype.forEach.call($("dm-tabs").querySelectorAll(".dm-tab"), function(b){ b.classList.toggle("on", b.dataset.p === (PANEL || "map")); }); }
  function openPanel(name){
    Object.keys(PANELS).forEach(function(k){ $(PANELS[k]).hidden = k !== name; });
    PANEL = name; paintTabs(); document.body.classList.add("dm-sheet");
    if(name === "dumps"){ renderDumps(); if(SEL_JOB != null) rankDumpsFor(SEL_JOB); }
    if(name === "haulers" && SEL_HAULER != null){ var row = document.querySelector('.dp-hr[data-id="' + String(SEL_HAULER).replace(/"/g, "") + '"]'); if(row) row.scrollIntoView({block: "nearest"}); }
  }
  function closePanel(){
    Object.keys(PANELS).forEach(function(k){ $(PANELS[k]).hidden = true; });
    PANEL = null; bookOpen = false; paintTabs(); document.body.classList.remove("dm-sheet");
  }
  $("dm-tabs").addEventListener("click", function(e){
    var b = e.target.closest(".dm-tab"); if(!b) return; var p = b.dataset.p;
    if(p === "map" || p === PANEL){ closePanel(); return; }
    if(p === "book"){ openBook(); return; }
    openPanel(p);
  });
  Array.prototype.forEach.call(document.querySelectorAll(".dm-panel [data-close]"), function(x){ x.addEventListener("click", closePanel); });

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
  document.addEventListener("keydown", function(e){
    if(e.key !== "Escape") return;
    if(!$("dp-drawer").hidden){ closeDrawer(); return; }
    if(PANEL){ closePanel(); return; }
    if(SEL_JOB != null || SEL_HAULER != null) clearSelection();
  });
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
    top.appendChild(el("span", "dp-tag " + groupTag(group), j.status_label || j.status || group));
    var pi = payInfo(j.payment); top.appendChild(el("span", "dp-tag " + pi.cls, pi.text));
    if(j.confirmed) top.appendChild(el("span", "dp-tag ok", "✓ confirmed" + (j.confirmed_by ? " by " + j.confirmed_by : "")));
    c.appendChild(top);
    var w = el("div", "when", (j.scheduled_human || "No time set") + (j.window ? " · " + j.window : "")); var hh = group === "done" || group === "cancelled" ? null : hoursHint(j.hours_out); if(hh) w.appendChild(el("span", "hint " + hh.cls, hh.text)); c.appendChild(w);
    var ad = el("div", "addr", j.address || "No address"); if(j.county) ad.appendChild(el("span", null, " · " + j.county)); c.appendChild(ad);
    c.appendChild(el("div", "items", itemsText(j)));
    var m = el("div", "money"); m.appendChild(el("b", null, money(j.total))); if(num(j.disposal_fee)) m.appendChild(el("span", null, "incl. " + money(j.disposal_fee) + " dump fee")); if(num(j.service_fee)) m.appendChild(el("span", null, money(j.service_fee) + " service")); c.appendChild(m);
    var who = el("div", "who"), cu = j.customer || {}, cl = el("div"); cl.appendChild(document.createTextNode((cu.name || "Customer") + " ")); if(cu.phone) cl.appendChild(telLink(cu.phone)); if(num(cu.prior_jobs)) cl.appendChild(el("span", null, " · " + cu.prior_jobs + " prior")); who.appendChild(cl);
    var hl = el("div"); if(j.hauler){ hl.appendChild(document.createTextNode("Hauler: " + (j.hauler.name || "") + " ")); if(j.hauler.tier_label) hl.appendChild(el("span", "dp-tag", j.hauler.tier_label)); if(j.hauler.phone){ hl.appendChild(document.createTextNode(" ")); hl.appendChild(telLink(j.hauler.phone)); } } else hl.appendChild(el("span", "none", group === "open" ? "No hauler yet" : "—")); who.appendChild(hl); c.appendChild(who);
    if(full && j.notes) c.appendChild(el("div", "notes", j.notes));
    if(j.lead_source) c.appendChild(el("div", "src", "via " + j.lead_source));
    if(!full && num(j.lat) != null && num(j.lng) != null){ var pin = btn("pill sm", "Show on map", function(){ selectJob(j.id, true); if(isPhone()) closePanel(); }); var pr = el("div", "dp-actions"); pr.appendChild(pin); c.appendChild(pr); }
    var acts = actions(j, group, c); if(acts) c.appendChild(acts);
    return c;
  }

  // Inline editor host: one open at a time per card.
  function inline(host){ var old = host.querySelector(".dp-inline"); if(old) old.remove(); var box = el("div", "dp-inline"); box.addEventListener("click", function(e){ e.stopPropagation(); }); host.appendChild(box); return box; }
  function closeInline(host){ var old = host.querySelector(".dp-inline"); if(old) old.remove(); }
  function afterAction(j, msg){ toast(msg || "Done", "good"); return load().then(function(){ if(DRAWER.kind === "job" && String(DRAWER.id) === String(j.id)) openJob(j.id); if(SEL_JOB != null && String(SEL_JOB) === String(j.id)) renderDock(true); }); }

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
  window.__openBook = function(){ openBook(); };
  function openBook(){
    openPanel("book"); bookOpen = true; resetBook();
    ensureCatalog().then(renderItems).catch(fail);
    $("bk-date").value = todayIso(); loadBookSlots(); refreshHaulerSelect();
    $("dp-book").querySelector(".dm-panel-body").scrollTop = 0; setTimeout(function(){ $("bk-phone").focus(); }, 300);
  }
  function closeBook(){ closePanel(); }
  function resetBook(){
    BK = {items: {}, addons: {}, load: null, geo: null, pay: "link", hauler: "open", customer_id: null};
    ["bk-phone", "bk-name", "bk-email", "bk-address", "bk-notes", "bk-items-q"].forEach(function(id){ $(id).value = ""; });
    $("bk-matches").hidden = true; clear($("bk-matches")); $("bk-geo").hidden = true; $("bk-err").hidden = true; $("bk-sendtext").checked = true;
    setTab("bk-pay", "v", "link"); setTab("bk-hauler", "v", "open"); $("bk-hauler-sel").hidden = true;
    clear($("bk-est")); $("bk-est").appendChild(el("p", "dp-empty", "Add items to see a price."));
    if(CATALOG) renderItems();
  }
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
      return load().then(function(){ if(r.job && r.job.id != null){ selectJob(r.job.id, true); openJob(r.job.id); } });
    }).catch(function(e){ sb.disabled = false; bad(e.message || "Couldn't book that."); });
  });

  // ---------------------------------------------------------------- boot
  if(ls(JWT_KEY) || ls(KEY)) load(); else showGate();
})();
