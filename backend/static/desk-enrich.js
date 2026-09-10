/* Live Google listing under the card's meta line: rating, reviews, open now,
   website, Maps. Fetched when a card is dealt; the server caches it a week. */
(function(){
  var JWT_KEY = "umuve_desk_jwt", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name";
  function jwt(){ return localStorage.getItem(JWT_KEY) || ""; }
  function post(path, body){
    body = body || {};
    var headers = {"Content-Type": "application/json"};
    if(jwt()) headers["Authorization"] = "Bearer " + jwt();
    else { body.code = localStorage.getItem(KEY) || ""; body.va_name = localStorage.getItem(VA_KEY) || ""; }
    return fetch(path, {method: "POST", headers: headers, body: JSON.stringify(body)})
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, body: j}; }); });
  }
  function el(tag, cls, text){ var e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; }
  var st = document.createElement("style"); document.head.appendChild(st);
  [".en-line{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;margin:-8px 0 12px;font-size:12.5px;color:var(--muted)}",
   ".en-line b{font-family:var(--display);font-weight:700;color:var(--ink)}",
   ".en-line .star{color:#F5B301}.en-line .open{color:var(--ok);font-family:var(--display);font-weight:700}.en-line .closed{color:#FF7A5C;font-family:var(--display);font-weight:700}",
   ".en-line a{color:#7FB8FF;text-decoration:none}.en-line a:hover{text-decoration:underline}",
   ".en-line.dim{color:var(--faint)}"
  ].forEach(function(r){ try { st.sheet.insertRule(r, st.sheet.cssRules.length); } catch(e){} });

  var line = null, lastKey = "";
  function ensure(){
    var meta = document.getElementById("c-meta"); if(!meta) return null;
    if(line && document.body.contains(line)) return line;
    line = el("div", "en-line"); line.hidden = true;
    meta.parentNode.insertBefore(line, meta.nextSibling);
    return line;
  }
  function render(d){
    var l = ensure(); if(!l) return;
    l.textContent = ""; l.className = "en-line";
    if(!d.found){ l.className += " dim"; l.textContent = d.reason === "no places key" ? "" : "No Google listing found for this name."; l.hidden = !l.textContent; return; }
    if(d.rating){ var r = el("span"); r.appendChild(el("span", "star", "★ ")); r.appendChild(el("b", null, String(d.rating))); r.appendChild(document.createTextNode(" · " + (d.reviews || 0) + " reviews")); l.appendChild(r); }
    else if(d.found){ l.appendChild(el("span", null, "No reviews yet")); }
    if(d.open_now === true) l.appendChild(el("span", "open", "Open now"));
    else if(d.open_now === false) l.appendChild(el("span", "closed", "Closed now"));
    if(d.hours_today) l.appendChild(el("span", null, d.hours_today.replace(/^[A-Za-z]+: /, "Today ")));
    if(d.status && d.status !== "OPERATIONAL") l.appendChild(el("span", "closed", d.status.replace(/_/g, " ").toLowerCase()));
    if(d.type) l.appendChild(el("span", null, d.type));
    if(d.website){ var a = el("a", null, d.website.replace(/^https?:\/\//, "").replace(/\/$/, "")); a.href = d.website; a.target = "_blank"; a.rel = "noopener"; l.appendChild(a); }
    if(d.maps){ var m = el("a", null, "Maps"); m.href = d.maps; m.target = "_blank"; m.rel = "noopener"; l.appendChild(m); }
    l.hidden = false;
  }
  function refresh(){
    var co = document.getElementById("c-company"), ph = document.getElementById("c-phone");
    if(!co || !ph) return;
    var key = co.textContent + "|" + ph.textContent;
    if(!co.textContent || key === lastKey) return;
    lastKey = key;
    var l = ensure(); if(l){ l.hidden = false; l.className = "en-line dim"; l.textContent = "Looking them up on Google…"; }
    post("/api/va/calls/enrich", {company: co.textContent, phone: ph.textContent}).then(function(r){
      if(r.status !== 200){ if(l) l.hidden = true; return; }
      render(r.body);
    }).catch(function(){ if(l) l.hidden = true; });
  }
  var co = document.getElementById("c-company");
  if(co){ new MutationObserver(function(){ setTimeout(refresh, 150); }).observe(co, {childList: true, characterData: true, subtree: true}); }
  setTimeout(refresh, 1500);
})();
