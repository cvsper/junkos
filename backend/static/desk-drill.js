/* Analytics drill-down. Any element with data-metric="…" opens a drawer
   listing the rows behind that number — when it happened, who, what came
   of it, and a link to the record. Shared by /va/analytics and /va/manager.
   The page sets window.__drillScope = () => ({period|days, va}) so the
   drawer uses the same window the numbers did. */
(function(){
  "use strict";
  (function(){ if(document.querySelector('link[href^="/static/desk-drill.css"]')) return; var l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/static/desk-drill.css?v=1"; document.head.appendChild(l); })();
  var JWT_KEY = "umuve_desk_jwt", ME_KEY = "umuve_desk_me", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";
  function jwt(){ try { return localStorage.getItem(JWT_KEY) || ""; } catch(e){ return ""; } }
  function me(){ try { return JSON.parse(localStorage.getItem(ME_KEY) || "null"); } catch(e){ return null; } }
  function code(){ try { return localStorage.getItem(KEY) || ""; } catch(e){ return ""; } }
  function vaName(){ var m = me(); try { return (m && m.name) || localStorage.getItem(VA_KEY) || ""; } catch(e){ return ""; } }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { body.code = code(); body.va_name = vaName(); }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }
  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  function money(v){ return v == null ? "" : "$" + Number(v).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}); }

  var TITLES = {calls: "Calls in", human: "Answered by a person", maya: "Went to Maya", missed: "Missed or voicemail",
    in_hours: "Calls in hours", after_hours: "Calls after hours", booked_calls: "Booked from calls", quoted_calls: "Quoted on a call",
    leads: "Leads", leads_touched: "Leads a person reached", leads_untouched: "Leads never touched", leads_auto_texted: "Leads auto-texted",
    dials: "Dials", connects: "Reached", interested: "Interested", wins: "Wins", callbacks: "Callbacks set",
    jobs: "Bookings", paid: "Paid bookings", completed: "Completed jobs", cancelled: "Cancelled jobs", revenue: "Paid revenue",
    dump_fees: "Dump fees passed to haulers", refunded: "Refunds", assigned: "Jobs with a hauler", confirmed: "Confirmed before the job",
    unconfirmed: "Not confirmed", no_shows: "Hauler no-shows", hauler_completed: "Completed by hauler",
    maya_calls: "Calls Maya took", maya_quoted: "Maya gave a price", maya_booked: "Booked by Maya", maya_lost: "Priced by Maya, didn't book",
    shifts: "Shifts on the clock", classes: "Weekly classes"};
  function title(metric){
    var k = metric.split(":")[0], arg = metric.split(":")[1];
    if(k === "source") return "Calls from " + (arg || "").replace(/^\w/, function(c){ return c.toUpperCase(); });
    if(k === "disposition" || k === "outcome" || k === "channel") return (arg || k).replace(/_/g, " ").replace(/^\w/, function(c){ return c.toUpperCase(); });
    return TITLES[k] || k;
  }

  var wrap = null, list = null, head = null, sub = null, more = null, state = {metric: null, offset: 0, rows: []};

  function ensure(){
    if(wrap) return;
    wrap = el("div", "dr-wrap"); wrap.hidden = true;
    var panel = el("aside", "dr"); panel.setAttribute("role", "dialog"); panel.setAttribute("aria-modal", "true");
    var h = el("div", "dr-h");
    head = el("h3", null, ""); sub = el("div", "dr-sub", "");
    var x = el("button", "dr-x", "×"); x.type = "button"; x.setAttribute("aria-label", "Close"); x.addEventListener("click", close);
    var ht = el("div"); ht.appendChild(head); ht.appendChild(sub);
    h.appendChild(ht); h.appendChild(x);
    list = el("div", "dr-list");
    more = el("button", "dr-more", "Show more"); more.type = "button"; more.hidden = true; more.addEventListener("click", function(){ load(state.metric, state.offset); });
    panel.appendChild(h); panel.appendChild(list); panel.appendChild(more);
    wrap.appendChild(panel); document.body.appendChild(wrap);
    wrap.addEventListener("click", function(e){ if(e.target === wrap) close(); });
    document.addEventListener("keydown", function(e){ if(e.key === "Escape" && !wrap.hidden) close(); });
  }
  function close(){ if(wrap){ wrap.hidden = true; document.body.classList.remove("dr-locked"); } }

  function row(r){
    var it = el("div", "dr-row");
    var top = el("div", "dr-top");
    top.appendChild(el("span", "dr-when", r.when || "—"));
    if(r.amount != null) top.appendChild(el("span", "dr-amt", money(r.amount)));
    it.appendChild(top);
    var what = el("div", "dr-what"); what.textContent = r.what || "";
    if(r.source) what.appendChild(el("span", "dr-tag", r.source));
    if(r.channel) what.appendChild(el("span", "dr-tag", r.channel));
    if(r.category) what.appendChild(el("span", "dr-tag", r.category));
    if(r.code) what.appendChild(el("span", "dr-tag", r.code));
    it.appendChild(what);
    var res = el("div", "dr-res");
    if(r.who) res.appendChild(el("b", null, r.who + " · "));
    res.appendChild(document.createTextNode(r.result || ""));
    if(r.duration) res.appendChild(el("span", "dr-dim", " · " + Math.round(r.duration / 60) + " min"));
    it.appendChild(res);
    if(r.note) it.appendChild(el("div", "dr-note", r.note));
    if(r.link){ var a = el("a", "dr-link", r.link.indexOf("/va/dispatch") === 0 ? "Open in Dispatch →" : "Open on the desk →"); a.href = r.link; it.appendChild(a); }
    return it;
  }

  function load(metric, offset){
    ensure();
    var scope = (window.__drillScope ? window.__drillScope() : {}) || {};
    var body = Object.assign({}, scope, {metric: metric, limit: 60, offset: offset || 0});
    if(!offset){ list.textContent = ""; state = {metric: metric, offset: 0, rows: []}; head.textContent = title(metric); sub.textContent = "Loading…"; more.hidden = true; }
    wrap.hidden = false; document.body.classList.add("dr-locked");
    post("/api/va/analytics/detail", body).then(function(r){
      if(r.status !== 200){ sub.textContent = (r.body && r.body.error) || "Couldn't load."; return; }
      var b = r.body;
      state.offset = b.offset + b.rows.length;
      sub.textContent = b.total + (b.total === 1 ? " record" : " records") + " · " + b.label + (b.va ? " · " + b.va : "") + (b.total_amount != null ? " · " + money(b.total_amount) : "");
      if(!b.rows.length && !offset){ list.appendChild(el("div", "dr-empty", "Nothing in this period.")); }
      b.rows.forEach(function(x){ list.appendChild(row(x)); });
      more.hidden = state.offset >= b.total;
    }).catch(function(){ sub.textContent = "Couldn't reach the desk."; });
  }

  document.addEventListener("click", function(e){
    var t = e.target.closest("[data-metric]"); if(!t) return;
    if(e.target.closest("a")) return;
    e.preventDefault();
    load(t.getAttribute("data-metric"), 0);
  });
  document.addEventListener("keydown", function(e){
    if(e.key !== "Enter" && e.key !== " ") return;
    var t = e.target.closest("[data-metric]"); if(!t) return;
    e.preventDefault(); load(t.getAttribute("data-metric"), 0);
  });
  // make marked elements keyboard-reachable and visibly clickable
  function decorate(){
    document.querySelectorAll("[data-metric]").forEach(function(n){
      if(!n.classList.contains("dr-hit")){ n.classList.add("dr-hit"); if(!n.hasAttribute("tabindex")) n.setAttribute("tabindex", "0"); n.setAttribute("role", "button"); n.title = "See what's behind this number"; }
    });
  }
  decorate();
  new MutationObserver(decorate).observe(document.body, {childList: true, subtree: true});
  window.__drill = {open: function(m){ load(m, 0); }, close: close};
})();
