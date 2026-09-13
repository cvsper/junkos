/* Desk shell — sidebar + greeting bar around every desk page.
   Builds after sign-in (#tool visible). Desktop: the page's own header
   controls move into the top bar and the header hides. Phone: nothing moves;
   tapping the brand in the page header opens the sidebar as a sheet.
   CSS lives in /static/desk-shell.css (the desk CSP is style-src 'self'). */
(function(){
  "use strict";
  var path = location.pathname;
  var PAGE = path === "/va" || path === "/va/" ? "home"
    : path.indexOf("/va/calls") === 0 ? "calls"
    : path.indexOf("/va/analytics") === 0 ? "analytics"
    : path.indexOf("/va/manager") === 0 ? "manager"
    : path.indexOf("/va/dispatch") === 0 ? "dispatch"
    : path.indexOf("/va/text") === 0 ? "text"
    : path.indexOf("/va/email") === 0 ? "email"
    : path.indexOf("/coach") === 0 ? "coach"
    : path.indexOf("/optext") === 0 ? "optext" : "other";

  var I = {
    home: '<svg viewBox="0 0 24 24"><path d="M3 11.5 12 4l9 7.5"/><path d="M5 10.5V20h14v-9.5"/><path d="M10 20v-6h4v6"/></svg>',
    phone: '<svg viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/></svg>',
    chart: '<svg viewBox="0 0 24 24"><path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-8"/><path d="M22 20H2"/></svg>',
    truck: '<svg viewBox="0 0 24 24"><path d="M3 7h11v9H3z"/><path d="M14 10h4l3 3v3h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/></svg>',
    chat: '<svg viewBox="0 0 24 24"><path d="M4 5h16v11H9l-5 4z"/></svg>',
    team: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.5A5 5 0 0 1 22 19"/></svg>',
    msg: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 8l9 6 9-6"/></svg>',
    mail: '<svg viewBox="0 0 24 24"><path d="M4 6h16v12H4z"/><path d="M4 7l8 5 8-5"/></svg>',
    hat: '<svg viewBox="0 0 24 24"><path d="M2 9l10-4 10 4-10 4z"/><path d="M6 11v5c0 1.5 3 3 6 3s6-1.5 6-3v-5"/></svg>',
    out: '<svg viewBox="0 0 24 24"><path d="M10 4H5v16h5"/><path d="M14 8l4 4-4 4"/><path d="M18 12H9"/></svg>'
  };

  var JWT_KEY = "umuve_desk_jwt", ME_KEY = "umuve_desk_me", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";
  function ls(k){ try { return localStorage.getItem(k) || ""; } catch(e){ return ""; } }
  function me(){ try { return JSON.parse(ls(ME_KEY) || "null"); } catch(e){ return null; } }
  function vaName(){ var m = me(); return (m && m.name) || ls(VA_KEY) || ""; }
  function firstName(){ return (vaName().trim().split(/\s+/)[0] || ""); }
  function isManager(){ var m = me(); if(!m) return true; return !!(m.is_manager || m.role === "manager" || m.role === "admin"); }
  function el(tag, cls, html){ var e = document.createElement(tag); if(cls) e.className = cls; if(html != null) e.innerHTML = html; return e; }
  function text(tag, cls, t){ var e = document.createElement(tag); if(cls) e.className = cls; e.textContent = t; return e; }

  var TILES = [
    {id: "home", label: "Home", href: "/va", icon: I.home},
    {id: "calls", label: "Call Desk", href: "/va/calls", icon: I.phone},
    {id: "analytics", label: "Analytics", href: "/va/analytics", icon: I.chart},
    {id: "dispatch", label: "Dispatch", href: "/va/dispatch", icon: I.truck},
    {id: "coach", label: "Coach", href: "/coach", icon: I.chat},
    {id: "manager", label: "Manager", href: "/va/manager", icon: I.team, mgr: true}
  ];
  var LIST = [
    {id: "text", label: "Send a text", href: "/va/text", icon: I.msg},
    {id: "email", label: "Send an email", href: "/va/email", icon: I.mail},
    {id: "optext", label: "Text an operator", href: "/optext", icon: I.hat}
  ];

  function greeting(){
    var h = new Date().getHours();
    var g = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
    var n = firstName();
    return n ? g + ", " + n : g;
  }
  function today(){
    try { return new Date().toLocaleDateString(undefined, {weekday: "long", day: "numeric", month: "long", year: "numeric"}); }
    catch(e){ return new Date().toDateString(); }
  }
  var FADE_MS = 400;
  function go(href){
    document.body.classList.add("pg-out");
    setTimeout(function(){ location.href = href; }, FADE_MS);
  }
  window.__deskGo = go;
  // Any plain click on a same-site link fades the page out before it leaves.
  document.addEventListener("click", function(e){
    if(e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest("a[href]"); if(!a) return;
    if(a.target && a.target !== "_self") return;
    if(a.hasAttribute("download") || a.getAttribute("href").charAt(0) === "#") return;
    var url; try { url = new URL(a.href, location.href); } catch(err){ return; }
    if(url.origin !== location.origin) return;
    if(!/^(tel|mailto|sms):/.test(url.protocol) && url.pathname === location.pathname && url.search === location.search) return;
    if(/^(tel|mailto|sms):/.test(a.href)) return;
    e.preventDefault(); go(a.href);
  }, true);
  // Coming back via the back button restores the page from cache with the
  // fade-out class still on; take it off so the page is visible.
  window.addEventListener("pageshow", function(){ document.body.classList.remove("pg-out"); });
  function signOut(){
    try { [JWT_KEY, ME_KEY, KEY, VA_KEY].forEach(function(k){ localStorage.removeItem(k); }); } catch(e){}
    go("/va");
  }

  function buildSide(){
    var side = el("aside", "sh-side");
    side.appendChild(el("div", "sh-handle"));
    var brand = el("a", "sh-brand"); brand.href = "/va";
    var img = document.createElement("img"); img.src = "/static/brand-logo.png"; img.alt = "Umuve";
    brand.appendChild(img); brand.appendChild(text("b", null, "muve"));
    side.appendChild(brand);
    var tiles = el("div", "sh-tiles");
    TILES.forEach(function(t){
      if(t.mgr && !isManager()) return;
      var a = el("a", "sh-tile" + (t.id === PAGE ? " is-on" : ""), t.icon); a.href = t.href;
      a.appendChild(text("span", null, t.label)); tiles.appendChild(a);
    });
    side.appendChild(tiles);
    var list = el("div", "sh-list");
    LIST.forEach(function(t){
      var a = el("a", "sh-item" + (t.id === PAGE ? " is-on" : "")); a.href = t.href;
      a.appendChild(el("i", null, t.icon)); a.appendChild(text("span", null, t.label)); list.appendChild(a);
    });
    side.appendChild(list);
    var foot = el("div", "sh-foot");
    foot.appendChild(text("div", "sh-avatar", (firstName().charAt(0) || "U").toUpperCase()));
    var who = el("div"); who.appendChild(text("b", null, vaName() || "Desk")); who.appendChild(text("span", null, "Signed in"));
    foot.appendChild(who);
    var out = text("button", null, "Sign out"); out.type = "button"; out.addEventListener("click", signOut);
    foot.appendChild(out);
    side.appendChild(foot);
    return side;
  }

  // Which header controls travel up into the top bar on desktop.
  function movable(node){
    if(node.nodeType !== 1) return false;
    if(node.matches(".brand, img.brand, .wordmark, .mg-title, .bar-sub")) return false;
    if(node.matches("a.back") && (node.getAttribute("href") === "/va" || node.getAttribute("href") === "/va/calls") && !node.id) return false;
    return node.matches("button, a, .clock, .ds-link, .who");
  }

  function buildTop(header){
    var top = el("header", "sh-top");
    var g = el("div", "sh-greet");
    g.appendChild(text("h1", null, greeting()));
    var meta = el("div", "sh-meta"); meta.appendChild(text("span", null, today()));
    g.appendChild(meta); top.appendChild(g);
    var actions = el("div", "sh-actions");
    if(header && window.matchMedia("(min-width:960px)").matches){
      Array.prototype.slice.call(header.children).forEach(function(c){
        if(c.matches(".bar-sub")){ if(PAGE !== "home") meta.appendChild(c); }
        else if(movable(c)) actions.appendChild(c);
      });
    }
    top.appendChild(actions);
    top.appendChild(text("div", "sh-avatar", (firstName().charAt(0) || "U").toUpperCase()));
    return top;
  }

  function homeKpis(){
    var body = document.querySelector("#tool .body"); if(!body) return;
    var wrap = el("div", "sh-kpis");
    var spec = [["calls", "Calls in today"], ["human", "Answered by a person"], ["leads", "Leads today"], ["booked", "Booked today"]];
    var cells = {};
    spec.forEach(function(s){
      var a = el("a", "sh-kpi"); a.href = "/va/analytics";
      var b = text("b", "dim", "–"); a.appendChild(b); a.appendChild(text("span", null, s[1]));
      cells[s[0]] = b; wrap.appendChild(a);
    });
    body.insertBefore(wrap, body.firstChild);
    var headers = {"Content-Type": "application/json"}, payload = {period: "today"};
    if(ls(JWT_KEY)) headers["Authorization"] = "Bearer " + ls(JWT_KEY); else { payload.code = ls(KEY); payload.va_name = vaName(); }
    fetch("/api/va/analytics/desk", {method: "POST", headers: headers, body: JSON.stringify(payload)})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if(!d) return;
        var inb = d.inbound || {}, sp = d.speed || {};
        function put(k, v){ if(v == null) return; cells[k].textContent = String(v); cells[k].classList.remove("dim"); }
        put("calls", inb.calls); put("human", inb.answered_by_human != null ? inb.answered_by_human : inb.answered);
        put("leads", sp.leads); put("booked", inb.booked);
      }).catch(function(){});
  }

  function build(){
    if(document.body.classList.contains("has-shell")) return;
    var app = document.getElementById("app"), tool = document.getElementById("tool") || document.getElementById("chat");
    if(!app || !tool) return;
    var header = tool.querySelector("header.bar, header.mg-bar");
    var shell = el("div", "sh"), main = el("div", "sh-main"), page = el("div", "sh-page");
    document.body.classList.add("has-shell", "sh-" + PAGE);
    shell.appendChild(buildSide());
    main.appendChild(buildTop(header));
    app.parentNode.insertBefore(shell, app);
    page.appendChild(app); main.appendChild(page); shell.appendChild(main);
    var scrim = el("div", "sh-scrim"); shell.appendChild(scrim);   // inside the shell so it stacks under the sheet
    function close(){ document.body.classList.remove("sh-open"); }
    function open(){ document.body.classList.add("sh-open"); }
    scrim.addEventListener("click", close);
    document.addEventListener("keydown", function(e){ if(e.key === "Escape") close(); });
    if(header){
      var brand = header.querySelector(".brand, img.brand, .wordmark");
      if(brand) brand.addEventListener("click", function(e){
        if(window.matchMedia("(max-width:959px)").matches){ e.preventDefault(); open(); }
      });
    }
    if(PAGE === "home") homeKpis();
  }

  function ready(){
    var tool = document.getElementById("tool") || document.getElementById("chat");
    if(!tool) return;
    if(!tool.hidden){ build(); return; }
    new MutationObserver(function(){ if(!tool.hidden) build(); }).observe(tool, {attributes: true, attributeFilter: ["hidden"]});
  }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", ready); else ready();
})();
