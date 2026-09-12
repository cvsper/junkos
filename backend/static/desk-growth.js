/* Umuve Call Desk — Phase 5 (Growth) client layer.
   Loads alongside /va/calls.js and touches the desk only through the DOM:
     - registers the service worker (/va/desk-sw.js) so the desk installs
     - "Enable notifications" in the line panel head (Web Push, VAPID)
     - app badge mirrors the Replies unread badge
     - "Add callbacks to my calendar" in the hours panel
     - "Maya spoke to them" under the card's angle when a pre-qual result exists
   Same auth as the desk: the JWT / passcode + name kept in localStorage.
   CSP is script-src 'self' / style-src 'self': no inline styles; rules go in via CSSOM. */
(function () {
  "use strict";
  var KEY = "umuve_coach_code", VA_KEY = "umuve_va_name", JWT_KEY = "umuve_desk_jwt", ME_KEY = "umuve_desk_me";

  function ls(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } }
  function me() { try { return JSON.parse(ls(ME_KEY) || "null"); } catch (e) { return null; } }
  function vaName() { var m = me(); return (m && m.name) || ls(VA_KEY) || ""; }
  function signedIn() { return !!ls(JWT_KEY) || !!ls(KEY); }
  function post(path, body) {
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if (ls(JWT_KEY)) headers["Authorization"] = "Bearer " + ls(JWT_KEY);
    else { body.code = ls(KEY); body.va_name = vaName(); }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function (r) { return r.json().then(function (j) { return {status: r.status, body: j}; }); });
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  // --- styles via CSSOM (allowed under style-src 'self') ---------------------
  (function(){ if(document.querySelector('link[href^="/static/desk-growth.css"]')) return; var l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/static/desk-growth.css?v=1"; document.head.appendChild(l); })();

  var toastEl = null, toastTimer = null;
  function toast(msg) {
    if (!toastEl) { toastEl = el("div", "gw-toast"); toastEl.setAttribute("role", "status"); document.body.appendChild(toastEl); }
    toastEl.textContent = msg; toastEl.classList.add("in");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { toastEl.classList.remove("in"); }, 2600);
  }

  // --- service worker ----------------------------------------------------------
  var swReg = null;
  function registerSW() {
    if (!("serviceWorker" in navigator)) return Promise.resolve(null);
    return navigator.serviceWorker.register("/va/desk-sw.js", {scope: "/va/"})
      .then(function (r) { swReg = r; return r; })
      .catch(function () { return null; });
  }

  // --- app badge mirrors the Replies badge ---------------------------------------
  function syncBadge() {
    if (!("setAppBadge" in navigator)) return;
    var b = document.getElementById("inbox-badge");
    var n = (!b || b.hidden) ? 0 : (parseInt(b.textContent, 10) || 0);
    try { if (n > 0) navigator.setAppBadge(n); else if (navigator.clearAppBadge) navigator.clearAppBadge(); } catch (e) {}
  }
  function watchBadge() {
    var b = document.getElementById("inbox-badge");
    if (!b) return;
    new MutationObserver(syncBadge).observe(b, {attributes: true, childList: true, characterData: true, subtree: true});
    syncBadge();
  }

  // --- push -------------------------------------------------------------------------
  function b64ToU8(s) {
    var pad = "=".repeat((4 - s.length % 4) % 4);
    var raw = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  var pushBtn = null;
  function pushSupported() { return "PushManager" in window && "Notification" in window && "serviceWorker" in navigator; }
  function setPushBtn(state) {
    if (!pushBtn) return;
    pushBtn.hidden = state === "hide";
    if (state === "on") { pushBtn.textContent = "Alerts on"; pushBtn.classList.add("is-on"); pushBtn.title = "Tap to turn off notifications on this device"; }
    else if (state === "off") { pushBtn.textContent = "Enable notifications"; pushBtn.classList.remove("is-on"); pushBtn.title = "Get a notification here when a prospect texts back or leaves a voicemail"; }
    else if (state === "blocked") { pushBtn.textContent = "Notifications blocked"; pushBtn.classList.remove("is-on"); pushBtn.title = "Allow notifications for this site in your browser settings"; }
  }
  function currentSub() {
    if (!swReg) return Promise.resolve(null);
    return swReg.pushManager.getSubscription().catch(function () { return null; });
  }
  function enablePush(key) {
    return Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") { setPushBtn("blocked"); toast("Notifications are blocked for this site."); return null; }
      return swReg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: b64ToU8(key)});
    }).then(function (sub) {
      if (!sub) return null;
      return post("/api/va/growth/push/subscribe", {subscription: sub.toJSON()}).then(function (r) {
        if (r.status === 200) { setPushBtn("on"); toast("You'll get a notification when a prospect replies."); }
        else { toast((r.body && r.body.error) || "Couldn't turn notifications on."); }
        return sub;
      });
    }).catch(function () { toast("Couldn't turn notifications on."); return null; });
  }
  function disablePush() {
    return currentSub().then(function (sub) {
      if (!sub) { setPushBtn("off"); return; }
      var ep = sub.endpoint;
      return sub.unsubscribe().catch(function () {}).then(function () {
        return post("/api/va/growth/push/unsubscribe", {endpoint: ep});
      }).then(function () { setPushBtn("off"); toast("Notifications off on this device."); });
    });
  }
  function initPush() {
    var head = document.querySelector("#line .ln-head");
    if (!head || document.getElementById("gw-push")) return;
    if (!pushSupported()) return;
    fetch("/api/va/growth/push/public-key").then(function (r) { return r.json(); }).then(function (cfg) {
      if (!cfg || !cfg.enabled || !cfg.key) return;
      pushBtn = el("button", "ln-btn", "Enable notifications");
      pushBtn.type = "button"; pushBtn.id = "gw-push";
      var inbox = document.getElementById("inbox-toggle");
      head.insertBefore(pushBtn, inbox || null);
      (swReg ? Promise.resolve(swReg) : registerSW()).then(function () {
        if (!swReg) { setPushBtn("hide"); return; }
        if (Notification.permission === "denied") { setPushBtn("blocked"); return; }
        currentSub().then(function (sub) { setPushBtn(sub ? "on" : "off"); });
      });
      pushBtn.addEventListener("click", function () {
        if (Notification.permission === "denied") { toast("Allow notifications for this site in your browser settings."); return; }
        currentSub().then(function (sub) { return sub ? disablePush() : enablePush(cfg.key); });
      });
    }).catch(function () {});
  }

  // --- calendar ---------------------------------------------------------------------
  function initCalendar() {
    var box = document.getElementById("timebox");
    if (!box || document.getElementById("gw-cal")) return;
    var wrap = el("div", "gw-cal"); wrap.id = "gw-cal";
    var btn = el("button", "tb-btn", "Add callbacks to my calendar"); btn.type = "button";
    var sub = el("div", "gw-sub", "Your scheduled callbacks as 15-minute events. Subscribe once; it stays in sync.");
    wrap.appendChild(btn); wrap.appendChild(sub);
    var list = document.getElementById("tb-list");
    if (list && list.parentNode === box) box.insertBefore(wrap, list); else box.appendChild(wrap);
    btn.addEventListener("click", function () {
      btn.disabled = true;
      post("/api/va/growth/calendar-link", {}).then(function (r) {
        btn.disabled = false;
        if (r.status !== 200) { toast((r.body && r.body.error) || "Couldn't build your calendar link."); return; }
        var url = r.body.url;
        sub.textContent = url;
        var copy = navigator.clipboard && navigator.clipboard.writeText ? navigator.clipboard.writeText(url) : Promise.reject();
        copy.then(function () { toast("Calendar link copied — paste it into Google Calendar › Other calendars › From URL."); })
            .catch(function () { toast("Here's your calendar link — copy it from below."); });
      }).catch(function () { btn.disabled = false; toast("Couldn't build your calendar link."); });
    });
  }

  // --- Maya pre-qual panel under the card -------------------------------------------
  var panel = null, lastKey = "";
  function angleRow() { var a = document.getElementById("c-angle"); return a ? a.closest(".factrow") || a.parentNode : null; }
  function hidePanel() { if (panel) panel.hidden = true; }
  function showPanel(pq) {
    var row = angleRow(); if (!row) return;
    if (!panel) { panel = el("div", "gw-maya"); panel.id = "gw-maya"; row.parentNode.insertBefore(panel, row.nextSibling); }
    panel.textContent = "";
    var k = el("div", "gw-k", "Maya spoke to them");
    var d = (pq.disposition || "").replace("_", " ");
    var chip = el("span", "gw-disp " + (pq.disposition || ""), d.toUpperCase()); k.appendChild(chip);
    if (pq.created_at) { var when = new Date(pq.created_at + (pq.created_at.slice(-1) === "Z" ? "" : "Z")); k.appendChild(el("span", "", when.toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"}))); }
    panel.appendChild(k);
    panel.appendChild(el("div", "gw-sum", pq.summary || (pq.disposition === "warm" ? "They said yes — call now." : "No summary recorded.")));
    if (pq.transcript) {
      var det = el("details", "gw-tx"); det.appendChild(el("summary", "", "Transcript"));
      det.appendChild(el("pre", "", pq.transcript)); panel.appendChild(det);
    }
    panel.hidden = false;
  }
  function refreshCard() {
    var co = document.getElementById("c-company"), ph = document.getElementById("c-phone"), card = document.getElementById("card");
    if (!co || !ph || !card || card.hidden || !signedIn()) { hidePanel(); return; }
    var company = co.textContent.trim(), phone = ph.textContent.trim();
    var key = company + "|" + phone;
    if (!company || key === lastKey) return;
    lastKey = key; hidePanel();
    post("/api/va/growth/card-lookup", {company: company, phone: phone}).then(function (r) {
      if (r.status !== 200 || !r.body.prospect_id) return;
      return post("/api/va/growth/prequal", {prospect_id: r.body.prospect_id}).then(function (q) {
        if (q.status === 200 && q.body.prequal && (company + "|" + phone) === lastKey) showPanel(q.body.prequal);
      });
    }).catch(function () {});
  }
  function watchCard() {
    var co = document.getElementById("c-company");
    if (!co) return;
    new MutationObserver(function () { lastKey = ""; refreshCard(); }).observe(co, {childList: true, characterData: true, subtree: true});
    var card = document.getElementById("card");
    if (card) new MutationObserver(function () { if (card.hidden) hidePanel(); else refreshCard(); }).observe(card, {attributes: true, attributeFilter: ["hidden"]});
    refreshCard();
  }

  // --- boot: run once the desk is open ----------------------------------------------
  var booted = false;
  function boot() {
    if (booted) return; booted = true;
    registerSW().then(function () { initPush(); });
    watchBadge(); initCalendar(); watchCard();
  }
  function ready() {
    var tool = document.getElementById("tool");
    if (!tool) return;
    if (!tool.hidden) boot();
    new MutationObserver(function () { if (!tool.hidden) boot(); }).observe(tool, {attributes: true, attributeFilter: ["hidden"]});
    if ("serviceWorker" in navigator) registerSW();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready); else ready();
})();
