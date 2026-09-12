/* Desk dock — one round trigger that springs open into the desk's quick
   actions (Work, Leads, Dial). A native port of the 21st.dev ExpandMenu:
   the trigger stays anchored at the corner, the ⋮ turns into an × (45°),
   items expand away from it with a staggered spring, click-outside closes.

   Loads before desk-dialpad / desk-work / desk-leads; each registers its
   action here instead of floating its own pill:
     window.__deskDock.add({id, label, icon, title, onClick}) → item element
     window.__deskDock.setBadge(id, n, hot)
     window.__deskDock.setLive(id, bool)
   CSS lives in /static/desk-dock.css (the desk's CSP is style-src 'self'). */
(function(){
  "use strict";
  (function(){ if(document.querySelector('link[href^="/static/desk-dock.css"]')) return; var l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/static/desk-dock.css?v=1"; document.head.appendChild(l); })();

  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  var ICONS = {
    dots: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm0 4.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm0 4.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z"/></svg>'
  };

  var dock = el("div", "dk"); dock.id = "desk-dock";
  var pill = el("div", "dk-pill");
  var list = el("div", "dk-items");
  var trigger = el("button", "dk-trigger"); trigger.type = "button"; trigger.setAttribute("aria-expanded", "false"); trigger.setAttribute("aria-label", "Quick actions");
  var tSpan = el("span", "dk-tspan"); tSpan.innerHTML = ICONS.dots; trigger.appendChild(tSpan);
  var tBadge = el("span", "dk-tbadge"); tBadge.hidden = true;
  pill.appendChild(list); pill.appendChild(trigger);   // direction "up": trigger last, anchored at the corner
  dock.appendChild(pill); dock.appendChild(tBadge);     // badge outside the pill so overflow:hidden can't clip it
  document.body.appendChild(dock);

  var items = {}, order = [], open = false;

  function setOpen(v){
    open = !!v;
    dock.classList.toggle("is-open", open);
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
    order.forEach(function(id, i){ items[id].el.style.transitionDelay = open ? (i * 40) + "ms" : ((order.length - 1 - i) * 25) + "ms"; });
  }
  trigger.addEventListener("click", function(e){ e.stopPropagation(); setOpen(!open); });
  document.addEventListener("mousedown", function(e){ if(open && !dock.contains(e.target)) setOpen(false); });
  document.addEventListener("touchstart", function(e){ if(open && !dock.contains(e.target)) setOpen(false); }, {passive: true});
  document.addEventListener("keydown", function(e){ if(e.key === "Escape" && open) setOpen(false); });

  function refreshTrigger(){
    var total = 0, hot = false, live = false;
    order.forEach(function(id){ var it = items[id]; total += it.n || 0; hot = hot || !!it.hot; live = live || !!it.live; });
    tBadge.textContent = total ? String(total) : "";
    tBadge.hidden = !total;
    dock.classList.toggle("has-hot", hot);
    dock.classList.toggle("is-live", live);
  }

  function add(spec){
    var b = el("button", "dk-item"); b.type = "button"; b.dataset.id = spec.id;
    if(spec.title) b.title = spec.title;
    var ic = el("span", "dk-ic"); ic.innerHTML = spec.icon || ""; b.appendChild(ic);
    b.appendChild(el("span", "dk-lbl", spec.label));
    var n = el("span", "dk-n"); n.hidden = true; b.appendChild(n);
    b.addEventListener("click", function(e){ e.stopPropagation(); setOpen(false); if(spec.onClick) spec.onClick(e); });
    // newest registration sits closest to the trigger (bottom of the stack)
    list.appendChild(b);
    items[spec.id] = {el: b, n: 0, hot: false, live: false, lbl: b.querySelector(".dk-lbl"), badge: n};
    order.push(spec.id);
    refreshTrigger();
    return b;
  }
  function setBadge(id, n, hot){
    var it = items[id]; if(!it) return;
    it.n = Number(n) || 0; it.hot = !!hot;
    it.badge.textContent = it.n ? String(it.n) : ""; it.badge.hidden = !it.n;
    it.el.classList.toggle("hot", it.hot);
    refreshTrigger();
  }
  function setLive(id, live){
    var it = items[id]; if(!it) return;
    it.live = !!live; it.el.classList.toggle("live", it.live);
    refreshTrigger();
  }
  function setLabel(id, text){ var it = items[id]; if(it) it.lbl.textContent = text; }

  // Sit above the bottom line panel on phones; beside it when it's a side column.
  function place(){
    var line = document.getElementById("line");
    var h = 0;
    dock.style.right = "14px";
    if(line && !line.hidden){
      var r = line.getBoundingClientRect();
      var isBottomBar = r.bottom >= window.innerHeight - 2 && r.height > 0 &&
                        r.height < window.innerHeight * 0.65 && r.width > window.innerWidth * 0.6;
      if(isBottomBar) h = r.height;
      else if(r.width && r.left > window.innerWidth * 0.4 && r.right >= window.innerWidth - 80){
        dock.style.right = Math.round(window.innerWidth - r.left + 14) + "px";
      }
    }
    dock.style.bottom = (h + 14) + "px";
  }
  place(); window.addEventListener("resize", place); setInterval(place, 1500);

  window.__deskDock = {add: add, setBadge: setBadge, setLive: setLive, setLabel: setLabel, open: function(){ setOpen(true); }, close: function(){ setOpen(false); }};
})();
