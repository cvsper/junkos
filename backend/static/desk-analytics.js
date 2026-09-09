/* Call Desk — Phase 4 add-on: a "Stats" tab in the hours panel and a call
   scorecard under the copilot summary. Loads before /va/calls.js and only
   touches DOM the desk already renders; nothing here blocks the desk if an
   endpoint is missing. */
(function(){
  var JWT_KEY = "umuve_desk_jwt", ME_KEY = "umuve_desk_me", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";
  function jwt(){ try { return localStorage.getItem(JWT_KEY) || ""; } catch(e){ return ""; } }
  function me(){ try { return JSON.parse(localStorage.getItem(ME_KEY) || "null"); } catch(e){ return null; } }
  function code(){ try { return localStorage.getItem(KEY) || ""; } catch(e){ return ""; } }
  function vaName(){ var m = me(); try { return (m && m.name) || localStorage.getItem(VA_KEY) || ""; } catch(e){ return ""; } }
  function isManager(){ var m = me(); return !!(m && m.is_manager) || (!jwt() && !!code()); }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { body.code = code(); body.va_name = vaName(); }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }
  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  function css(e, o){ for(var k in o) e.style[k] = o[k]; return e; }
  var C = {ink: "#F4F6F8", muted: "rgba(244,246,248,.62)", faint: "rgba(244,246,248,.38)", line: "rgba(244,246,248,.09)",
           raise: "#1A2029", accent: "#FF6A2C", blue: "#7FB8FF", ok: "#3DD68C"};

  // ---- Stats tab in the hours panel ----------------------------------------
  function mountStats(){
    var team = document.getElementById("tb-team"), mine = document.getElementById("tb-mine"), list = document.getElementById("tb-list");
    if(!team || !mine || !list || document.getElementById("tb-stats")) return;
    var tab = el("button", "kit-tab", "Stats"); tab.type = "button"; tab.id = "tb-stats";
    team.parentNode.appendChild(tab);
    var panel = el("div"); panel.id = "tb-stats-panel"; panel.hidden = true;
    list.parentNode.insertBefore(panel, list.nextSibling);
    var teamTotals = document.getElementById("tb-team-totals");
    function off(){
      if(panel.hidden) return;
      panel.hidden = true; list.hidden = false; tab.classList.remove("is-on");
    }
    mine.addEventListener("click", off); team.addEventListener("click", off);
    tab.addEventListener("click", function(){
      mine.classList.remove("is-on"); team.classList.remove("is-on"); tab.classList.add("is-on");
      list.hidden = true; if(teamTotals) teamTotals.hidden = true; panel.hidden = false;
      loadStats(panel);
    });
  }
  function loadStats(panel){
    panel.textContent = "";
    panel.appendChild(css(el("p", null, "Adding up your calls…"), {color: C.faint, fontSize: "13px", margin: "10px 0"}));
    var periods = [["today", "Today"], ["week", "This week"], ["pay_period", "Pay period"]];
    Promise.all(periods.map(function(p){ return post("/api/va/analytics/funnel", {period: p[0]}).catch(function(){ return {status: 0}; }); }))
      .then(function(rs){
        panel.textContent = "";
        if(rs.some(function(r){ return r.status !== 200; })){
          panel.appendChild(css(el("p", null, "Couldn't load your stats. Try again in a minute."), {color: C.faint, fontSize: "13px"}));
          return;
        }
        var head = css(el("div", null, "Your calls · pay period " + (rs[2].body.label || "")),
                       {color: C.muted, fontSize: "12.5px", margin: "10px 0 6px"});
        panel.appendChild(head);
        var t = css(el("table"), {width: "100%", borderCollapse: "collapse", fontSize: "13.5px"});
        var tr = el("tr"); tr.appendChild(css(el("th", null, ""), {textAlign: "left", fontWeight: "500", color: C.faint, padding: "6px 0", borderBottom: "1px solid " + C.line}));
        periods.forEach(function(p){ tr.appendChild(css(el("th", null, p[1]), {textAlign: "right", fontWeight: "600", color: C.muted, padding: "6px 0", borderBottom: "1px solid " + C.line})); });
        t.appendChild(tr);
        var rows = [["Dials", function(b){ return b.dials; }], ["Reached", function(b){ return b.connects + (b.dials ? " · " + b.reach_rate + "%" : ""); }],
                    ["Interested", function(b){ return b.interested; }], ["Wins", function(b){ return b.wins; }],
                    ["Texts sent", function(b){ return b.texts ? b.texts.sent : 0; }],
                    ["Callbacks kept", function(b){ return b.callbacks ? (b.callbacks.kept + " of " + b.callbacks.set) : "0"; }]];
        rows.forEach(function(r, i){
          var row = el("tr");
          row.appendChild(css(el("td", null, r[0]), {padding: "7px 0", color: C.muted, borderBottom: "1px solid " + C.line}));
          rs.forEach(function(x){
            var v = r[1](x.body);
            var td = el("td", null, String(v));
            css(td, {padding: "7px 0", textAlign: "right", fontVariantNumeric: "tabular-nums", borderBottom: "1px solid " + C.line,
                     color: (i === 3 && x.body.wins) ? C.accent : C.ink, fontWeight: i === 0 || i === 3 ? "700" : "500"});
            row.appendChild(td);
          });
          t.appendChild(row);
        });
        panel.appendChild(t);
        if(isManager()){
          var a = el("a", null, "Open the manager page"); a.href = "/va/manager";
          css(a, {display: "inline-block", marginTop: "12px", color: C.blue, fontSize: "13px", textDecoration: "none", borderBottom: "1px solid " + C.blue});
          panel.appendChild(a);
        }
      });
  }

  // ---- Scorecard under the copilot summary ---------------------------------
  var lastSid = null;
  function mountScore(){
    var sum = document.getElementById("cp-sum");
    if(!sum || sum.dataset.scoreWired) return;
    sum.dataset.scoreWired = "1";
    var mo = new MutationObserver(function(){ if(!sum.hidden) fetchScore(sum, 0); });
    mo.observe(sum, {attributes: true, attributeFilter: ["hidden"]});
  }
  function fetchScore(sum, attempt){
    var co = document.getElementById("c-company"), ph = document.getElementById("c-phone");
    var body = {company: co ? co.textContent.trim() : "", phone: ph ? ph.textContent.trim() : ""};
    post("/api/va/coaching/scorecard", body).then(function(r){
      if(r.status !== 200 || !r.body.score){
        if(attempt < 3) setTimeout(function(){ if(!sum.hidden) fetchScore(sum, attempt + 1); }, 3000);
        return;
      }
      renderScore(sum, r.body.score);
    }).catch(function(){});
  }
  function renderScore(sum, s){
    var old = document.getElementById("cp-score"); if(old) old.remove();
    var box = el("div"); box.id = "cp-score";
    css(box, {margin: "6px 0 10px", padding: "8px 0 0", borderTop: "1px solid " + C.line});
    var head = css(el("div"), {display: "flex", alignItems: "baseline", gap: "8px", marginBottom: "6px"});
    head.appendChild(css(el("span", null, "Call score"), {color: C.faint, fontSize: "11.5px"}));
    head.appendChild(css(el("b", null, s.total + " / 25"), {color: C.ink, fontSize: "13px"}));
    if(s.reviewed) head.appendChild(css(el("span", null, "reviewed"), {color: C.ok, fontSize: "11.5px"}));
    box.appendChild(head);
    var labels = {opener: "Open", discovery: "Ask", objection: "Answer", close: "Close", compliance: "Notice"};
    var bars = css(el("div"), {display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "6px"});
    ["opener", "discovery", "objection", "close", "compliance"].forEach(function(k){
      var v = (s.scores && s.scores[k]) || 0;
      var cell = el("div");
      var track = css(el("div"), {height: "6px", borderRadius: "3px", background: C.raise, overflow: "hidden"});
      track.appendChild(css(el("div"), {height: "100%", width: (v * 20) + "%", borderRadius: "3px", background: v <= 2 ? C.accent : C.blue}));
      cell.appendChild(track);
      cell.appendChild(css(el("div", null, labels[k] + " " + v), {color: C.faint, fontSize: "10.5px", marginTop: "3px", whiteSpace: "nowrap"}));
      cell.title = k + ": " + v + " of 5";
      bars.appendChild(cell);
    });
    box.appendChild(bars);
    if(s.top_fix){
      var fix = css(el("div"), {marginTop: "7px", fontSize: "13px", lineHeight: "1.4", color: C.ink});
      fix.appendChild(css(el("span", null, "Next time: "), {color: C.accent, fontWeight: "700"}));
      fix.appendChild(document.createTextNode(s.top_fix));
      box.appendChild(fix);
    }
    var btns = sum.querySelector(".cp-sum-btns");
    if(btns) sum.insertBefore(box, btns); else sum.appendChild(box);
  }

  function init(){ try { mountStats(); mountScore(); } catch(e){ /* the desk keeps working without stats */ } }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
