/* Coach tab. Renders /api/va/coach/home into the page sections, runs the
   playbook search, the chat coach, and opens classes through desk-class.js.
   Styles: /static/coach.css. */
(function(){
  "use strict";
  var JWT_KEY = "umuve_desk_jwt", ME_KEY = "umuve_desk_me", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name", CHAT_KEY = "umuve_coach_chat";
  function ls(k){ try { return localStorage.getItem(k) || ""; } catch(e){ return ""; } }
  function me(){ try { return JSON.parse(ls(ME_KEY) || "null"); } catch(e){ return null; } }
  function vaName(){ var m = me(); return (m && m.name) || ls(VA_KEY) || ""; }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(ls(JWT_KEY)) headers["Authorization"] = "Bearer " + ls(JWT_KEY);
    else { body.code = ls(KEY); body.va_name = vaName(); }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }
  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  function clear(n){ while(n.firstChild) n.removeChild(n.firstChild); }
  function when(iso){
    if(!iso) return "";
    var d = new Date(iso.indexOf("Z") > 0 || /[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
    var now = new Date(), diff = (now - d) / 36e5;
    if(diff < 24 && d.getDate() === now.getDate()) return d.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
    return d.toLocaleDateString([], {month: "short", day: "numeric"});
  }
  var LABEL = {opener: "opener", discovery: "discovery", objection: "objections", close: "close", compliance: "notice"};
  var COLORS = {opener: "#3B6FD9", discovery: "#1F9D55", objection: "#C52222", close: "#B8780C", compliance: "#26272C"};

  var gate = document.getElementById("gate"), tool = document.getElementById("tool");
  var DATA = null, VA = null;

  // ---------------------------------------------------------------- gate
  function showGate(msg){ tool.hidden = true; gate.hidden = false; var e = document.getElementById("gate-err"); if(msg){ e.textContent = msg; e.hidden = false; } }
  function showTool(){ gate.hidden = true; tool.hidden = false; }
  document.getElementById("gate-form").addEventListener("submit", function(ev){
    ev.preventDefault();
    var name = document.getElementById("va-name").value.trim(), code = document.getElementById("code").value.trim();
    if(!name || !code){ showGate("Your first name and the access code, please."); return; }
    try { localStorage.setItem(KEY, code); localStorage.setItem(VA_KEY, name); } catch(e){}
    load();
  });

  // ---------------------------------------------------------------- load
  function load(va){
    var body = va ? {va: va} : {};
    post("/api/va/coach/home", body).then(function(r){
      if(r.status === 401){ showGate(ls(KEY) ? "That code didn't work." : ""); return; }
      if(r.status !== 200){ showGate((r.body && r.body.error) || "Couldn't load the coach."); return; }
      DATA = r.body; VA = DATA.va; showTool();
      document.getElementById("who").textContent = DATA.va || "";
      renderVaPicker(); renderWeek(); renderClass(); renderTrend(); renderCalls(); renderPlaybook(); renderChips(); renderHistory();
    }).catch(function(){ showGate("Couldn't reach the desk."); });
  }

  function renderVaPicker(){
    var wrap = document.getElementById("co-va"), sel = document.getElementById("co-va-sel");
    if(!DATA.manager || !(DATA.vas || []).length){ wrap.hidden = true; return; }
    clear(sel);
    DATA.vas.forEach(function(v){ var o = el("option", null, v); o.value = v; if(v === VA) o.selected = true; sel.appendChild(o); });
    wrap.hidden = false;
    sel.onchange = function(){ load(sel.value); };
  }

  // ---------------------------------------------------------------- week
  function renderWeek(){
    var w = DATA.week, box = document.getElementById("co-week"); clear(box);
    if(!w){ box.appendChild(el("div", "co-empty", "No numbers yet this week.")); return; }
    function tile(v, label, small, dim){
      var k = el("div", "co-k"); var b = el("b", dim ? "dim" : null, v == null ? "–" : String(v)); k.appendChild(b); k.appendChild(el("span", null, label)); if(small) k.appendChild(el("small", null, small)); return k;
    }
    box.appendChild(tile(w.dials, "Dials this week"));
    box.appendChild(tile(w.connects, "Reached", w.reach_rate != null ? w.reach_rate + "% reach" : null));
    box.appendChild(tile(w.interested, "Interested"));
    box.appendChild(tile(w.wins, "Wins", w.conversion != null ? w.conversion + "% of dials" : null));
    box.appendChild(tile(w.hours != null ? w.hours + "h" : null, "On the clock"));
    var st = el("div", "co-k"); st.appendChild(el("b", null, String(w.streak || 0))); st.appendChild(el("span", null, (w.streak === 1 ? "day" : "days") + " in a row dialing"));
    var sp = el("div", "co-spark"); var max = Math.max.apply(null, (w.series || []).map(function(r){ return r.dials; }).concat([1]));
    (w.series || []).slice(-14).forEach(function(r, i, arr){
      var bar = el("i"); bar.style.height = Math.max(2, Math.round(r.dials / max * 34)) + "px";
      if(i === arr.length - 1) bar.className = "today"; else if(r.dials > 0) bar.className = "hot";
      bar.title = r.day + ": " + r.dials + " dials"; sp.appendChild(bar);
    });
    st.appendChild(sp); box.appendChild(st);
  }

  // ---------------------------------------------------------------- class + focus
  function statusPill(k){
    var c = k.current;
    if(!c) return el("span", "co-status", "No class this week yet");
    if(c.status === "completed") return el("span", "co-status done", "Completed · " + (c.quiz_score != null ? c.quiz_score + "/" + c.quiz_total : "done"));
    if(c.status === "waived") return el("span", "co-status", "Waived by your manager");
    if(k.overdue) return el("span", "co-status overdue", "Overdue · due " + when(c.due_at));
    return el("span", "co-status due", "Due " + when(c.due_at));
  }
  function renderClass(){
    var box = document.getElementById("co-class"), k = DATA.klass || {}, f = DATA.focus; clear(box);
    var h = el("div", "co-h"); h.appendChild(el("h2", null, "This week's class")); h.appendChild(statusPill(k)); box.appendChild(h);
    if(!k.current && !f){
      box.appendChild(el("p", "co-sum", "Your first class arrives Friday at 5pm, built from this week's scored calls. Until then, the playbook and the coach below are yours."));
      return;
    }
    var src = k.current || (k.history || [])[0];
    if(f && f.title) box.appendChild(el("h3", "co-title", f.title));
    if(f && f.summary) box.appendChild(el("p", "co-sum", f.summary));
    if(src && src.dims){
      var strip = el("div", "co-dims");
      Object.keys(src.dims).forEach(function(d){ var it = el("div", "co-dim" + (d === src.weakest ? " is-weak" : "")); it.appendChild(el("b", null, String(src.dims[d]))); it.appendChild(el("span", null, LABEL[d] || d)); strip.appendChild(it); });
      box.appendChild(strip);
    }
    if(f && f.drill){
      var line = el("div", "co-line"); line.appendChild(el("div", "lbl", "Your line to practise this week")); line.appendChild(el("p", null, "“" + f.drill.line + "”"));
      if(f.drill.why) line.appendChild(el("div", "why", f.drill.why)); box.appendChild(line);
    }
    if(f && f.fixes && f.fixes.length){
      var ul = el("ul", "co-fixes");
      f.fixes.forEach(function(x){ var li = el("li", null, x.point || ""); if(x.say_instead) li.appendChild(el("em", null, "Say instead: " + x.say_instead)); ul.appendChild(li); });
      box.appendChild(ul);
    }
    var btns = el("div", "co-btns");
    if(k.current){
      var open = el("button", "pill dark", k.current.status === "assigned" ? "Take the class" : "Open the class"); open.type = "button";
      open.addEventListener("click", function(){ openClass(k.current, k.current.status !== "assigned", k.overdue); }); btns.appendChild(open);
    }
    var ask = el("button", "pill", "Ask the coach about this"); ask.type = "button";
    ask.addEventListener("click", function(){ sendChat("My weekly focus is " + (f ? f.label : "my calls") + ". Give me one drill I can do in the next 5 minutes."); }); btns.appendChild(ask);
    box.appendChild(btns);
  }
  function openClass(cls, readOnly, overdue){
    if(window.__deskClass && window.__deskClass.open){ window.__deskClass.open(cls, {readOnly: !!readOnly, overdue: !!overdue, onDone: function(){ load(VA); }}); }
  }

  // ---------------------------------------------------------------- trend
  function renderTrend(){
    var t = DATA.trend, svg = document.getElementById("co-trend-svg"), leg = document.getElementById("co-legend"); clear(svg); clear(leg);
    var weeks = (t && t.weeks) || [];
    if(weeks.length < 2){ var tx = document.createElementNS("http://www.w3.org/2000/svg", "text"); tx.setAttribute("x", 8); tx.setAttribute("y", 80); tx.setAttribute("fill", "#8A8B92"); tx.setAttribute("font-size", 13); tx.textContent = weeks.length ? "One week scored so far — the line starts next week." : "No scored calls yet."; svg.appendChild(tx); return; }
    var W = 600, H = 150, pad = 14, n = weeks.length;
    function x(i){ return pad + i * (W - 2 * pad) / (n - 1); }
    function y(v){ return H - pad - (v / 5) * (H - 2 * pad); }
    [1, 2, 3, 4, 5].forEach(function(g){ var l = document.createElementNS("http://www.w3.org/2000/svg", "line"); l.setAttribute("x1", pad); l.setAttribute("x2", W - pad); l.setAttribute("y1", y(g)); l.setAttribute("y2", y(g)); l.setAttribute("stroke", "rgba(23,24,28,.08)"); svg.appendChild(l); });
    (t.dimensions || []).forEach(function(d){
      var pts = weeks.map(function(w, i){ return x(i).toFixed(1) + "," + y(w[d] || 0).toFixed(1); }).join(" ");
      var p = document.createElementNS("http://www.w3.org/2000/svg", "polyline"); p.setAttribute("points", pts); p.setAttribute("fill", "none"); p.setAttribute("stroke", COLORS[d] || "#888"); p.setAttribute("stroke-width", 2); p.setAttribute("stroke-linejoin", "round"); svg.appendChild(p);
      var last = weeks[n - 1]; var c = document.createElementNS("http://www.w3.org/2000/svg", "circle"); c.setAttribute("cx", x(n - 1)); c.setAttribute("cy", y(last[d] || 0)); c.setAttribute("r", 3.5); c.setAttribute("fill", COLORS[d] || "#888"); svg.appendChild(c);
      var li = el("span"); var sw = el("i"); sw.style.background = COLORS[d] || "#888"; li.appendChild(sw); li.appendChild(document.createTextNode((LABEL[d] || d) + " " + (last[d] != null ? last[d] : "–"))); leg.appendChild(li);
    });
  }

  // ---------------------------------------------------------------- calls
  function renderCalls(){
    var box = document.getElementById("co-calls"), c = DATA.calls || {calls: []}; clear(box);
    var h = el("div", "co-h"); h.appendChild(el("h2", null, "Calls to review"));
    h.appendChild(el("span", "co-note", (c.total || 0) + " scored in " + (c.days || 14) + " days" + (c.avg_total != null ? " · averaging " + c.avg_total + "/25" : "") + (c.reviewed ? " · " + c.reviewed + " reviewed by your manager" : "")));
    box.appendChild(h);
    if(!c.calls.length){ box.appendChild(el("div", "co-empty", "No scored calls yet. A call is scored once it has a real conversation on the transcript (about six lines).")); return; }
    var rows = el("div", "co-rows");
    c.calls.forEach(function(p){
      var row = el("button", "co-row"); row.type = "button";
      var sc = el("div", "sc" + (p.total >= 18 ? " good" : p.total <= 11 ? " low" : ""), String(p.total)); row.appendChild(sc);
      var t = el("div", "t"); var b = el("b", null, p.company || "Unknown business"); if(p.reviewed) b.appendChild(el("span", "co-tag rev", "reviewed")); if(p.category) b.appendChild(el("span", "co-tag", p.category)); t.appendChild(b);
      t.appendChild(el("span", null, p.top_fix ? "Next time: " + p.top_fix : (p.strengths && p.strengths[0]) || "")); row.appendChild(t);
      row.appendChild(el("span", "when", when(p.at)));
      var det = el("div", "co-detail"); det.hidden = true;
      var strip = el("div", "co-dims");
      Object.keys(p.scores || {}).forEach(function(d){ var it = el("div", "co-dim"); it.appendChild(el("b", null, String(p.scores[d]))); it.appendChild(el("span", null, LABEL[d] || d)); strip.appendChild(it); });
      det.appendChild(strip);
      if(p.strengths && p.strengths.length){ det.appendChild(el("h4", null, "What worked")); var u = el("ul"); p.strengths.forEach(function(s){ u.appendChild(el("li", null, s)); }); det.appendChild(u); }
      if(p.fixes && p.fixes.length){ det.appendChild(el("h4", null, "What to fix")); var u2 = el("ul"); p.fixes.forEach(function(s){ u2.appendChild(el("li", null, s)); }); det.appendChild(u2); }
      if(p.review_note){ var nb = el("div", "co-note-box"); nb.appendChild(el("b", null, (p.reviewed_by || "Your manager") + ": ")); nb.appendChild(document.createTextNode(p.review_note)); if(p.review_tags && p.review_tags.length) nb.appendChild(el("div", null, "Tags: " + p.review_tags.join(", "))); det.appendChild(nb); }
      if(p.excerpt && p.excerpt.length){ det.appendChild(el("h4", null, "How it opened")); var ex = el("div", "co-x"); p.excerpt.forEach(function(l){ var d = el("div"); d.appendChild(el("b", null, (l.track === "va" ? "You" : "Them") + ": ")); d.appendChild(document.createTextNode(l.text)); ex.appendChild(d); }); det.appendChild(ex); }
      var btns = el("div", "co-btns");
      if(p.recording_url){ var a = el("a", "pill", "Listen"); a.href = p.recording_url; a.target = "_blank"; a.rel = "noopener"; btns.appendChild(a); }
      if(p.link){ var a2 = el("a", "pill", "Open the card"); a2.href = p.link; btns.appendChild(a2); }
      var ask = el("button", "pill dark", "Ask the coach about this call"); ask.type = "button";
      ask.addEventListener("click", function(){ sendChat("On my call with " + (p.company || "this business") + " I scored " + p.total + "/25" + (p.top_fix ? " and the note says: " + p.top_fix : "") + ". What exactly should I say differently next time?"); });
      btns.appendChild(ask); det.appendChild(btns);
      row.addEventListener("click", function(){ det.hidden = !det.hidden; });
      rows.appendChild(row); rows.appendChild(det);
    });
    box.appendChild(rows);
  }

  // ---------------------------------------------------------------- history
  function renderHistory(){
    var box = document.getElementById("co-history"), hist = (DATA.klass && DATA.klass.history) || []; clear(box);
    var h = el("div", "co-h"); h.appendChild(el("h2", null, "Past classes")); h.appendChild(el("span", "co-note", hist.length ? "tap one to reread it" : "")); box.appendChild(h);
    if(!hist.length){ box.appendChild(el("div", "co-empty", "Nothing yet — classes collect here week by week.")); return; }
    var rows = el("div", "co-rows");
    hist.forEach(function(c){
      var row = el("button", "co-row"); row.type = "button";
      var sc = el("div", "sc" + (c.avg_total >= 18 ? " good" : c.avg_total != null && c.avg_total <= 11 ? " low" : ""), c.avg_total == null ? "–" : String(c.avg_total)); row.appendChild(sc);
      var t = el("div", "t"); var b = el("b", null, (c.lesson && c.lesson.title) || "Week of " + c.week_start); b.appendChild(el("span", "co-tag" + (c.status === "completed" ? " rev" : ""), c.status)); t.appendChild(b);
      t.appendChild(el("span", null, "Week of " + c.week_start + " · " + c.calls + " calls · focus " + (LABEL[c.weakest] || c.weakest || "–") + (c.quiz_score != null ? " · quiz " + c.quiz_score + "/" + c.quiz_total : "")));
      row.appendChild(t); row.appendChild(el("span", "when", c.completed_at ? "done " + when(c.completed_at) : ""));
      row.addEventListener("click", function(){ openClass(c, c.status !== "assigned", false); });
      rows.appendChild(row);
    });
    box.appendChild(rows);
  }

  // ---------------------------------------------------------------- playbook
  var PB_TAB = "objections";
  function renderPlaybook(){
    var pb = DATA.playbook, box = document.getElementById("co-pb"); clear(box);
    if(!pb){ box.appendChild(el("div", "co-empty", "The playbook couldn't load.")); return; }
    var q = (document.getElementById("co-q").value || "").trim().toLowerCase();
    function hit(){ for(var i = 0; i < arguments.length; i++){ if(String(arguments[i] || "").toLowerCase().indexOf(q) >= 0) return true; } return !q; }
    function card(k, say, reply, list){
      var c = el("div", "co-card"); var kk = el("div", "k", k); var cp = el("button", "co-copy", "Copy"); cp.type = "button"; cp.addEventListener("click", function(){ try { navigator.clipboard.writeText(reply || say || (list || []).join("\n")); cp.textContent = "Copied"; setTimeout(function(){ cp.textContent = "Copy"; }, 1200); } catch(e){} }); kk.appendChild(cp); c.appendChild(kk);
      if(say) c.appendChild(el("div", "say", say)); if(reply) c.appendChild(el("div", "reply", reply));
      if(list && list.length){ var u = el("ul"); list.forEach(function(x){ u.appendChild(el("li", null, x)); }); c.appendChild(u); }
      return c;
    }
    var n = 0;
    if(PB_TAB === "objections" || q){
      (pb.demand.objections || []).forEach(function(o){ if(hit(o.say, o.reply)){ box.appendChild(card("Customer side · they say", "“" + o.say + "”", o.reply)); n++; } });
      (pb.supply.objections || []).forEach(function(o){ if(hit(o.say, o.reply)){ box.appendChild(card("Hauler side · they say", "“" + o.say + "”", o.reply)); n++; } });
    }
    if(PB_TAB === "answers" || q){
      (pb.demand.answers || []).forEach(function(o){ if(hit(o.q, o.a)){ box.appendChild(card("Customer side · they ask", o.q, o.a)); n++; } });
      (pb.supply.answers || []).forEach(function(o){ if(hit(o.q, o.a)){ box.appendChild(card("Hauler side · they ask", o.q, o.a)); n++; } });
    }
    if(PB_TAB === "openers" || q){
      (pb.openers || []).forEach(function(o){ if(hit(o.key, o.text)){ box.appendChild(card("Opener · " + o.key, null, o.text)); n++; } });
      if(pb.supply.track && pb.supply.track.opener && hit("hauler opener", pb.supply.track.opener)){ box.appendChild(card("Opener · haulers", null, pb.supply.track.opener)); n++; }
    }
    if(PB_TAB === "tracks" || q){
      Object.keys(pb.demand.tracks || {}).forEach(function(seg){ var t = pb.demand.tracks[seg]; if(hit(seg, t.pitch, t.close, (t.discover || []).join(" "))){ box.appendChild(card("Track · " + seg, t.pitch, t.close, t.discover)); n++; } });
      if(pb.supply.track && hit("haulers", pb.supply.track.pitch, pb.supply.track.close)){ box.appendChild(card("Track · haulers", pb.supply.track.pitch, pb.supply.track.close, pb.supply.track.discover)); n++; }
    }
    if(PB_TAB === "prices" || q){
      var pc = el("div", "co-card"); pc.appendChild(el("div", "k", "Prices customers pay, all-in"));
      (pb.prices || []).forEach(function(r){ if(hit(r.label)){ var row = el("div", "co-price"); row.appendChild(el("span", null, r.label)); row.appendChild(el("b", null, "$" + r.from)); pc.appendChild(row); n++; } });
      if(pb.price_note) pc.appendChild(el("div", "k", pb.price_note));
      if(pc.children.length > 1) box.appendChild(pc);
    }
    if(!n) box.appendChild(el("div", "co-empty", "Nothing matches “" + q + "”."));
  }
  document.getElementById("co-q").addEventListener("input", renderPlaybook);
  document.getElementById("co-pb-tabs").addEventListener("click", function(e){
    var b = e.target.closest("button[data-t]"); if(!b) return;
    PB_TAB = b.dataset.t; Array.prototype.forEach.call(this.querySelectorAll("button"), function(x){ x.classList.toggle("on", x === b); }); renderPlaybook();
  });

  // ---------------------------------------------------------------- chat
  var thread = document.getElementById("co-thread"), input = document.getElementById("co-input"), sendBtn = document.getElementById("co-send");
  var history = []; try { history = JSON.parse(sessionStorage.getItem(CHAT_KEY) || "[]"); } catch(e){ history = []; }
  var busy = false;
  function save(){ try { sessionStorage.setItem(CHAT_KEY, JSON.stringify(history.slice(-16))); } catch(e){} }
  function bubble(role, text){ var b = el("div", "co-msg " + (role === "user" ? "user" : "bot"), text); thread.appendChild(b); thread.scrollTop = thread.scrollHeight; return b; }
  function greet(){
    if(history.length){ history.forEach(function(m){ bubble(m.role, m.content); }); return; }
    bubble("bot", "Hey " + (DATA.first || "there") + ". I've read your week, your class, and your last scored calls. Ask me for the exact words.");
  }
  function renderChips(){
    var chips = document.getElementById("co-chips"); clear(chips);
    var f = DATA.focus, list = [];
    if(f && f.label) list.push("Drill me on " + f.label);
    var last = (DATA.calls && DATA.calls.calls || [])[0];
    if(last && last.top_fix) list.push("Reword this: " + last.top_fix);
    list.push("They said “we already have a guy”", "Reword the voicemail shorter", "Explain Stripe to a hauler simply", "What do I say when they ask the price?");
    list.slice(0, 6).forEach(function(t){ var b = el("button", null, t); b.type = "button"; b.addEventListener("click", function(){ sendChat(t); }); chips.appendChild(b); });
    if(!thread.childElementCount) greet();
  }
  function sendChat(text){
    text = (text || "").trim(); if(!text || busy) return;
    bubble("user", text); history.push({role: "user", content: text}); save();
    busy = true; sendBtn.disabled = true; input.value = "";
    var t = bubble("bot", "…"); t.classList.add("typing");
    var body = {messages: history.slice(-16), passcode: ls(KEY)}; if(VA) body.va = VA;
    post("/api/coach/chat", body).then(function(r){
      t.remove(); busy = false; sendBtn.disabled = false;
      if(r.status !== 200 || !r.body || !r.body.reply){ bubble("bot", (r.body && r.body.error) || "Couldn't reach the coach."); return; }
      bubble("bot", r.body.reply); history.push({role: "assistant", content: r.body.reply}); save();
    }).catch(function(){ t.remove(); busy = false; sendBtn.disabled = false; bubble("bot", "Couldn't reach the coach."); });
    document.getElementById("co-chat").scrollIntoView({block: "nearest"});
  }
  document.getElementById("co-form").addEventListener("submit", function(e){ e.preventDefault(); sendChat(input.value); });
  input.addEventListener("keydown", function(e){ if(e.key === "Enter" && !e.shiftKey){ e.preventDefault(); sendChat(input.value); } });
  input.addEventListener("input", function(){ input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 140) + "px"; });
  document.getElementById("co-clear").addEventListener("click", function(){ history = []; save(); clear(thread); greet(); });

  // ---------------------------------------------------------------- boot
  if(ls(JWT_KEY) || ls(KEY)) load(); else showGate();
})();
