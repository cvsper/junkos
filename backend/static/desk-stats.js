/* Desk analytics page — reads POST /api/va/analytics/desk. Same sign-in
   plumbing as manager.js: a desk JWT, or the shared passcode + VA name. */
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
  function money(v){ return v == null ? "–" : "$" + Number(v).toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0}); }
  function pct(v){ return v == null ? "–" : v + "%"; }
  function num(v){ return v == null ? "–" : String(v); }
  function secs(v){ if(v == null) return "–"; if(v < 90) return Math.round(v) + "s"; if(v < 3600) return Math.round(v / 60) + " min"; return (v / 3600).toFixed(1) + " h"; }
  function dayLabel(iso){ var d = new Date(iso + "T12:00:00"); return d.toLocaleDateString([], {month: "short", day: "numeric"}); }
  var LABEL = {desk: "Desk line", google: "Google Local Services", meta: "Meta ads", maya: "Maya", unknown: "Unknown",
               answered_by_human: "Answered by a person", to_maya: "Went to Maya", voicemail: "Voicemail", missed: "Missed", ringing: "Still ringing / unknown",
               booked: "Booked", quoted: "Quoted", callback: "Callback set", not_fit: "Not a fit", spam: "Spam", none: "No outcome logged",
               phone: "Phone (desk)", web: "Web", maya_ch: "Maya", waitlist: "Waitlist", other: "Other"};

  var gate = $("gate"), tool = $("tool"), err = $("err");
  var period = {days: 30}, va = "";
  function say(msg){ err.textContent = msg; err.hidden = !msg; }

  function tableRows(table, head, rows, opts){
    opts = opts || {};
    table.textContent = "";
    if(!rows.length){ var tr0 = el("tr"); var td0 = el("td", "dim", opts.empty || "Nothing in this period."); td0.colSpan = head.length; tr0.appendChild(td0); table.appendChild(tr0); return; }
    var th = el("tr"); head.forEach(function(h){ th.appendChild(el("th", null, h)); }); table.appendChild(th);
    rows.forEach(function(r){
      var tr = el("tr", r.tot ? "tot" : null);
      r.cells.forEach(function(c, i){
        var td = el("td", c.cls || null);
        if(c.bar != null){ var b = el("i", "bar"); b.style.width = Math.max(2, Math.round(60 * c.bar)) + "px"; td.appendChild(b); }
        td.appendChild(document.createTextNode(c.v == null ? "–" : c.v));
        if(c.sub){ td.appendChild(el("span", "sub", c.sub)); }
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
  }
  function facts(box, items){
    box.textContent = "";
    items.forEach(function(it){ var f = el("div", "mg-fact"); var b = el("b", it.cls || null, it.v); f.appendChild(b); f.appendChild(el("span", null, it.l)); box.appendChild(f); });
  }

  // ---- chart: calls (blue), answered by a person (accent), bookings (green) --
  function renderChart(series){
    var box = $("chart"), tip = $("tip"); box.textContent = ""; tip.hidden = true;
    if(!series || !series.length){ box.appendChild(el("div", "mg-empty", "No days in this period.")); return; }
    var W = Math.max(320, Math.round(box.clientWidth || 1100)), H = W < 640 ? 200 : 240, padL = 34, padR = 10, padT = 12, padB = 26;
    var n = series.length;
    var max = Math.max.apply(null, [1].concat(series.map(function(d){ return Math.max(d.calls, d.bookings); })));
    var iw = (W - padL - padR) / n, bw = Math.max(2, Math.min(22, iw * 0.6));
    var s = svg("svg", {viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Calls, answered calls and bookings per day"});
    var steps = max <= 5 ? max : 4;
    for(var g = 0; g <= steps; g++){
      var val = Math.round(max * g / steps), y = padT + (H - padT - padB) * (1 - val / max);
      s.appendChild(svg("line", {x1: padL, x2: W - padR, y1: y, y2: y, "class": "grid"}));
      var tx = svg("text", {x: padL - 6, y: y + 4, "text-anchor": "end", "class": "ax"}); tx.textContent = val; s.appendChild(tx);
    }
    var every = Math.max(1, Math.ceil(n / Math.max(4, Math.floor((W - padL - padR) / 64))));
    var plot = H - padT - padB;
    series.forEach(function(d, i){
      var x = padL + i * iw + (iw - bw) / 2;
      var hC = plot * d.calls / max, hH = plot * d.human / max, hB = plot * d.bookings / max;
      if(d.calls) s.appendChild(svg("rect", {x: x, y: H - padB - hC, width: bw, height: hC, rx: 3, "class": "b-d"}));
      if(d.human) s.appendChild(svg("rect", {x: x, y: H - padB - hH, width: bw, height: hH, rx: 3, "class": "b-i"}));
      if(d.bookings) s.appendChild(svg("rect", {x: x + bw * 0.55, y: H - padB - hB, width: bw * 0.45, height: hB, rx: 2, "class": "b-b"}));
      if(i % every === 0 || i === n - 1){ var l = svg("text", {x: x + bw / 2, y: H - 8, "text-anchor": "middle", "class": "ax"}); l.textContent = dayLabel(d.day); s.appendChild(l); }
      var hit = svg("rect", {x: padL + i * iw, y: padT, width: iw, height: plot, "class": "hit"});
      hit.addEventListener("mousemove", function(ev){
        tip.textContent = "";
        tip.appendChild(el("b", null, dayLabel(d.day)));
        tip.appendChild(document.createElement("br"));
        tip.appendChild(el("span", null, d.calls + " calls · " + d.human + " answered · " + d.bookings + " booked" + (d.revenue ? " · " + money(d.revenue) + " paid" : "")));
        var r = box.getBoundingClientRect();
        tip.style.left = Math.min(ev.clientX - r.left + 12, r.width - 260) + "px"; tip.style.top = (ev.clientY - r.top - 44) + "px"; tip.hidden = false;
      });
      hit.addEventListener("mouseleave", function(){ tip.hidden = true; });
      s.appendChild(hit);
    });
    box.appendChild(s);
  }

  function render(r){
    var ib = r.inbound, sp = r.speed, mgr = !!r.manager;
    document.querySelectorAll("[data-mgr]").forEach(function(n){ n.hidden = !mgr; });
    $("mgr-link").hidden = !mgr;
    $("stamp").textContent = r.label + (r.va ? " · " + r.va : "");

    $("k-calls").textContent = num(ib.calls);
    $("k-human").textContent = ib.human_rate == null ? "–" : ib.human_rate + "%";
    $("k-speed").textContent = secs(sp.median_seconds);
    $("k-booked").textContent = num(ib.booked);
    if(mgr && r.bookings){ $("k-rev").textContent = money(r.bookings.revenue); }
    if(mgr && r.haulers){ var ns = $("k-noshow"); ns.textContent = num(r.haulers.no_shows); ns.classList.toggle("hot", r.haulers.no_shows > 0); }

    renderChart(r.series);

    var maxS = Math.max.apply(null, [1].concat(ib.by_source.map(function(x){ return x.calls; })));
    tableRows($("t-source"), ["Number dialled", "Calls", "Share"], ib.by_source.map(function(x){
      return {cells: [{v: LABEL[x.source] || x.source}, {v: x.calls, bar: x.calls / maxS}, {v: pct(ib.calls ? Math.round(1000 * x.calls / ib.calls) / 10 : null), cls: "dim"}]};
    }));
    $("disp-note").textContent = ib.in_hours + " in hours · " + ib.after_hours + " after hours";
    var disp = Object.keys(ib.by_disposition).filter(function(k){ return ib.by_disposition[k]; }).map(function(k){
      return {cells: [{v: LABEL[k] || k}, {v: ib.by_disposition[k]}, {v: pct(ib.calls ? Math.round(1000 * ib.by_disposition[k] / ib.calls) / 10 : null), cls: "dim"}]};
    });
    var outs = Object.keys(ib.by_outcome).filter(function(k){ return ib.by_outcome[k] && k !== "none"; }).map(function(k){
      return {cells: [{v: "→ " + (LABEL[k] || k), cls: "dim"}, {v: ib.by_outcome[k], cls: k === "booked" ? "hot" : null}, {v: "", cls: "dim"}]};
    });
    tableRows($("t-disp"), ["Disposition", "Calls", "Share"], disp.concat(outs));

    facts($("speed"), [
      {v: secs(sp.median_seconds), l: "Median time to a person", cls: sp.median_seconds != null && sp.median_seconds <= sp.target_seconds ? "ok" : (sp.median_seconds != null ? "warn" : null)},
      {v: secs(sp.p90_seconds), l: "Slowest 10% took"},
      {v: pct(sp.within_target_pct), l: "Inside 2 minutes"},
      {v: num(sp.untouched), l: "Never touched", cls: sp.untouched > 0 ? "warn" : null}
    ]);

    var maxV = Math.max.apply(null, [1].concat(ib.by_va.map(function(x){ return x.answered; })));
    tableRows($("t-va"), ["Person", "Answered", "Booked", "Quoted", "Book rate", "Talk time"], ib.by_va.map(function(x){
      return {cells: [{v: x.va}, {v: x.answered, bar: x.answered / maxV}, {v: x.booked, cls: x.booked ? "hot" : null}, {v: x.quoted}, {v: pct(x.book_rate)}, {v: secs(x.seconds), cls: "dim"}]};
    }), {empty: "No inbound calls answered in this period."});

    if(mgr && r.bookings){
      var b = r.bookings;
      $("book-note").textContent = b.jobs + " booked · " + b.paid + " paid" + (b.pay_rate != null ? " (" + b.pay_rate + "%)" : "");
      facts($("money"), [
        {v: money(b.revenue), l: "Paid revenue", cls: b.revenue ? "ok" : null},
        {v: b.avg_ticket == null ? "–" : money(b.avg_ticket), l: "Average ticket"},
        {v: money(b.dump_fees), l: "Dump fees passed to haulers"},
        {v: b.refunded ? money(b.refunded) : "$0", l: "Refunded", cls: b.refunded ? "warn" : null}
      ]);
      tableRows($("t-channel"), ["Channel", "Booked", "Paid", "Revenue"], b.by_channel.map(function(x){
        return {cells: [{v: LABEL[x.channel === "maya" ? "maya_ch" : x.channel] || x.channel}, {v: x.jobs}, {v: x.paid}, {v: money(x.revenue)}]};
      }));
    }
    if(mgr && r.haulers){
      var h = r.haulers;
      $("haul-note").textContent = h.assigned + " jobs with a hauler on the calendar";
      facts($("haulers"), [
        {v: pct(h.confirm_rate), l: "Confirmed before the job", cls: h.confirm_rate != null && h.confirm_rate < 80 ? "warn" : null},
        {v: num(h.no_shows), l: "No-shows", cls: h.no_shows ? "warn" : null},
        {v: num(h.completed), l: "Completed"},
        {v: h.owed_today ? money(h.owed_today.total) : "–", l: h.owed_today ? "Owed today (" + h.owed_today.count + ")" : "Owed today", cls: h.owed_today && h.owed_today.count ? "warn" : null}
      ]);
      tableRows($("t-hauler"), ["Hauler", "Jobs", "Confirmed", "Completed"], h.by_hauler.map(function(x){
        return {cells: [{v: x.name}, {v: x.jobs}, {v: pct(x.confirm_rate), cls: x.confirm_rate != null && x.confirm_rate < 80 ? "hot" : null}, {v: x.completed}]};
      }), {empty: "No hauler jobs on the calendar in this period."});
    }
    if(mgr){
      var m = r.maya;
      if(m){
        $("maya-note").textContent = m.calls + " calls · avg " + secs(m.avg_seconds) + (m.under_20s ? " · " + m.under_20s + " hung up under 20s" : "");
        facts($("maya"), [
          {v: num(m.calls), l: "Calls Maya took"},
          {v: pct(m.quote_rate), l: "Got a price"},
          {v: num(m.booked), l: "Booked by Maya", cls: m.booked ? "ok" : null},
          {v: num(m.lost_after_quote), l: "Priced, didn't book", cls: m.lost_after_quote ? "warn" : null}
        ]);
      } else { $("maya").textContent = ""; $("maya").appendChild(el("div", "mg-empty", "Maya's call log isn't available.")); }
      var cls = r.classes || [];
      var STATUS = {assigned: "Not done", completed: "Done", waived: "Waived"};
      tableRows($("t-classes"), ["Person", "Week", "Calls", "Avg / 25", "Focus", "Status", "Quiz", "Her one line"], cls.map(function(x){
        var late = x.status === "assigned" && x.due_at && new Date(x.due_at) < new Date();
        return {cells: [{v: x.va}, {v: x.week, cls: "dim"}, {v: x.calls}, {v: x.avg_total == null ? "–" : x.avg_total},
                        {v: x.weakest || "–", cls: "dim"}, {v: late ? "Overdue" : (STATUS[x.status] || x.status), cls: late ? "hot" : (x.status === "completed" ? null : "dim")},
                        {v: x.quiz == null ? "–" : x.quiz + "/" + x.quiz_total}, {v: x.reflection || "", cls: "dim"}]};
      }), {empty: "No classes yet — the first one builds Friday at 5pm from this week's scored calls."});
      var hr = r.hours;
      if(hr){
        $("hours-note").textContent = hr.hours + " h · " + money(hr.cost) + " at $" + hr.rate.toFixed(2) + "/h";
        tableRows($("t-hours"), ["Person", "Hours", "Cost"], hr.by_va.map(function(x){ return {cells: [{v: x.va}, {v: x.hours}, {v: money(x.hours * hr.rate)}]}; }), {empty: "Nobody clocked in during this period."});
      }
    }
    var o = r.outbound;
    if(o){
      facts($("outbound"), [
        {v: num(o.dials), l: "Dials"}, {v: num(o.connects), l: "Reached"},
        {v: num(o.interested), l: "Interested"}, {v: num(o.wins), l: "Wins", cls: o.wins ? "ok" : null}
      ]);
    } else { $("outbound").textContent = ""; $("outbound").appendChild(el("div", "mg-empty", "No outbound data.")); }
  }

  function load(){
    say("");
    var body = {va: va}; if(period.period) body.period = period.period; else body.days = period.days;
    post("/api/va/analytics/desk", body).then(function(r){
      if(r.status === 401){ tool.hidden = true; gate.hidden = false; return; }
      if(r.status !== 200){ say((r.body && r.body.error) || "Couldn't load analytics."); return; }
      render(r.body);
      var pick = $("va-pick"), wrap = $("va-wrap");
      if(r.body.manager){
        wrap.hidden = false;
        var names = {}; (r.body.inbound.by_va || []).forEach(function(x){ names[x.va] = 1; }); ((r.body.hours || {}).by_va || []).forEach(function(x){ names[x.va] = 1; });
        var cur = pick.value; pick.textContent = "";
        var o0 = el("option", null, "Everyone"); o0.value = ""; pick.appendChild(o0);
        Object.keys(names).sort().forEach(function(n){ var o = el("option", null, n); o.value = n; pick.appendChild(o); });
        pick.value = cur;
      }
    }).catch(function(){ say("Couldn't reach the desk. Try again in a moment."); });
  }

  function init(){
    if(!jwt() && !code()){ gate.hidden = false; return; }
    tool.hidden = false;
    var m = me(); $("who").textContent = (m && m.name) || vaName() || "";
    $("period").addEventListener("click", function(e){
      var b = e.target.closest("button"); if(!b) return;
      document.querySelectorAll("#period button").forEach(function(x){ x.classList.toggle("is-on", x === b); });
      period = b.dataset.p ? {period: b.dataset.p} : {days: Number(b.dataset.d)};
      load();
    });
    $("va-pick").addEventListener("change", function(){ va = this.value; load(); });
    var t; window.addEventListener("resize", function(){ clearTimeout(t); t = setTimeout(load, 250); });
    load();
  }
  init();
})();
