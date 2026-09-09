/* Call Desk CRM layer (Phase 3): stage chip, tags, claiming, note history,
   account link. Loads before /va/calls.js and never touches its code —
   it reads the card from the same JSON the desk fetches, then decorates the
   card once calls.js has drawn it (MutationObserver on #c-company). */
(function(){
  "use strict";
  var JWT_KEY = "umuve_desk_jwt", CODE_KEY = "umuve_coach_code", VA_KEY = "umuve_va_name", ME_KEY = "umuve_desk_me";
  var CARD_PATHS = /\/api\/va\/calls\/(next|log|callback|get)(\?|$)/;
  var RENEW_MS = 5 * 60 * 1000;
  var LABELS = {interested: "Interested", sent_link: "Sent the link", vendor_listed: "On their vendor list",
                voicemail: "Voicemail", no_answer: "No answer", not_interested: "Not interested",
                bad_number: "Bad number", converted: "Converted", callback: "Callback set", skip: "Skipped",
                opted_out: "Opted out"};
  var STAGE_WORD = {new: "New", contacted: "Contacted", engaged: "Engaged", qualified: "Qualified",
                    won: "Won", lost: "Lost", nurture: "Nurture"};

  // ---- stylesheet (CSP: style-src 'self', so link it rather than inline it)
  var link = document.createElement("link");
  link.rel = "stylesheet"; link.href = "/static/desk-crm.css?v=1";
  document.head.appendChild(link);

  // ---- auth mirrors calls.js
  function jwt(){ return localStorage.getItem(JWT_KEY) || ""; }
  function me(){ try { return JSON.parse(localStorage.getItem(ME_KEY) || "null"); } catch(e){ return null; } }
  function vaName(){ var m = me(); return (m && m.name) || localStorage.getItem(VA_KEY) || ""; }
  function post(path, body, opts){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { body.code = localStorage.getItem(CODE_KEY) || ""; body.va_name = vaName(); }
    var init = {method: "POST", headers: headers, body: JSON.stringify(body)};
    if(opts && opts.keepalive) init.keepalive = true;
    return nativeFetch(path, init).then(function(r){
      return r.json().then(function(j){ return {status: r.status, body: j}; }, function(){ return {status: r.status, body: {}}; });
    });
  }

  // ---- watch the desk's own card fetches
  var nativeFetch = window.fetch.bind(window);
  var pending = null;        // card JSON we have not drawn yet
  var shown = null;          // card currently decorated
  window.fetch = function(input, init){
    var url = typeof input === "string" ? input : (input && input.url) || "";
    var p = nativeFetch(input, init);
    if(CARD_PATHS.test(url)){
      p.then(function(r){
        if(!r.ok) return;
        r.clone().json().then(function(j){
          if(j && j.card){ pending = j.card; tryDraw(); }
          else if(j && j.empty){ pending = null; onEmpty(); }
        }, function(){});
      }, function(){});
    }
    return p;
  };

  function tryDraw(){
    var co = document.getElementById("c-company");
    if(!pending || !co) return;
    if(co.textContent !== pending.company) return;   // calls.js hasn't drawn it yet
    var card = pending; pending = null;
    draw(card);
  }
  function observe(){
    var co = document.getElementById("c-company");
    if(!co) return;
    new MutationObserver(function(){ tryDraw(); }).observe(co, {childList: true, characterData: true, subtree: true});
  }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", observe);
  else observe();

  // ---- helpers
  function el(tag, cls, text){
    var e = document.createElement(tag);
    if(cls) e.className = cls;
    if(text != null) e.textContent = text;
    return e;
  }
  function ensure(id, tag, cls, after){
    var e = document.getElementById(id);
    if(e) return e;
    e = el(tag, cls); e.id = id;
    if(after && after.parentNode) after.parentNode.insertBefore(e, after.nextSibling);
    return e;
  }
  function ago(iso){
    if(!iso) return "";
    var t = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z");
    var s = Math.max(0, (Date.now() - t.getTime()) / 1000);
    if(s < 60) return "just now";
    if(s < 3600) return Math.round(s / 60) + "m ago";
    if(s < 86400) return Math.round(s / 3600) + "h ago";
    if(s < 14 * 86400) return Math.round(s / 86400) + "d ago";
    return t.toLocaleDateString([], {month: "short", day: "numeric"});
  }
  function toast(msg){
    var t = document.getElementById("desk-toast");
    if(!t) return;
    t.textContent = msg; t.hidden = false;
    setTimeout(function(){ t.hidden = true; }, 4000);
  }

  // ---- draw
  function draw(card){
    var changed = !shown || shown.id !== card.id;
    if(changed && shown) releaseClaim(shown.id);
    shown = card;
    drawStage(card);
    drawTags(card);
    drawHistory(card);
    if(changed) claimCard(card.id);
    else if(card.claimed_by && card.claimed_by !== vaName()) drawClaim(card);
  }

  function drawStage(card){
    var row = document.querySelector("#card .chiprow");
    if(!row) return;
    var chip = document.getElementById("crm-stage");
    if(!chip){ chip = el("span", "chip crm-stage"); chip.id = "crm-stage"; row.appendChild(chip); }
    chip.textContent = STAGE_WORD[card.stage] || card.stage || "New";
    chip.dataset.stage = card.stage || "new";
    var days = card.stage_age_days || 0;
    if(days >= 1 && card.stage !== "won" && card.stage !== "lost"){
      chip.appendChild(el("span", "crm-age", days + "d"));
    }
  }

  function drawClaim(card, holder){
    var meta = document.getElementById("c-meta");
    var box = ensure("crm-claim", "div", "crm-claim", meta);
    var who = (holder && holder.claimed_by) || card.claimed_by;
    var until = (holder && holder.claimed_until) || card.claimed_until;
    var mins = holder && holder.minutes_left != null ? holder.minutes_left
             : until ? Math.max(0, Math.round((new Date(until.endsWith("Z") ? until : until + "Z") - Date.now()) / 60000)) : 0;
    box.textContent = "";
    box.appendChild(el("b", null, who));
    box.appendChild(document.createTextNode(" is on this card right now"));
    box.appendChild(el("span", "crm-left", mins + " min left"));
    box.hidden = false;
  }
  function hideClaim(){ var b = document.getElementById("crm-claim"); if(b) b.hidden = true; }

  function drawTags(card){
    var meta = document.getElementById("c-meta");
    var wrap = ensure("crm-tags", "div", "crm-tags", meta);
    // keep the claim notice directly under meta
    var claimBox = document.getElementById("crm-claim");
    if(claimBox && claimBox.nextSibling !== wrap) meta.parentNode.insertBefore(wrap, claimBox.nextSibling);
    wrap.textContent = "";
    (card.tags || []).forEach(function(t){
      var pill = el("span", "crm-tag", t);
      var x = el("button", null, "×"); x.type = "button"; x.title = "Remove " + t;
      x.setAttribute("aria-label", "Remove tag " + t);
      x.addEventListener("click", function(){ changeTags(card.id, [], [t]); });
      pill.appendChild(x); wrap.appendChild(pill);
    });
    var add = el("span", "crm-tag-add");
    var inp = el("input"); inp.type = "text"; inp.placeholder = "add a tag"; inp.maxLength = 40;
    inp.autocomplete = "off"; inp.setAttribute("list", "crm-tag-list"); inp.id = "crm-tag-input";
    var dl = document.getElementById("crm-tag-list");
    if(!dl){ dl = el("datalist"); dl.id = "crm-tag-list"; document.body.appendChild(dl); }
    inp.addEventListener("input", function(){ suggest(inp.value, dl); });
    inp.addEventListener("keydown", function(e){
      if(e.key === "Enter"){ e.preventDefault(); var v = inp.value.trim(); if(v){ changeTags(card.id, [v], []); inp.value = ""; } }
    });
    add.appendChild(inp); wrap.appendChild(add);
    // account
    var acct = el("span", "crm-acct");
    if(card.account){
      acct.appendChild(document.createTextNode("account "));
      acct.appendChild(el("b", null, card.account.name));
    } else {
      var b = el("button", null, "Link to an account"); b.type = "button"; b.id = "crm-acct-link";
      b.addEventListener("click", function(){ linkAccount(card); });
      acct.appendChild(b);
    }
    wrap.appendChild(acct);
  }

  var suggestTimer = null;
  function suggest(q, dl){
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(function(){
      post("/api/va/crm/tag-suggest", {q: q}).then(function(r){
        if(r.status !== 200) return;
        dl.textContent = "";
        (r.body.tags || []).forEach(function(t){ var o = el("option"); o.value = t.tag; dl.appendChild(o); });
      }).catch(function(){});
    }, 150);
  }
  function changeTags(id, add, remove){
    post("/api/va/crm/tags", {prospect_id: id, add: add, remove: remove}).then(function(r){
      if(r.status !== 200){ toast((r.body && r.body.error) || "Couldn't save the tag."); return; }
      if(shown && shown.id === id){ shown.tags = r.body.tags; drawTags(shown); }
      var inp = document.getElementById("crm-tag-input"); if(inp && add.length) inp.focus();
    }).catch(function(){ toast("No connection — the tag didn't save."); });
  }
  function linkAccount(card){
    post("/api/va/crm/account", {prospect_id: card.id}).then(function(r){
      if(r.status !== 200){ toast((r.body && r.body.error) || "Couldn't link the account."); return; }
      if(shown && shown.id === card.id){ shown.account = {id: r.body.account.id, name: r.body.account.name}; drawTags(shown); }
      toast((r.body.created ? "Account created: " : "Linked to ") + r.body.account.name);
    }).catch(function(){ toast("No connection — try again."); });
  }

  function drawHistory(card){
    var note = document.getElementById("c-lastnote");
    var box = ensure("crm-hist", "div", "crm-hist", note);
    var rows = card.history || [];
    if(!rows.length){ box.hidden = true; return; }
    box.hidden = false; box.textContent = "";
    box.appendChild(el("b", "crm-hist-t", rows.length === 1 ? "Earlier call" : "Earlier calls"));
    var ol = el("ol");
    rows.forEach(function(h, i){
      var li = el("li");
      var oc = el("span", "crm-oc", LABELS[h.outcome] || h.outcome); oc.dataset.o = h.outcome;
      li.appendChild(oc);
      li.appendChild(el("span", "crm-who", (h.va_name || "desk") + " · " + ago(h.created_at)));
      li.appendChild(el("span", "crm-note", h.note || ""));
      if(i >= 3) li.hidden = true;
      ol.appendChild(li);
    });
    box.appendChild(ol);
    if(rows.length > 3){
      var more = el("button", "crm-more", "Show " + (rows.length - 3) + " more"); more.type = "button";
      more.addEventListener("click", function(){
        var hidden = ol.querySelectorAll("li[hidden]").length > 0;
        ol.querySelectorAll("li").forEach(function(li, i){ if(i >= 3) li.hidden = !hidden; });
        more.textContent = hidden ? "Show fewer" : "Show " + (rows.length - 3) + " more";
      });
      box.appendChild(more);
    }
  }

  // ---- claims
  var renewTimer = null, claimedId = null;
  function claimCard(id){
    clearInterval(renewTimer);
    post("/api/va/crm/claim", {prospect_id: id}).then(function(r){
      if(!shown || shown.id !== id) return;
      if(r.status === 409){ drawClaim(shown, r.body); claimedId = null; return; }
      if(r.status !== 200) return;
      hideClaim(); claimedId = id;
      renewTimer = setInterval(function(){
        if(claimedId !== id || document.hidden) return;
        post("/api/va/crm/claim", {prospect_id: id}).then(function(rr){
          if(rr.status === 409 && shown && shown.id === id) drawClaim(shown, rr.body);
        }).catch(function(){});
      }, RENEW_MS);
    }).catch(function(){});
  }
  function releaseClaim(id){
    clearInterval(renewTimer);
    if(claimedId !== id){ claimedId = null; return; }
    claimedId = null;
    post("/api/va/crm/release", {prospect_id: id}, {keepalive: true}).catch(function(){});
  }
  function onEmpty(){
    if(shown) releaseClaim(shown.id);
    shown = null; hideClaim();
  }
  window.addEventListener("pagehide", function(){ if(claimedId) releaseClaim(claimedId); });
})();
