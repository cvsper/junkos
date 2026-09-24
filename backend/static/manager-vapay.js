/* VA pay on /va/manager — every VA's statement for a pay period: hours x rate,
   hauler sign-ups, booking bonuses. The VA sees her own on the desk's My pay tab.
   CSP-safe: external file, styles from manager-vapay.css. */
(function(){
  var JWT_KEY = "umuve_desk_jwt", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";
  function jwt(){ try { return localStorage.getItem(JWT_KEY) || ""; } catch(e){ return ""; } }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { try { body.code = localStorage.getItem(KEY) || ""; body.va_name = localStorage.getItem(VA_KEY) || ""; } catch(e){} }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }
  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  function money(v){ return "$" + Number(v || 0).toFixed(2); }
  (function(){ if(document.querySelector('link[href^="/static/manager-vapay.css"]')) return; var l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/static/manager-vapay.css?v=2"; document.head.appendChild(l); })();

  var host = document.getElementById("vapay"), note = document.getElementById("vapay-note");
  if(!host) return;
  var back = 0;

  function line(label, val){ var r = el("div", "vp-line"); r.appendChild(el("span", null, label)); r.appendChild(el("b", null, val)); return r; }

  function render(d){
    host.textContent = "";
    var nav = el("div", "vp-nav");
    var prev = el("button", "pay-btn alt", "← Earlier"); prev.type = "button";
    var next = el("button", "pay-btn alt", "Later →"); next.type = "button"; next.disabled = back === 0;
    prev.addEventListener("click", function(){ if(back < 12){ back++; load(); } });
    next.addEventListener("click", function(){ if(back > 0){ back--; load(); } });
    nav.appendChild(prev); nav.appendChild(el("span", "vp-label", "Biweekly · " + d.period_label + (d.closed ? "" : " · in progress"))); nav.appendChild(next);
    host.appendChild(nav);
    var r = d.rules || {};
    if(note) note.textContent = "Hourly rate on the clock, " + money(r.signup_bonus) + " per hauler sign-up, " +
      Math.round((r.booking_pct || 0) * 100) + "% of each completed booking (" + money(r.booking_min) + " to " + money(r.booking_max) + ").";
    if(!d.vas.length){ host.appendChild(el("div", "pay-empty", "Nobody clocked in this period.")); return; }
    d.vas.forEach(function(v){
      var card = el("div", "vp-card");
      var head = el("div", "pay-h");
      var who = el("div", "who", v.va_name); who.appendChild(el("small", null, money(v.hourly_rate) + "/hr"));
      head.appendChild(who);
      var amt = el("span", "amt", money(v.total));
      if(v.booking_pending) amt.appendChild(el("small", null, "+" + money(v.booking_pending) + " pending"));
      head.appendChild(amt); card.appendChild(head);
      card.appendChild(line("Hours · " + v.hours.toFixed(2) + " × " + money(v.hourly_rate), v.rate_set ? money(v.hours_pay) : "rate not set"));
      card.appendChild(line("Hauler sign-ups · " + v.signup_count, money(v.signup_pay)));
      card.appendChild(line("Bookings · " + v.booking_count, money(v.booking_pay)));
      if(v.unpaid_hours) card.appendChild(line("Unpaid shifts · " + v.unpaid_hours.toFixed(2) + " hrs", "$0.00"));
      if(v.capped_hours) card.appendChild(line("Forgot to clock out · capped", "−" + v.capped_hours.toFixed(2) + " hrs"));
      if(v.total > 0){
        var L = v.local && v.local.currency !== "USD" ? v.local : null;
        var loc = function(x){ return L ? " · " + L.symbol + Math.round(x).toLocaleString("en-US") : ""; };
        if(v.fees_total) card.appendChild(line("Transfer fee · " + v.fee_pct.toFixed(2) + "%", "−" + money(v.fees_total)));
        var n = line("She receives", money(v.net) + loc(L ? L.net : 0)); n.className = "vp-line vp-net"; card.appendChild(n);
        if(v.fees_total) card.appendChild(line("Send this for her to receive the full " + money(v.total), money(v.send_for_full)));
        if(L) card.appendChild(line("Exchange rate", "$1 = " + L.symbol + Number(L.rate).toLocaleString("en-US", {maximumFractionDigits: 2})));
      }
      var det = el("details", "vp-det"); det.appendChild(el("summary", null, "Shifts, sign-ups, bookings"));
      v.shifts.forEach(function(s){
        var t = s.day + " · " + s.start_local + "–" + (s.end_local || "now") + " · " + s.hours.toFixed(2) + " hrs";
        if(s.unpaid) t += " · not paid: " + (s.unpaid_reason || "");
        else if(s.capped) t += " · paid " + s.paid_hours.toFixed(2);
        det.appendChild(el("div", "vp-item" + (s.unpaid ? " off" : ""), t));
      });
      v.signups.forEach(function(x){ det.appendChild(el("div", "vp-item", "Sign-up · " + x.day + " · " + x.company)); });
      v.bookings.forEach(function(b){ det.appendChild(el("div", "vp-item" + (b.state === "cancelled" ? " off" : ""), "Booking · " + b.day + " · " + (b.code || "") + " · " + money(b.value) + " · " + b.state + " · " + money(b.bonus))); });
      card.appendChild(det);
      host.appendChild(card);
    });
    if(d.vas.length > 1) host.appendChild(line("All VAs", money(d.total)));
  }
  function load(){
    post("/api/va/time/team-pay", {periods_back: back}).then(function(r){
      if(r.status !== 200){ host.textContent = ""; host.appendChild(el("div", "pay-empty", (r.body && r.body.error) || "Couldn't load VA pay.")); return; }
      render(r.body);
    }).catch(function(){ host.textContent = ""; host.appendChild(el("div", "pay-empty", "No connection — couldn't load VA pay.")); });
  }
  load();
})();
