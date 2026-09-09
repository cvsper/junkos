/* Desk manager page — reads /api/va/analytics/* and /api/va/coaching/*.
   No libraries; the chart is inline SVG built here. Identity is whatever the
   Call Desk stored (JWT, else the shared code + name). */
(function(){
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
  function svg(tag, attrs){ var e = document.createElementNS("http://www.w3.org/2000/svg", tag); for(var k in attrs) e.setAttribute(k, attrs[k]); return e; }
  function $(id){ return document.getElementById(id); }
  function money(v){ return v == null ? "–" : "$" + Number(v).toFixed(2); }
  function pct(v){ return (v == null ? 0 : v) + "%"; }
  function dayLabel(iso){ var d = new Date(iso + "T12:00:00"); return d.toLocaleDateString([], {month: "short", day: "numeric"}); }

  var gate = $("gate"), tool = $("tool"), err = $("err");
  var days = 30, va = "";
  if(!jwt() && !code()){ gate.hidden = false; return; }
  tool.hidden = false;
  var m = me();
  $("who").textContent = m ? (m.name + (m.is_manager ? " · manager" : "")) : (vaName() + " · access code");

  function say(msg){ err.textContent = msg; err.hidden = !msg; }
  function tableRows(table, head, rows, opts){
    table.textContent = "";
    var tr = el("tr"); head.forEach(function(h){ tr.appendChild(el("th", null, h)); }); table.appendChild(tr);
    if(!rows.length){ var td = el("td", "mg-empty", (opts && opts.empty) || "Nothing in this period yet."); td.colSpan = head.length; var r = el("tr"); r.appendChild(td); table.appendChild(r); return; }
    rows.forEach(function(cells, i){
      var row = el("tr", (opts && opts.total && i === rows.length - 1) ? "tot" : null);
      cells.forEach(function(c){
        var td = el("td");
        if(c && typeof c === "object" && c.nodeType){ td.appendChild(c); }
        else if(c && typeof c === "object"){ td.textContent = c.text; if(c.cls) td.className = c.cls; }
        else td.textContent = c == null ? "–" : c;
        row.appendChild(td);
      });
      table.appendChild(row);
    });
  }
  function barCell(v, max, cls){
    var wrap = el("span"); var b = el("i", "bar"); b.style.width = (max ? Math.max(2, Math.round(80 * v / max)) : 2) + "px"; wrap.appendChild(b);
    wrap.appendChild(document.createTextNode(v)); return wrap;
  }

  // ---- funnel → KPIs, tables, heat, facts ----------------------------------
  function renderFunnel(f){
    $("k-dials").textContent = f.dials;
    $("k-reach").textContent = pct(f.reach_rate);
    $("k-int").textContent = f.interested;
    var w = $("k-wins"); w.textContent = f.wins; w.classList.toggle("hot", f.wins > 0);
    $("side-note").textContent = "Demand " + f.by_side.demand.dials + " dials · supply " + f.by_side.supply.dials + " dials";
    // caller picker keeps its options across periods
    var pick = $("va-pick"); var have = {}; Array.prototype.forEach.call(pick.options, function(o){ have[o.value] = 1; });
    (f.by_va || []).forEach(function(r){ if(r.va && !have[r.va]){ var o = el("option", null, r.va); o.value = r.va; pick.appendChild(o); } });
    var maxD = Math.max.apply(null, [1].concat((f.by_va || []).map(function(r){ return r.dials; })));
    tableRows($("t-va"), ["Caller", "Dials", "Reached", "Interested", "Wins", "Reach rate", "Conversion"],
      (f.by_va || []).map(function(r){ return [r.va, barCell(r.dials, maxD), r.connects, r.interested, {text: r.wins, cls: r.wins ? "hot" : ""}, pct(r.reach_rate), pct(r.conversion)]; }),
      {empty: "No calls logged in this period."});
    var maxC = Math.max.apply(null, [1].concat((f.by_category || []).map(function(r){ return r.dials; })));
    tableRows($("t-cat"), ["Category", "Dials", "Reached", "Interested", "Wins", "Reach rate"],
      (f.by_category || []).map(function(r){ return [r.category, barCell(r.dials, maxC), r.connects, r.interested, {text: r.wins, cls: r.wins ? "hot" : ""}, pct(r.reach_rate)]; }),
      {empty: "No calls logged in this period."});
    renderHeat(f.heatmap);
    var facts = $("facts"); facts.textContent = "";
    var cb = f.callbacks || {}, tx = f.texts || {};
    [[cb.set || 0, "Callbacks set"], [(cb.kept || 0) + (cb.set ? " · " + pct(cb.kept_rate) : ""), "Callbacks kept" + (cb.pending ? " (" + cb.pending + " still ahead)" : "")],
     [tx.sent || 0, "Texts sent"], [tx.received || 0, "Texts back"]].forEach(function(x){
      var d = el("div", "mg-fact"); d.appendChild(el("b", null, String(x[0]))); d.appendChild(el("span", null, x[1])); facts.appendChild(d);
    });
  }
  function renderHeat(h){
    var box = $("heat"); box.textContent = "";
    if(!h){ return; }
    var grid = h.connects, max = 0;
    grid.forEach(function(r){ r.forEach(function(v){ if(v > max) max = v; }); });
    var t = el("table"), tr = el("tr"); tr.appendChild(el("th", "d", ""));
    for(var hr = 0; hr < 24; hr++){ tr.appendChild(el("th", null, hr === 0 ? "12a" : hr < 12 ? hr + "a" : hr === 12 ? "12p" : (hr - 12) + "p")); }
    t.appendChild(tr);
    h.weekdays.forEach(function(d, i){
      var row = el("tr"); row.appendChild(el("th", "d", d));
      for(var x = 0; x < 24; x++){
        var v = grid[i][x], dials = h.dials[i][x];
        var lvl = !v ? 0 : Math.max(1, Math.ceil(5 * v / max));
        var td = el("td", "h" + lvl, v ? String(v) : "0");
        td.title = d + " " + x + ":00 — " + v + " reached of " + dials + " dials";
        row.appendChild(td);
      }
      t.appendChild(row);
    });
    box.appendChild(t);
    if(!max) box.appendChild(el("p", "mg-empty", "No one has picked up in this period yet."));
  }

  // ---- daily chart (inline SVG): dials bar with the interested share inside --
  function renderChart(series){
    var box = $("chart"), tip = $("tip"); box.textContent = ""; tip.hidden = true;
    var W = Math.max(320, Math.round(box.clientWidth || 1100)), H = W < 640 ? 200 : 240, padL = 34, padR = 10, padT = 12, padB = 26;
    var n = series.length || 1;
    var max = Math.max.apply(null, [1].concat(series.map(function(d){ return d.dials; })));
    var iw = (W - padL - padR) / n, bw = Math.max(2, Math.min(28, iw * 0.66));
    var s = svg("svg", {viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Dials and interested per day"});
    var steps = max <= 5 ? max : 4;
    for(var g = 0; g <= steps; g++){
      var val = Math.round(max * g / steps), y = padT + (H - padT - padB) * (1 - val / max);
      s.appendChild(svg("line", {x1: padL, x2: W - padR, y1: y, y2: y, "class": "grid"}));
      var tx = svg("text", {x: padL - 6, y: y + 4, "text-anchor": "end", "class": "ax"}); tx.textContent = val; s.appendChild(tx);
    }
    var every = Math.max(1, Math.ceil(n / Math.max(4, Math.floor((W - padL - padR) / 64))));
    series.forEach(function(d, i){
      var x = padL + i * iw + (iw - bw) / 2;
      var hD = (H - padT - padB) * d.dials / max, hI = (H - padT - padB) * d.interested / max;
      var yD = H - padB - hD, yI = H - padB - hI;
      if(d.dials) s.appendChild(svg("rect", {x: x, y: yD, width: bw, height: hD, rx: 3, "class": "b-d"}));
      if(d.interested) s.appendChild(svg("rect", {x: x, y: yI, width: bw, height: hI, rx: 3, "class": "b-i"}));
      if(i % every === 0 || i === n - 1){ var l = svg("text", {x: x + bw / 2, y: H - 8, "text-anchor": "middle", "class": "ax"}); l.textContent = dayLabel(d.day); s.appendChild(l); }
      if(d.dials === max && max > 0){ var lb = svg("text", {x: x + bw / 2, y: yD - 4, "text-anchor": "middle", "class": "lbl"}); lb.textContent = d.dials; s.appendChild(lb); }
      var hit = svg("rect", {x: padL + i * iw, y: padT, width: iw, height: H - padT - padB, "class": "hit"});
      hit.addEventListener("mousemove", function(ev){
        tip.textContent = "";
        tip.appendChild(el("b", null, dayLabel(d.day)));
        tip.appendChild(document.createElement("br"));
        tip.appendChild(el("span", null, d.dials + " dials · " + d.connects + " reached · " + d.interested + " interested · " + d.wins + " wins"));
        var r = box.getBoundingClientRect();
        tip.style.left = Math.min(ev.clientX - r.left + 12, r.width - 260) + "px"; tip.style.top = (ev.clientY - r.top - 44) + "px"; tip.hidden = false;
      });
      hit.addEventListener("mouseleave", function(){ tip.hidden = true; });
      s.appendChild(hit);
    });
    box.appendChild(s);
  }

  // ---- economics + lists ----------------------------------------------------
  function renderEcon(e){
    var w = e.window, p = e.period;
    $("econ-note").textContent = "$" + e.rate.toFixed(2) + "/hour · " + w.label + " (pay period " + p.label + " in the last row)";
    var rows = (w.vas || []).map(function(r){ return [r.va, r.hours.toFixed(1), r.dials, r.dials_per_hour == null ? "–" : r.dials_per_hour, money(r.cost), money(r.cost_per_dial), money(r.cost_per_connect), money(r.cost_per_interested), {text: money(r.cost_per_win), cls: r.cost_per_win == null ? "dim" : "hot"}]; });
    var t = w.totals, pt = p.totals;
    rows.push(["Everyone · " + w.label, t.hours.toFixed(1), t.dials, t.dials_per_hour == null ? "–" : t.dials_per_hour, money(t.cost), money(t.cost_per_dial), money(t.cost_per_connect), money(t.cost_per_interested), money(t.cost_per_win)]);
    rows.push(["Pay period " + p.label, pt.hours.toFixed(1), pt.dials, pt.dials_per_hour == null ? "–" : pt.dials_per_hour, money(pt.cost), money(pt.cost_per_dial), money(pt.cost_per_connect), money(pt.cost_per_interested), money(pt.cost_per_win)]);
    tableRows($("t-econ"), ["Caller", "Hours", "Dials", "Dials/hour", "Cost", "Per dial", "Per reach", "Per interested", "Per win"], rows, {total: true});
    $("k-hours").textContent = t.hours.toFixed(1);
    $("k-cpw").textContent = t.cost_per_win == null ? "–" : money(t.cost_per_win);
  }
  function renderLists(l){
    tableRows($("t-lists"), ["Imported", "Size", "Worked", "Dials", "Reached", "Interested", "Wins", "Top categories"],
      (l.lists || []).map(function(r){ return [dayLabel(r.day), r.size, r.worked + " · " + pct(r.worked_pct), r.dials, r.reach + " · " + pct(r.reach_rate), r.interested, {text: r.wins, cls: r.wins ? "hot" : ""}, {text: (r.categories || []).map(function(c){ return c.category + " " + c.n; }).join(", "), cls: "dim"}]; }),
      {empty: "No lists imported in this period."});
  }

  // ---- review queue + trend --------------------------------------------------
  var TAGS = ["opener", "discovery", "objections", "close", "compliance", "great-call"];
  var LBL = {opener: "Open", discovery: "Ask", objection: "Answer", close: "Close", compliance: "Notice"};
  function renderQueue(q){
    var box = $("rq"); box.textContent = "";
    $("rq-note").textContent = q.unreviewed ? (q.unreviewed + " unreviewed · lowest score first") : "Every scored call has been reviewed";
    if(!(q.queue || []).length){ box.appendChild(el("p", "mg-empty", "Nothing to review. Scores appear after copilot calls with a real conversation.")); return; }
    var wrap = el("div", "mg-rq");
    q.queue.forEach(function(s){
      var row = el("div", "mg-rq-row");
      var sc = el("div", "mg-rq-score");
      sc.appendChild(el("b", s.total < 12 ? "low" : null, s.total + " / 25"));
      sc.appendChild(el("span", "m", s.source === "claude" ? "Scored by Claude" : "Scored by rule"));
      var bars = el("div", "mg-rq-bars");
      ["opener", "discovery", "objection", "close", "compliance"].forEach(function(k){
        var v = s.scores[k] || 0, cell = el("div"), i = el("i", v <= 2 ? "low" : null), em = el("em"); em.style.width = (v * 20) + "%";
        i.appendChild(em); cell.appendChild(i); cell.appendChild(el("small", null, LBL[k] + " " + v)); bars.appendChild(cell);
      });
      sc.appendChild(bars); row.appendChild(sc);
      var body = el("div", "mg-rq-body");
      var who = el("div", "who"); who.appendChild(el("b", null, s.company || "Unknown company")); who.appendChild(document.createTextNode(" · " + (s.va_name || "—") + " · " + new Date(s.created_at + "Z").toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"})));
      body.appendChild(who);
      var x = el("div", "mg-rq-x");
      (s.excerpt || []).forEach(function(l){ var d = el("div", l.track === "them" ? "them" : "you"); d.appendChild(el("b", null, l.track === "them" ? "Them" : "VA")); d.appendChild(document.createTextNode(l.text)); x.appendChild(d); });
      body.appendChild(x);
      if(s.top_fix){ var f = el("div", "mg-rq-fix"); f.appendChild(el("b", null, "Coach on: ")); f.appendChild(document.createTextNode(s.top_fix)); body.appendChild(f); }
      row.appendChild(body);
      var form = el("form", "mg-rq-form");
      var ta = el("textarea"); ta.placeholder = "Note for " + (s.va_name || "the caller") + " — what to do differently next time"; form.appendChild(ta);
      var tags = el("div", "tags"), picked = {};
      TAGS.forEach(function(t){ var lab = el("label", null, t); var inp = el("input"); inp.type = "checkbox"; lab.appendChild(inp);
        lab.addEventListener("click", function(ev){ ev.preventDefault(); picked[t] = !picked[t]; lab.classList.toggle("on", !!picked[t]); }); tags.appendChild(lab); });
      form.appendChild(tags);
      var btn = el("button", null, "Mark reviewed"); btn.type = "submit"; form.appendChild(btn);
      form.addEventListener("submit", function(ev){
        ev.preventDefault(); btn.disabled = true;
        post("/api/va/coaching/review", {call_sid: s.call_sid, note: ta.value, tags: Object.keys(picked).filter(function(k){ return picked[k]; })}).then(function(r){
          if(r.status !== 200){ btn.disabled = false; say((r.body && r.body.error) || "Couldn't save the review."); return; }
          form.textContent = ""; form.appendChild(el("span", "mg-rq-done", "Reviewed — " + (s.va_name || "the caller") + " sees your note on the card."));
          loadTrend();
        }).catch(function(){ btn.disabled = false; say("No connection — the review didn't save."); });
      });
      row.appendChild(form);
      wrap.appendChild(row);
    });
    box.appendChild(wrap);
  }
  function renderTrend(t){
    var rows = [];
    Object.keys(t.vas || {}).sort().forEach(function(name){
      (t.vas[name] || []).forEach(function(w){ rows.push([name, dayLabel(w.week), w.n, w.opener, w.discovery, w.objection, w.close, w.compliance, {text: w.total, cls: w.total < 12 ? "hot" : ""}]); });
    });
    tableRows($("t-trend"), ["Caller", "Week of", "Calls scored", "Open", "Ask", "Answer", "Close", "Notice", "Total"], rows, {empty: "No scored calls yet."});
  }

  // ---- load ------------------------------------------------------------------
  function load(){
    say("");
    $("stamp").textContent = "Updating…";
    var body = {days: days}; if(va) body.va = va;
    Promise.all([
      post("/api/va/analytics/funnel", body), post("/api/va/analytics/timeseries", body),
      post("/api/va/analytics/economics", {days: days}), post("/api/va/analytics/lists", {days: Math.max(days, 90)}),
      post("/api/va/coaching/review-queue", {days: Math.max(days, 30), va: va})
    ]).then(function(rs){
      var f = rs[0], ts = rs[1], ec = rs[2], ls = rs[3], rq = rs[4];
      if(f.status === 401){ tool.hidden = true; gate.hidden = false; return; }
      if(f.status === 403 || ec.status === 403){ say("This page needs a manager login. You can still see your own numbers on the desk under Hours → Stats."); }
      if(f.status === 200) renderFunnel(f.body);
      if(ts.status === 200) renderChart(ts.body.series || []);
      if(ec.status === 200) renderEcon(ec.body);
      if(ls.status === 200) renderLists(ls.body);
      if(rq.status === 200) renderQueue(rq.body);
      $("stamp").textContent = (f.body && f.body.label ? f.body.label + " · " : "") + "updated " + new Date().toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
    }).catch(function(){ say("No connection — couldn't load the desk numbers."); $("stamp").textContent = ""; });
    loadTrend();
  }
  function loadTrend(){
    post("/api/va/coaching/trend", {days: Math.max(days, 56), va: va}).then(function(r){ if(r.status === 200) renderTrend(r.body); }).catch(function(){});
  }
  $("period").addEventListener("click", function(e){
    var b = e.target.closest("button"); if(!b) return;
    days = parseInt(b.dataset.d, 10) || 30;
    Array.prototype.forEach.call($("period").querySelectorAll("button"), function(x){ x.classList.toggle("is-on", x === b); });
    load();
  });
  $("va-pick").addEventListener("change", function(){ va = this.value; load(); });
  load();
})();
