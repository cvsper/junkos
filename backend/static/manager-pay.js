/* Haulers owed today — the same-day-pay ledger on /va/manager.
   App haulers with a debit card are paid automatically the moment a job is marked
   complete. Anything listed here is a phone-only hauler (no Stripe) or a failed
   transfer: settle by Zelle with the memo shown, tap Paid, and the hauler gets a
   text. One tap also texts them a Stripe setup link so next time it's automatic.
   CSP-safe: no inline scripts, styles via CSSOM. */
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
  var st = document.createElement("style"); document.head.appendChild(st);
  [".pay-sum{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:baseline;margin:0 0 12px;font-size:13px;color:var(--muted)}",
   ".pay-sum b{font-family:var(--display);font-weight:800;font-size:22px;color:var(--ink)}",
   ".pay-sum .ok{color:var(--ok);font-family:var(--display);font-weight:700}.pay-sum .bad{color:#FF7A5C;font-family:var(--display);font-weight:700}",
   ".pay-h{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px 14px;padding:12px 0 8px;border-top:1px solid var(--line)}",
   ".pay-h:first-of-type{border-top:0}",
   ".pay-h .who{font-family:var(--display);font-weight:800;font-size:15px;color:var(--ink)}",
   ".pay-h .who small{font-weight:600;font-size:12px;color:var(--faint);margin-left:8px}",
   ".pay-h .amt{font-family:var(--display);font-weight:800;font-size:18px;color:var(--ink)}",
   ".pay-h .amt small{font-size:11px;color:var(--faint);font-weight:600;margin-left:6px}",
   ".pay-job{display:grid;grid-template-columns:1fr auto;gap:6px 12px;align-items:center;padding:7px 0 7px 12px;border-left:2px solid var(--line);margin:0 0 6px;font-size:13px;color:var(--muted)}",
   ".pay-job .l b{color:var(--ink);font-family:var(--display);font-weight:700}",
   ".pay-job .l .memo{display:block;font-size:12px;color:var(--faint);margin-top:2px;word-break:break-word}",
   ".pay-job .l .memo code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;color:var(--muted);background:var(--raise);padding:1px 5px;border-radius:5px}",
   ".pay-job.today .l b:after{content:' · today';color:var(--ok);font-size:11px}",
   ".pay-act{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}",
   ".pay-btn{font-family:var(--display);font-weight:800;font-size:12.5px;color:#0B0E12;background:var(--ok);border:0;border-radius:9px;padding:8px 12px;cursor:pointer;white-space:nowrap}",
   ".pay-btn:disabled{opacity:.5;cursor:default}",
   ".pay-btn.alt{background:var(--raise);color:var(--ink);border:1px solid var(--line)}",
   ".pay-btn.copy{background:transparent;color:var(--muted);border:1px solid var(--line);font-weight:700}",
   ".pay-sel{font:inherit;font-size:12.5px;color:var(--ink);background:var(--raise);border:1px solid var(--line);border-radius:9px;padding:7px 8px}",
   ".pay-empty{padding:14px 0;font-size:13.5px;color:var(--muted)}.pay-empty b{color:var(--ok);font-family:var(--display)}",
   ".pay-msg{font-size:12px;color:var(--faint);margin:6px 0 0}",
   "@media(max-width:640px){.pay-job{grid-template-columns:1fr}.pay-act{justify-content:flex-start}}"
  ].forEach(function(r){ try { st.sheet.insertRule(r, st.sheet.cssRules.length); } catch(e){} });

  var host = document.getElementById("pay"), note = document.getElementById("pay-note");
  if(!host) return;

  function copy(text, btn){
    var done = function(){ var t = btn.textContent; btn.textContent = "Copied"; setTimeout(function(){ btn.textContent = t; }, 1400); };
    if(navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(text).then(done, function(){}); return; }
    var ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); done(); } catch(e){} ta.remove();
  }

  function render(rep, status){
    host.textContent = "";
    var sum = el("div", "pay-sum");
    var t = el("span"); t.appendChild(el("b", null, money(rep.today_total))); t.appendChild(document.createTextNode(" owed for today's jobs"));
    sum.appendChild(t);
    if(rep.total > rep.today_total){ var o = el("span"); o.appendChild(el("b", null, money(rep.total - rep.today_total))); o.appendChild(document.createTextNode(" older")); sum.appendChild(o); }
    if(status){
      var td = status.today || {};
      var auto = el("span", null, "Paid automatically today: " + (td.instant || 0) + " instant" + (td.standard ? ", " + td.standard + " standard" : "") + (status.fee_cover_today ? " · fees covered " + money(status.fee_cover_today) : ""));
      sum.appendChild(auto);
      if(status.auto_instant === false) sum.appendChild(el("span", "bad", "Auto instant payout is OFF"));
      if(status.balance && status.balance.state !== "ok") sum.appendChild(el("span", status.balance.state === "fail" ? "bad" : "", "Stripe: " + status.balance.reason));
      else if(status.balance && status.balance.available != null) sum.appendChild(el("span", "ok", "Stripe balance " + money(status.balance.available)));
    }
    host.appendChild(sum);
    if(!rep.haulers.length){
      var e = el("div", "pay-empty"); e.appendChild(el("b", null, "Nobody is waiting on pay. ")); e.appendChild(document.createTextNode("Every completed job has been settled."));
      host.appendChild(e); return;
    }
    rep.haulers.forEach(function(h){
      var head = el("div", "pay-h");
      var who = el("div", "who", h.hauler);
      if(h.phone) who.appendChild(el("small", null, h.phone));
      if(!h.has_stripe) who.appendChild(el("small", null, "no Stripe · Zelle"));
      head.appendChild(who);
      var right = el("div", "pay-act");
      var amt = el("span", "amt", money(h.total)); if(h.today_total && h.today_total !== h.total) amt.appendChild(el("small", null, money(h.today_total) + " today"));
      right.appendChild(amt);
      if(!h.has_stripe && h.contractor_id){
        var ob = el("button", "pay-btn alt", "Text Stripe setup"); ob.type = "button";
        ob.title = "Texts them a 2-minute Stripe link. After that every job pays to their debit card automatically.";
        ob.addEventListener("click", function(){
          ob.disabled = true;
          post("/api/va/pay/onboard-link", {contractor_id: h.contractor_id, send: true}).then(function(r){
            ob.disabled = false; ob.textContent = r.status === 200 ? "Link sent" : ((r.body && r.body.error) || "Couldn't send");
          }).catch(function(){ ob.disabled = false; ob.textContent = "Couldn't send"; });
        });
        right.appendChild(ob);
      }
      head.appendChild(right); host.appendChild(head);
      h.jobs.forEach(function(j){
        var row = el("div", "pay-job" + (j.today ? " today" : ""));
        var l = el("div", "l");
        var b = el("b", null, money(j.amount) + " · " + j.job_code); l.appendChild(b);
        l.appendChild(document.createTextNode(" " + (j.address || "") + (j.completed_at ? " · done " + new Date(j.completed_at).toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"}) : "")));
        var memo = el("span", "memo"); memo.appendChild(document.createTextNode("Zelle memo ")); memo.appendChild(el("code", null, j.memo)); l.appendChild(memo);
        if(j.status === "failed") l.appendChild(el("span", "memo", "Stripe transfer failed — settle by hand, then mark paid."));
        row.appendChild(l);
        var act = el("div", "pay-act");
        var cp = el("button", "pay-btn copy", "Copy memo"); cp.type = "button"; cp.addEventListener("click", function(){ copy(j.memo, cp); });
        var sel = el("select", "pay-sel");
        ["zelle", "cash", "check", "venmo", "cashapp"].forEach(function(m){ var o = el("option", null, m === "cashapp" ? "Cash App" : m.charAt(0).toUpperCase() + m.slice(1)); o.value = m; sel.appendChild(o); });
        var paid = el("button", "pay-btn", "Paid"); paid.type = "button";
        paid.addEventListener("click", function(){
          paid.disabled = true; paid.textContent = "Marking…";
          post("/api/va/pay/mark-paid", {payment_id: j.payment_id, method: sel.value}).then(function(r){
            if(r.status !== 200){ paid.disabled = false; paid.textContent = "Paid"; host.appendChild(el("p", "pay-msg", (r.body && r.body.error) || "Couldn't mark paid.")); return; }
            load();
          }).catch(function(){ paid.disabled = false; paid.textContent = "Paid"; });
        });
        act.appendChild(cp); act.appendChild(sel); act.appendChild(paid);
        row.appendChild(act); host.appendChild(row);
      });
    });
  }

  function load(){
    Promise.all([post("/api/va/pay/owed", {}), post("/api/va/pay/status", {})]).then(function(rs){
      var owed = rs[0], status = rs[1];
      if(owed.status !== 200){ host.textContent = ""; host.appendChild(el("div", "pay-empty", owed.status === 403 ? "Manager sign-in needed to see pay." : ((owed.body && owed.body.error) || "Couldn't load."))); return; }
      render(owed.body, status.status === 200 ? status.body : null);
    }).catch(function(){ host.textContent = ""; host.appendChild(el("div", "pay-empty", "Couldn't load.")); });
  }
  // the manager page loads after login; poll until the tool is visible, then refresh every 2 min
  var tool = document.getElementById("tool"), started = false;
  setInterval(function(){
    var visible = tool && !tool.hidden;
    if(visible && !started){ started = true; load(); setInterval(load, 120000); }
  }, 700);
})();
