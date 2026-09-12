/* Leads — every incoming customer lead, every channel, one list.
 *
 * A customer who *calls* the desk already gets a good experience. Everyone
 * else leaked: web quotes and Meta forms never reached the VA, a phone quote
 * that didn't book was never followed up, and nothing said where a lead came
 * from. This panel is the one place they all land, newest paid leads first,
 * with a timer counting up from the moment they reached out.
 *
 * Rules it holds to:
 *   - paid leads (Google, Meta) sort first and wear a badge: someone paid for
 *     that ring;
 *   - the timer is the point — "2 min" means the customer is dialling the next
 *     company right now;
 *   - every row can be called, texted, or marked, from the row;
 *   - "Spam" / "Not a fit" on a Google lead is what gets the money back.
 *
 * CSP-safe: no inline script, styles via CSSOM.
 */
(function(){
  "use strict";
  var JWT_KEY = "umuve_desk_jwt", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";

  function jwt(){ try { return localStorage.getItem(JWT_KEY) || ""; } catch(e){ return ""; } }
  function vaName(){ try { return localStorage.getItem(VA_KEY) || ""; } catch(e){ return ""; } }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { try { body.code = localStorage.getItem(KEY) || ""; body.va_name = vaName(); } catch(e){} }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }
  function el(tag, cls, text){
    var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e;
  }

    (function(){ if(document.querySelector('link[href^="/static/desk-leads.css"]')) return; var l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/static/desk-leads.css?v=2"; document.head.appendChild(l); })();

  var tab = el("button", "ld-tab"); tab.type = "button";
  tab.appendChild(el("span", null, "Leads"));
  var badge = el("span", "n", "0"); tab.appendChild(badge);
  tab.title = "Every incoming customer lead, every channel";
  document.body.appendChild(tab);

  var wrap = el("div", "ld-wrap"); wrap.hidden = true;
  var panel = el("div", "ld");
  var head = el("div", "ld-h");
  head.appendChild(el("h3", null, "Incoming leads"));
  var close = el("button", "ld-x", "×"); close.type = "button"; close.setAttribute("aria-label", "Close");
  head.appendChild(close);
  var sub = el("p", "ld-sub");
  var list = el("div");
  var msg = el("p", "ld-msg");
  [head, sub, list, msg].forEach(function(n){ panel.appendChild(n); });
  wrap.appendChild(panel);
  document.body.appendChild(wrap);

  var data = null, busy = false, tick = null;

  function say(t, kind){ msg.textContent = t || ""; msg.className = "ld-msg" + (kind ? " " + kind : ""); }
  function fmtAge(s){
    if(s < 60) return Math.max(1, Math.round(s)) + "s";
    if(s < 3600) return Math.floor(s / 60) + " min";
    if(s < 86400) return Math.floor(s / 3600) + "h";
    return Math.floor(s / 86400) + "d";
  }
  function placeTab(){
    var line = document.getElementById("line"), h = 0;
    if(line && !line.hidden){
      var r = line.getBoundingClientRect();
      var isBottomBar = r.bottom >= window.innerHeight - 2 && r.height > 0 &&
                        r.height < window.innerHeight * 0.65 && r.width > window.innerWidth * 0.6;
      if(isBottomBar) h = r.height;
    }
    // beside the Work tab (same row), not stacked on top of the card
    var work = document.querySelector(".wq-tab");
    if(work && !work.hidden){ var wr = work.getBoundingClientRect(); tab.style.left = Math.round(wr.right + 8) + "px"; tab.style.bottom = (h + 14) + "px"; }
    else { tab.style.left = "14px"; tab.style.bottom = (h + 14) + "px"; }
  }

  function dial(pretty){
    var digits = (pretty || "").replace(/\D/g, "");
    if(digits.length === 11 && digits.charAt(0) === "1") digits = digits.slice(1);
    if(digits.length !== 10){ say("That number doesn't look dialable.", "err"); return; }
    if(window.__deskCallsBlocked){ say("The calling window is closed right now.", "err"); return; }
    var dev = window.__deskDevice;
    if(dev && typeof dev.connect === "function"){
      dev.connect({params: {To: "+1" + digits, va_name: vaName()}}).then(function(){ shut(); })
        .catch(function(){ say("Couldn't start the call — check the microphone.", "err"); });
      return;
    }
    var a = document.createElement("a"); a.href = "tel:+1" + digits; a.style.display = "none";
    document.body.appendChild(a); a.click(); a.remove();
  }

  function mark(l, outcome, btn, note){
    if(busy) return; busy = true; if(btn) btn.disabled = true;
    post("/api/va/leads/touch", {kind: l.kind, ref_id: l.ref_id, phone: l.phone_digits, outcome: outcome, note: note || ""})
      .then(function(r){
        busy = false; if(btn) btn.disabled = false;
        if(r.status !== 200){ say((r.body && r.body.error) || "That didn't work.", "err"); return; }
        say(outcome === "spam" || outcome === "not_a_fit" ? "Marked — it's on the dispute list for Shamar." : "Got it.", "ok");
        load();
      }).catch(function(){ busy = false; if(btn) btn.disabled = false; say("No connection — try again.", "err"); });
  }

  function row(l){
    var box = el("div", "ld-i" + (l.touched_at ? " done" : ""));
    var top = el("div", "ld-top");
    var who = el("div", "ld-who");
    var b = el("span", "ld-badge " + (l.source || ""), l.source_label || "New");
    who.appendChild(b);
    who.appendChild(document.createTextNode(l.name || l.phone || "Unknown caller"));
    if(l.contacts > 1) who.appendChild(el("span", "ld-badge", l.contacts + "×"));
    top.appendChild(who);
    var t = el("span", "ld-timer" + (!l.touched_at && l.age_seconds >= (data.speed_to_lead_seconds || 120) ? " hot" : ""), fmtAge(l.age_seconds));
    t.setAttribute("data-age", String(l.age_seconds)); t.setAttribute("data-hot", l.touched_at ? "0" : "1");
    top.appendChild(t);
    box.appendChild(top);
    if(l.what) box.appendChild(el("p", "ld-what", (l.phone && l.name ? l.phone + " · " : "") + l.what));
    if(l.maya_context){
      var m = el("div", "ld-maya"); m.appendChild(el("b", null, "From Maya · ")); m.appendChild(document.createTextNode(l.maya_context.summary));
      box.appendChild(m);
    }
    if(l.touched_at) box.appendChild(el("p", "ld-touch", (l.touched_by || "Someone") + " is on it" + (l.outcome ? " · " + l.outcome.replace(/_/g, " ") : "")));
    else if(l.auto_text_at) box.appendChild(el("p", "ld-touch", "Auto-texted — waiting on a person"));

    var act = el("div", "ld-act");
    if(l.phone){
      var c = el("button", "ld-b go", "Call"); c.type = "button";
      c.addEventListener("click", function(){ mark(l, null, c); dial(l.phone); });
      act.appendChild(c);
    }
    if(!l.touched_at){
      var take = el("button", "ld-b", "I'm on it"); take.type = "button";
      take.addEventListener("click", function(){ mark(l, null, take); });
      act.appendChild(take);
    }
    var booked = el("button", "ld-b", "Booked"); booked.type = "button";
    booked.addEventListener("click", function(){ mark(l, "booked", booked); });
    act.appendChild(booked);
    if(l.source === "google" || l.source === "meta"){
      var nf = el("button", "ld-b bad", "Not a fit"); nf.type = "button";
      nf.title = "Wrong service or area — disputable";
      nf.addEventListener("click", function(){ mark(l, "not_a_fit", nf, "not a fit"); });
      var sp = el("button", "ld-b bad", "Spam"); sp.type = "button";
      sp.addEventListener("click", function(){ mark(l, "spam", sp, "spam"); });
      act.appendChild(nf); act.appendChild(sp);
    }
    box.appendChild(act);
    return box;
  }

  function paint(){
    badge.textContent = data ? String(data.untouched) : "0";
    tab.classList.toggle("hot", !!(data && data.untouched > 0));
    if(wrap.hidden) return;
    list.textContent = "";
    if(!data){ sub.textContent = "Loading…"; return; }
    sub.textContent = data.total === 0 ? "" :
      data.total + " open · " + data.untouched + " untouched" + (data.paid ? " · " + data.paid + " paid" : "") +
      " · untouched for " + Math.round((data.speed_to_lead_seconds || 120) / 60) + " min gets an automatic text, then it's on you";
    if(!data.leads.length){
      var e = el("div", "ld-empty"); e.appendChild(el("b", null, "No open leads.")); e.appendChild(document.createTextNode("Calls, texts, web quotes and ad forms all land here."));
      list.appendChild(e);
    } else {
      data.leads.forEach(function(l){ list.appendChild(row(l)); });
    }
    if(data.day3 && data.day3.length){
      list.appendChild(el("div", "ld-sec", "Quoted, no answer after 3 days — your call"));
      data.day3.forEach(function(d){
        var r = el("div", "ld-i");
        var top = el("div", "ld-top");
        top.appendChild(el("div", "ld-who", (d.name || d.phone || "") + (d.quote_total ? " · $" + Math.round(d.quote_total) : "")));
        top.appendChild(el("span", "ld-timer", fmtAge(d.age_hours * 3600)));
        r.appendChild(top);
        var act = el("div", "ld-act");
        var c = el("button", "ld-b go", "Call " + d.phone); c.type = "button";
        c.addEventListener("click", function(){ dial(d.phone); });
        act.appendChild(c);
        var drop = el("button", "ld-b", "Let it go"); drop.type = "button";
        drop.addEventListener("click", function(){
          post("/api/va/leads/touch", {phone: d.phone_digits, outcome: "not_a_fit", note: "no reply after 3 days"}).then(load);
        });
        act.appendChild(drop);
        r.appendChild(act); list.appendChild(r);
      });
    }
  }

  function tickTimers(){
    if(wrap.hidden) return;
    list.querySelectorAll(".ld-timer[data-age]").forEach(function(t){
      var a = parseFloat(t.getAttribute("data-age") || "0") + 1; t.setAttribute("data-age", String(a));
      t.textContent = fmtAge(a);
      if(t.getAttribute("data-hot") === "1" && a >= (data && data.speed_to_lead_seconds || 120)) t.classList.add("hot");
    });
  }

  function load(){
    post("/api/va/leads/list", {}).then(function(r){
      if(r.status !== 200){ if(!wrap.hidden) say((r.body && r.body.error) || "Couldn't load.", "err"); return; }
      data = r.body; paint();
    }).catch(function(){});
  }
  function open(){ wrap.hidden = false; paint(); load(); }
  function shut(){ wrap.hidden = true; say(""); }
  tab.addEventListener("click", open);
  close.addEventListener("click", shut);
  wrap.addEventListener("click", function(e){ if(e.target === wrap) shut(); });
  document.addEventListener("keydown", function(e){ if(e.key === "Escape" && !wrap.hidden) shut(); });

  placeTab(); window.addEventListener("resize", placeTab); setInterval(placeTab, 1500);
  setTimeout(load, 2200); setInterval(load, 30000);
  tick = setInterval(tickTimers, 1000);
})();
