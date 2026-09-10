/* Call Desk — inbound customer intake (Phase 6).
 *
 * Loads before /va/calls.js and never reaches into it. It talks to the same
 * DOM (#incoming, #inc-who, #inc-answer, #deck, .col-main, #inbox-list) and
 * the same identity in localStorage, and adds:
 *   - who is calling, while the desk rings (customer / prospect / new)
 *   - a customer intake card (items → live engine quote → book + pay link,
 *     quote text, callback, not-a-fit / spam) that replaces the prospect
 *     card for the length of the call
 *   - "CUSTOMER · missed" rows in the inbox with one-tap Call back now
 * Dialing back uses window.__deskDevice (the desk's Twilio.Device, exposed by
 * calls.js) and falls back to a tel: link when it isn't there.
 */
(function(){
  "use strict";
  var KEY = "umuve_coach_code", VA_KEY = "umuve_va_name", JWT_KEY = "umuve_desk_jwt", ME_KEY = "umuve_desk_me";
  function jwt(){ return localStorage.getItem(JWT_KEY) || ""; }
  function code(){ return localStorage.getItem(KEY) || ""; }
  function me(){ try { return JSON.parse(localStorage.getItem(ME_KEY) || "null"); } catch(e){ return null; } }
  function vaName(){ var m = me(); return (m && m.name) || localStorage.getItem(VA_KEY) || ""; }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { body.code = code(); body.va_name = vaName(); }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }
  function digitsOf(s){ var d = String(s || "").replace(/\D/g, ""); return d.length > 10 ? d.slice(-10) : d; }
  function pretty(d){ return d.length === 10 ? "(" + d.slice(0,3) + ") " + d.slice(3,6) + "-" + d.slice(6) : d; }
  function money(n){ return "$" + (Math.round(Number(n) * 100) / 100).toLocaleString([], {minimumFractionDigits: 0, maximumFractionDigits: 2}); }
  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  function label(cat){ return String(cat || "").replace(/_/g, " "); }

  var css = document.createElement("link"); css.rel = "stylesheet"; css.href = "/static/desk-inbound.css?v=1";
  document.head.appendChild(css);

  var incoming = document.getElementById("incoming");
  var incWho = document.getElementById("inc-who");
  var deck = document.getElementById("deck");
  var colMain = document.querySelector(".col-main");
  if(!incoming || !incWho || !deck || !colMain) return;

  // ------------------------------------------------------------ who's calling
  var incKind = el("div", "inc-kind"); incKind.id = "inc-kind"; incKind.hidden = true;
  incWho.insertAdjacentElement("afterend", incKind);
  var ring = {digits: "", who: null, pending: null};

  function whoLine(w){
    if(!w) return "";
    if(w.kind === "customer" && w.customer){
      var c = w.customer, bits = [c.name || "Returning customer", "customer"];
      if(c.prior_jobs) bits.push(c.prior_jobs + (c.prior_jobs === 1 ? " prior job" : " prior jobs"));
      if(c.last_job && c.last_job.address) bits.push(c.last_job.address.split(",")[0]);
      return bits.join(" · ");
    }
    if(w.kind === "prospect" && w.prospect){
      return [w.prospect.company, "prospect", w.prospect.city].filter(Boolean).join(" · ");
    }
    if(w.callback) return "New caller · asked for a call back";
    if(w.recent_calls && w.recent_calls.length > 1) return "New caller · " + w.recent_calls.length + " calls this week";
    return "New caller — likely a customer";
  }
  function lookup(digits){
    if(digits.length !== 10) return Promise.resolve(null);
    return post("/api/va/inbound/whois", {phone: digits}).then(function(r){ return r.status === 200 ? r.body : null; }).catch(function(){ return null; });
  }
  setInterval(function(){
    if(incoming.hidden){
      if(ring.digits){ ring.digits = ""; ring.who = null; incKind.hidden = true; incKind.textContent = ""; }
      return;
    }
    var d = digitsOf(incWho.textContent);
    if(d === ring.digits) return;
    ring.digits = d; ring.who = null; incKind.hidden = true;
    var p = ring.pending = lookup(d).then(function(w){
      if(ring.pending !== p || ring.digits !== d) return;
      ring.who = w;
      incKind.textContent = whoLine(w);
      incKind.className = "inc-kind" + (w ? " is-" + w.kind : "");
      incKind.hidden = !w;
    });
  }, 500);

  // answer → customer intake (capture phase: runs before the desk's own handler)
  document.addEventListener("click", function(e){
    var btn = e.target && e.target.closest ? e.target.closest("#inc-answer") : null;
    if(!btn || incoming.hidden) return;
    var d = digitsOf(incWho.textContent);
    var ready = ring.who ? Promise.resolve(ring.who) : (ring.pending || lookup(d));
    ready.then(function(w){
      if(w && w.kind === "prospect") return;          // the desk deals their prospect card
      openIntake(d, w, {fromCall: true});
    });
  }, true);

  // ------------------------------------------------------------ intake card
  var state = {digits: "", who: null, callSid: null, items: [], quote: null, window: "", cats: null, ownCall: null, timer: null, busy: false, quoteSeq: 0};
  var POPULAR = ["sofa", "mattress", "refrigerator", "washer_dryer_set", "hot_tub", "tv_flatscreen", "dresser", "bed_set", "treadmill", "yard_waste", "construction", "general"];
  var WINDOWS = [["8-10", "8–10a"], ["10-12", "10–12"], ["12-2", "12–2p"], ["2-4", "2–4p"], ["4-6", "4–6p"]];
  var ui = {};

  function build(){
    var box = el("div", "deskcard intake"); box.id = "intake"; box.hidden = true;
    box.innerHTML =
      '<div class="in-head"><span class="chip in-chip" id="in-chip">CUSTOMER INTAKE</span>' +
      '<span class="in-kind" id="in-kind"></span>' +
      '<button type="button" class="in-close" id="in-close" aria-label="Back to the queue">Back to the queue</button></div>' +
      '<div class="in-callbar" id="in-callbar" hidden><span class="in-dot"></span><span id="in-callstate">Calling…</span><span class="in-time" id="in-time"></span>' +
      '<button type="button" class="in-hang" id="in-hang">Hang up</button></div>' +
      '<div class="in-grid">' +
      '<label class="in-f"><span class="lbl">Name</span><input id="in-name" type="text" autocomplete="off" placeholder="Who am I speaking with?"></label>' +
      '<label class="in-f"><span class="lbl">Phone</span><input id="in-phone" type="tel" inputmode="tel" autocomplete="off" placeholder="(561) 555-0142"></label>' +
      '<label class="in-f in-wide"><span class="lbl">Pickup address</span><input id="in-addr" type="text" autocomplete="off" placeholder="Street, city"></label>' +
      '<label class="in-f"><span class="lbl">Zip</span><input id="in-zip" type="text" inputmode="numeric" maxlength="5" autocomplete="off" placeholder="33460"></label>' +
      '</div>' +
      '<div class="in-sec"><div class="in-h">WHAT ARE WE HAULING?</div>' +
      '<div class="in-chips" id="in-popular"></div>' +
      '<div class="in-addrow"><input id="in-search" type="text" list="in-cats" autocomplete="off" placeholder="Type an item — sofa, mattress, hot tub…"><datalist id="in-cats"></datalist>' +
      '<button type="button" class="si-btn" id="in-add">Add</button></div>' +
      '<div class="in-items" id="in-items"></div>' +
      '<label class="in-chk"><input type="checkbox" id="in-photo"><span>Photo quote — they\'ll text photos for a firm number</span></label></div>' +
      '<div class="in-quote" id="in-quote"><div class="in-qt"><span class="in-ql">ALL-IN QUOTE</span><span class="in-total" id="in-total">—</span></div>' +
      '<div class="in-qb" id="in-breakdown">Add an item to price it.</div></div>' +
      '<div class="in-sec"><div class="in-h">WHEN?</div><div class="in-when"><input id="in-date" type="date">' +
      '<div class="in-wins" id="in-wins"></div></div></div>' +
      '<label class="in-f"><span class="lbl">Notes <span class="opt">— gate code, stairs, where it sits</span></span><input id="in-notes" type="text" autocomplete="off" placeholder="Optional"></label>' +
      '<div class="in-actions">' +
      '<button type="button" class="in-book" id="in-book">Book &amp; text pay link</button>' +
      '<button type="button" class="in-alt" id="in-quotetext">Quote only — text it</button>' +
      '<button type="button" class="in-alt" id="in-cb">Call back later</button>' +
      '<button type="button" class="in-bad" id="in-notfit">Not a fit</button>' +
      '<button type="button" class="in-bad" id="in-spam">Spam</button>' +
      '</div>' +
      '<div class="in-cbrow" id="in-cbrow" hidden>' +
      '<button type="button" class="cb" data-p="hour">In an hour</button><button type="button" class="cb" data-p="tomorrow_am">Tomorrow 9am</button>' +
      '<button type="button" class="cb" data-p="tomorrow_pm">Tomorrow 2pm</button><button type="button" class="cb" data-p="two_days">In 2 days</button>' +
      '<label class="cb cb-pick"><span>Pick a time</span><input type="datetime-local" id="in-cbat"></label></div>' +
      '<p class="in-status" id="in-status" hidden></p>';
    var toast = document.getElementById("desk-toast");
    if(toast && toast.parentNode === colMain) colMain.insertBefore(box, toast); else colMain.appendChild(box);
    ["chip","kind","close","callbar","callstate","time","hang","name","phone","addr","zip","popular","search","cats","add","items","photo","total","breakdown","date","wins","notes","book","quotetext","cb","notfit","spam","cbrow","cbat","status"]
      .forEach(function(k){ ui[k] = document.getElementById("in-" + k); });

    WINDOWS.forEach(function(w){
      var b = el("button", "in-win", w[1]); b.type = "button"; b.dataset.w = w[0];
      b.addEventListener("click", function(){ state.window = state.window === w[0] ? "" : w[0]; paintWins(); });
      ui.wins.appendChild(b);
    });
    ui.date.min = new Date().toISOString().slice(0, 10);
    ui.date.addEventListener("change", requote);
    ui.add.addEventListener("click", function(){ addFromSearch(); });
    ui.search.addEventListener("keydown", function(e){ if(e.key === "Enter"){ e.preventDefault(); addFromSearch(); } });
    ui.search.addEventListener("change", function(){ if(state.cats && state.cats[ui.search.value.trim().toLowerCase().replace(/ /g, "_")]) addFromSearch(); });
    ui.close.addEventListener("click", function(){ closeIntake(); });
    ui.hang.addEventListener("click", function(){ if(state.ownCall) state.ownCall.disconnect(); });
    ui.book.addEventListener("click", book);
    ui.quotetext.addEventListener("click", quoteText);
    ui.cb.addEventListener("click", function(){ ui.cbrow.hidden = !ui.cbrow.hidden; });
    ui.cbrow.addEventListener("click", function(e){
      var b = e.target.closest("button.cb"); if(!b) return;
      callback(b.dataset.p);
    });
    ui.cbat.addEventListener("change", function(){ if(ui.cbat.value) callback(ui.cbat.value); });
    ui.notfit.addEventListener("click", function(){ outcome("not_fit"); });
    ui.spam.addEventListener("click", function(){ outcome("spam"); });
    loadCats();
    return box;
  }

  function loadCats(){
    if(state.cats) return;
    fetch("/api/pricing/categories").then(function(r){ return r.json(); }).then(function(j){
      state.cats = j.categories || {};
      ui.cats.textContent = "";
      Object.keys(state.cats).sort().forEach(function(k){ var o = el("option"); o.value = label(k); ui.cats.appendChild(o); });
      ui.popular.textContent = "";
      POPULAR.filter(function(k){ return state.cats[k]; }).forEach(function(k){
        var b = el("button", "in-pop", label(k)); b.type = "button";
        b.addEventListener("click", function(){ addItem(k); });
        ui.popular.appendChild(b);
      });
    }).catch(function(){});
  }
  function addFromSearch(){
    var v = ui.search.value.trim().toLowerCase().replace(/ /g, "_");
    if(!v) return;
    var key = null;
    if(state.cats){
      if(state.cats[v]) key = v;
      else Object.keys(state.cats).some(function(k){ if(k.indexOf(v) === 0 || label(k).indexOf(v.replace(/_/g, " ")) === 0){ key = k; return true; } return false; });
    }
    if(!key){ status("Not in the price list — add it as \"general\" and note it.", true); return; }
    addItem(key); ui.search.value = "";
  }
  function addItem(cat){
    var hit = null;
    state.items.some(function(it){ if(it.category === cat && !it.size){ hit = it; return true; } return false; });
    if(hit) hit.quantity += 1; else state.items.push({category: cat, quantity: 1});
    paintItems(); requote();
  }
  function sizesFor(cat){
    var c = (state.cats || {})[cat] || {};
    return Object.keys(c).filter(function(k){ return k !== "default"; });
  }
  function paintItems(){
    ui.items.textContent = "";
    if(!state.items.length){ ui.items.appendChild(el("p", "in-none", "Nothing yet — tap an item above or type one.")); return; }
    state.items.forEach(function(it, i){
      var row = el("div", "in-item");
      var name = el("span", "in-iname", label(it.category)); row.appendChild(name);
      var sizes = sizesFor(it.category);
      if(sizes.length){
        var sel = el("select", "in-size");
        ["default"].concat(sizes).forEach(function(s){ var o = el("option", null, s === "default" ? "standard" : s); o.value = s; if((it.size || "default") === s) o.selected = true; sel.appendChild(o); });
        sel.addEventListener("change", function(){ if(sel.value === "default") delete it.size; else it.size = sel.value; requote(); });
        row.appendChild(sel);
      }
      var step = el("div", "in-step");
      var minus = el("button", "in-sb", "−"); minus.type = "button";
      var n = el("span", "in-n", String(it.quantity));
      var plus = el("button", "in-sb", "+"); plus.type = "button";
      minus.addEventListener("click", function(){ it.quantity -= 1; if(it.quantity <= 0) state.items.splice(i, 1); paintItems(); requote(); });
      plus.addEventListener("click", function(){ it.quantity = Math.min(50, it.quantity + 1); paintItems(); requote(); });
      step.appendChild(minus); step.appendChild(n); step.appendChild(plus);
      row.appendChild(step);
      ui.items.appendChild(row);
    });
  }
  function paintWins(){
    Array.prototype.forEach.call(ui.wins.children, function(b){ b.classList.toggle("on", b.dataset.w === state.window); });
  }
  var quoteTimer = null;
  function requote(){
    clearTimeout(quoteTimer);
    quoteTimer = setTimeout(function(){
      if(!state.items.length){ state.quote = null; ui.total.textContent = "—"; ui.breakdown.textContent = "Add an item to price it."; return; }
      var seq = ++state.quoteSeq;
      post("/api/va/inbound/quote", {items: state.items, zip: ui.zip.value, date: ui.date.value || null}).then(function(r){
        if(seq !== state.quoteSeq) return;
        if(r.status !== 200){ status((r.body && r.body.error) || "Couldn't price that.", true); return; }
        state.quote = r.body;
        ui.total.textContent = money(r.body.total);
        ui.breakdown.textContent = "";
        (r.body.items || []).forEach(function(l){
          var line = el("div", "in-ql2");
          line.appendChild(el("span", null, l.quantity + "× " + label(l.category) + (l.size ? " (" + l.size + ")" : "")));
          line.appendChild(el("span", null, money(l.line_total)));
          ui.breakdown.appendChild(line);
        });
        var extras = [];
        if(r.body.volume_discount > 0) extras.push("−" + money(r.body.volume_discount) + " " + (r.body.volume_discount_label || "volume discount"));
        if(r.body.surge_amount > 0) extras.push("+" + money(r.body.surge_amount) + " " + (r.body.surge_reasons || []).join(", "));
        if(r.body.service_fee > 0) extras.push("+" + money(r.body.service_fee) + " service");
        if(r.body.recycling_fees > 0) extras.push("+" + money(r.body.recycling_fees) + " disposal");
        if(r.body.minimum_applied) extras.push("minimum " + money(r.body.minimum_job_price) + " applied");
        if(extras.length) ui.breakdown.appendChild(el("div", "in-qx", extras.join(" · ")));
        ui.breakdown.appendChild(el("div", "in-qx", "Includes pickup, labor, and disposal. " + (r.body.estimated_duration ? "About " + r.body.estimated_duration + "." : "")));
      }).catch(function(){});
    }, 250);
  }

  var statusTimer = null;
  function status(msg, bad){
    ui.status.textContent = msg; ui.status.hidden = !msg; ui.status.classList.toggle("bad", !!bad);
    clearTimeout(statusTimer);
    if(msg && !bad) statusTimer = setTimeout(function(){ ui.status.hidden = true; }, 6000);
  }
  function setBusy(b){
    state.busy = b;
    [ui.book, ui.quotetext, ui.cb, ui.notfit, ui.spam].forEach(function(x){ x.disabled = b; });
  }
  function payload(extra){
    var p = {
      call_sid: state.callSid, name: ui.name.value.trim(), phone: ui.phone.value, address: ui.addr.value.trim(),
      zip: ui.zip.value.trim(), items: state.items, date: ui.date.value || null, window: state.window,
      notes: ui.notes.value.trim(), photo_quote: ui.photo.checked
    };
    for(var k in (extra || {})) p[k] = extra[k];
    return p;
  }
  function done(msg){
    status(msg);
    setTimeout(function(){ closeIntake(); }, 1400);
  }
  function book(){
    if(state.busy) return;
    if(!state.items.length){ status("Add what we're hauling first.", true); return; }
    if(!ui.addr.value.trim()){ status("Need the pickup address.", true); ui.addr.focus(); return; }
    if(digitsOf(ui.phone.value).length !== 10){ status("Need a 10-digit phone for the pay link.", true); ui.phone.focus(); return; }
    setBusy(true); status("Booking…");
    post("/api/va/inbound/book", payload()).then(function(r){
      setBusy(false);
      if(r.status !== 200){ status((r.body && r.body.error) || "Couldn't book it.", true); return; }
      try { window.__lastBookedJob = r.body.job || null; } catch(e){}
      done("Booked " + (r.body.job && r.body.job.code ? r.body.job.code : "") + " — " + money(r.body.total) + ". " +
           (r.body.texted ? "Confirmation + pay link texted." : "Text didn't go — read them the total."));
    }).catch(function(){ setBusy(false); status("No connection — nothing was booked.", true); });
  }
  function quoteText(){
    if(state.busy) return;
    if(!state.items.length){ status("Add what we're hauling first.", true); return; }
    if(digitsOf(ui.phone.value).length !== 10){ status("Need a 10-digit phone to text.", true); ui.phone.focus(); return; }
    setBusy(true); status("Texting the quote…");
    post("/api/va/inbound/quote-text", payload()).then(function(r){
      setBusy(false);
      if(r.status !== 200){ status((r.body && r.body.error) || "Couldn't send it.", true); return; }
      done(r.body.message || "Quote texted.");
    }).catch(function(){ setBusy(false); status("No connection — nothing was sent.", true); });
  }
  function callback(when){
    if(state.busy) return;
    if(digitsOf(ui.phone.value).length !== 10){ status("Need their number to call back.", true); ui.phone.focus(); return; }
    setBusy(true);
    post("/api/va/inbound/callback", payload({when: when, note: ui.notes.value.trim()})).then(function(r){
      setBusy(false);
      if(r.status !== 200){ status((r.body && r.body.error) || "Couldn't set that.", true); return; }
      done(r.body.message || "Callback set.");
    }).catch(function(){ setBusy(false); status("No connection.", true); });
  }
  function outcome(kind){
    if(state.busy) return;
    var d = digitsOf(ui.phone.value) || state.digits;
    if(d.length !== 10){ closeIntake(); return; }
    setBusy(true);
    post("/api/va/inbound/outcome", {phone: d, call_sid: state.callSid, outcome: kind, note: ui.notes.value.trim()}).then(function(r){
      setBusy(false);
      if(r.status !== 200){ status((r.body && r.body.error) || "Couldn't log that.", true); return; }
      done(kind === "spam" ? "Marked as spam." : "Logged — not a fit.");
    }).catch(function(){ setBusy(false); status("No connection.", true); });
  }

  function reset(){
    state.items = []; state.quote = null; state.window = ""; state.callSid = null; state.quoteSeq++;
    ui.name.value = ""; ui.phone.value = ""; ui.addr.value = ""; ui.zip.value = ""; ui.notes.value = "";
    ui.date.value = ""; ui.photo.checked = false; ui.search.value = ""; ui.cbrow.hidden = true; ui.cbat.value = "";
    ui.status.hidden = true; setBusy(false); paintItems(); paintWins();
    ui.total.textContent = "—"; ui.breakdown.textContent = "Add an item to price it.";
  }
  function openIntake(digits, who, opts){
    opts = opts || {};
    var box = document.getElementById("intake") || build();
    reset();
    state.digits = digits; state.who = who || null;
    ui.phone.value = pretty(digits);
    if(who){
      state.callSid = who.call ? who.call.call_sid : null;
      if(who.customer){
        ui.name.value = who.customer.name || "";
        if(who.customer.last_job && who.customer.last_job.address && !opts.fresh) ui.addr.value = who.customer.last_job.address;
      }
      if(who.callback && who.callback.name) ui.name.value = ui.name.value || who.callback.name;
      ui.kind.textContent = whoLine(who);
    } else { ui.kind.textContent = ""; }
    ui.chip.textContent = opts.callback ? "CALLBACK" : (opts.fromCall ? "CUSTOMER INTAKE · ON THE CALL" : "CUSTOMER INTAKE");
    deck.classList.add("intake-open");
    box.hidden = false;
    if(!opts.silent){ try { (ui.name.value ? ui.addr : ui.name).focus(); } catch(e){} }
    if(!reduced()){
      box.style.opacity = "0"; box.style.transform = "translateY(6px)";
      requestAnimationFrame(function(){ box.style.transition = "opacity .18s ease, transform .18s ease"; box.style.opacity = "1"; box.style.transform = "none";
        setTimeout(function(){ box.style.transition = ""; }, 220); });
    }
  }
  function reduced(){ return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  function closeIntake(){
    var box = document.getElementById("intake");
    if(box) box.hidden = true;
    deck.classList.remove("intake-open");
    state.digits = ""; state.who = null;
    if(state.ownCall) return;                                   // still talking — keep the strip alive
    var card = document.getElementById("card"), empty = document.getElementById("empty");
    if(card && card.hidden && empty && empty.hidden) location.reload();
  }

  // ------------------------------------------------------------ dial back
  function fmtTime(s){ var m = Math.floor(s / 60), r = s % 60; return (m < 10 ? "0" : "") + m + ":" + (r < 10 ? "0" : "") + r; }
  function bindOwnCall(call){
    state.ownCall = call;
    ui.callbar.hidden = false; ui.callstate.textContent = "Calling " + pretty(state.digits) + "…"; ui.time.textContent = "";
    var start = 0;
    function tick(){ if(start) ui.time.textContent = fmtTime(Math.floor((Date.now() - start) / 1000)); }
    call.on("accept", function(){ start = Date.now(); ui.callstate.textContent = "On the call"; clearInterval(state.timer); state.timer = setInterval(tick, 1000); });
    function endc(){ clearInterval(state.timer); state.ownCall = null; ui.callbar.hidden = true; }
    call.on("disconnect", endc); call.on("cancel", endc); call.on("reject", endc);
    call.on("error", function(){ endc(); status("The call dropped.", true); });
  }
  function dial(digits){
    var dev = window.__deskDevice;
    if(dev && typeof dev.connect === "function"){
      try {
        dev.connect({params: {To: "+1" + digits, va_name: vaName()}}).then(bindOwnCall).catch(function(){ status("Couldn't start the call from the browser — tap the number on your phone.", true); });
        return;
      } catch(e){}
    }
    var a = document.createElement("a"); a.href = "tel:+1" + digits; a.style.display = "none";
    document.body.appendChild(a); a.click(); a.remove();
    status("Dialing from your phone — the browser dialer isn't connected.", false);
  }
  function callBack(digits, hint){
    lookup(digits).then(function(w){
      openIntake(digits, w, {callback: !!(w && w.callback) || hint === "callback", fresh: false});
      dial(digits);
    });
  }

  // ------------------------------------------------------------ inbox: CUSTOMER · missed
  var inboxList = document.getElementById("inbox-list");
  var recent = {at: 0, calls: {}, cbs: {}, pending: null};
  function loadRecent(){
    if(recent.pending) return recent.pending;
    recent.pending = post("/api/va/inbound/recent", {days: 7}).then(function(r){
      recent.pending = null;
      if(r.status !== 200) return recent;
      recent.at = Date.now(); recent.calls = {}; recent.cbs = {};
      (r.body.calls || []).forEach(function(c){ if(!recent.calls[c.phone_digits]) recent.calls[c.phone_digits] = c; });
      (r.body.callbacks || []).forEach(function(c){ if(!recent.cbs[c.phone_digits]) recent.cbs[c.phone_digits] = c; });
      return recent;
    }).catch(function(){ recent.pending = null; return recent; });
    return recent.pending;
  }
  function decorate(){
    if(!inboxList) return;
    var rows = Array.prototype.filter.call(inboxList.querySelectorAll("button.sr"), function(b){ return !b.dataset.p6; });
    if(!rows.length) return;
    loadRecent().then(function(){
      rows.forEach(function(row){
        row.dataset.p6 = "1";
        var t = row.querySelector(".sr-t"); if(!t) return;
        var d = digitsOf(t.textContent);
        if(d.length !== 10 || /[A-Za-z]/.test(t.textContent)) return;      // a prospect row — the desk owns it
        var call = recent.calls[d], cb = recent.cbs[d];
        if(!call && !cb) return;
        var name = (call && call.name) || (cb && cb.name) || "";
        var tag = el("span", "sr-tag " + (cb ? "is-cb" : (call && call.missed ? "is-missed" : "is-cust")),
                     cb ? "CALLBACK" : (call && call.missed ? "CUSTOMER · missed" : "CUSTOMER"));
        t.textContent = name ? name + " · " + pretty(d) : pretty(d);
        t.insertAdjacentElement("afterbegin", tag);
        if(cb){
          var when = el("div", "sr-when", "Wants a call " + (cb.requested_human || "any time") + (cb.note ? " — " + cb.note : ""));
          t.insertAdjacentElement("afterend", when);
        }
        var go = el("button", "sr-callnow", "Call back now"); go.type = "button";
        go.addEventListener("click", function(e){ e.preventDefault(); e.stopPropagation(); callBack(d, cb ? "callback" : "missed"); });
        row.appendChild(go);
        row.classList.add("sr-cust");
      });
    });
  }
  if(inboxList){
    var obs = new MutationObserver(function(){ recent.at = 0; decorate(); });
    obs.observe(inboxList, {childList: true});
    decorate();
  }
})();
