/* Call Desk — weekly improvement class. Asks the desk for the VA's open
   class; when one is assigned it covers the desk until she reads it,
   answers the three questions, and writes one line about Monday. Managers
   and the shared passcode never get blocked. Loads after /va/calls.js;
   nothing here breaks the desk if the endpoint is missing. */
(function(){
  var JWT_KEY = "umuve_desk_jwt", ME_KEY = "umuve_desk_me", KEY = "umuve_coach_code", VA_KEY = "umuve_va_name", SNOOZE_KEY = "umuve_class_snooze";
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
  function snoozedUntil(){ try { return Number(localStorage.getItem(SNOOZE_KEY) || 0); } catch(e){ return 0; } }
  function snooze(hours){ try { localStorage.setItem(SNOOZE_KEY, String(Date.now() + hours * 3600 * 1000)); } catch(e){} }
  var LABEL = {opener: "the opener", discovery: "discovery questions", objection: "handling objections", close: "the close", compliance: "the recording notice"};

  var overlay = null, current = null;

  function quoteBlock(text, tone){
    var q = el("blockquote", "cl-quote" + (tone ? " " + tone : ""));
    q.appendChild(el("span", null, "“" + text + "”"));
    return q;
  }

  function render(data){
    var c = data["class"], lesson = c.lesson || {};
    if(overlay){ overlay.remove(); }
    overlay = el("div", "cl-overlay"); overlay.id = "class-overlay";
    var card = el("div", "cl-card");
    var head = el("div", "cl-head");
    head.appendChild(el("div", "cl-eyebrow", "Your weekly class · week of " + c.week_start + (data.overdue ? " · overdue" : "")));
    head.appendChild(el("h2", "cl-title", lesson.title || "This week's class"));
    var meta = el("div", "cl-meta", c.calls + " scored call" + (c.calls === 1 ? "" : "s") + " · averaging " + (c.avg_total == null ? "–" : c.avg_total) + "/25 · focus: " + (LABEL[c.weakest] || c.weakest));
    head.appendChild(meta);
    if(lesson.summary) head.appendChild(el("p", "cl-summary", lesson.summary));
    card.appendChild(head);

    // rubric strip
    var dims = c.dims || {}, strip = el("div", "cl-dims");
    Object.keys(dims).forEach(function(d){
      var it = el("div", "cl-dim" + (d === c.weakest ? " is-weak" : "")); it.appendChild(el("b", null, String(dims[d]))); it.appendChild(el("span", null, d)); strip.appendChild(it);
    });
    card.appendChild(strip);

    var well = el("section", "cl-sec"); well.appendChild(el("h3", null, "What went well"));
    (lesson.went_well || []).forEach(function(w){
      var it = el("div", "cl-item ok"); it.appendChild(el("p", null, w.point)); if(w.quote) it.appendChild(quoteBlock(w.quote, "ok")); well.appendChild(it);
    });
    if(!(lesson.went_well || []).length) well.appendChild(el("p", "cl-dim-text", "Not enough on the transcripts to quote you — more talk time next week."));
    card.appendChild(well);

    var fix = el("section", "cl-sec"); fix.appendChild(el("h3", null, "What to fix"));
    (lesson.fix || []).forEach(function(f, i){
      var it = el("div", "cl-item fix"); it.appendChild(el("p", null, (i + 1) + ". " + f.point));
      if(f.quote){ it.appendChild(el("div", "cl-lbl", "You said")); it.appendChild(quoteBlock(f.quote, "warn")); }
      if(f.say_instead){ it.appendChild(el("div", "cl-lbl", "Say instead")); it.appendChild(quoteBlock(f.say_instead, "ok")); }
      fix.appendChild(it);
    });
    card.appendChild(fix);

    if(lesson.drill && lesson.drill.line){
      var drill = el("section", "cl-sec cl-drill"); drill.appendChild(el("h3", null, "60-second drill"));
      drill.appendChild(quoteBlock(lesson.drill.line, "ok"));
      if(lesson.drill.why) drill.appendChild(el("p", "cl-dim-text", lesson.drill.why));
      card.appendChild(drill);
    }

    var form = el("form", "cl-sec cl-quiz"); form.appendChild(el("h3", null, "Quick check"));
    (lesson.quiz || []).forEach(function(q, qi){
      var box = el("fieldset", "cl-q"); box.appendChild(el("legend", null, (qi + 1) + ". " + q.q));
      (q.options || []).forEach(function(o, oi){
        var lab = el("label", "cl-opt"); var inp = el("input"); inp.type = "radio"; inp.name = "q" + qi; inp.value = String(oi); inp.required = true;
        lab.appendChild(inp); lab.appendChild(el("span", null, o)); box.appendChild(lab);
      });
      form.appendChild(box);
    });
    var refl = el("textarea", "cl-refl"); refl.id = "cl-refl"; refl.rows = 3; refl.required = true; refl.minLength = 10;
    refl.placeholder = "One line: what will you do differently on Monday's first call?";
    form.appendChild(el("h3", null, "Your one line")); form.appendChild(refl);
    var errp = el("p", "cl-err"); errp.hidden = true; form.appendChild(errp);
    var row = el("div", "cl-btns");
    var submit = el("button", "si-btn cl-primary", "Finish the class"); submit.type = "submit"; row.appendChild(submit);
    if(!data.overdue){ var later = el("button", "si-btn", "Not now (4 hours)"); later.type = "button"; later.addEventListener("click", function(){ snooze(4); close(); }); row.appendChild(later); }
    form.appendChild(row);
    form.addEventListener("submit", function(ev){
      ev.preventDefault();
      var answers = (lesson.quiz || []).map(function(q, qi){ var chk = form.querySelector("input[name=q" + qi + "]:checked"); return chk ? Number(chk.value) : null; });
      submit.disabled = true; errp.hidden = true;
      post("/api/va/coaching/class/complete", {class_id: c.id, answers: answers, reflection: refl.value.trim()}).then(function(r){
        submit.disabled = false;
        if(r.status !== 200){ errp.textContent = (r.body && r.body.error) || "Couldn't save. Try again."; errp.hidden = false; return; }
        showResults(r.body);
      }).catch(function(){ submit.disabled = false; errp.textContent = "Couldn't reach the desk."; errp.hidden = false; });
    });
    card.appendChild(form);
    overlay.appendChild(card);
    document.body.appendChild(overlay);
    document.body.classList.add("cl-locked");
  }

  function showResults(res){
    var card = overlay.querySelector(".cl-card"); card.textContent = "";
    var head = el("div", "cl-head");
    head.appendChild(el("div", "cl-eyebrow", "Class complete"));
    head.appendChild(el("h2", "cl-title", res.score + " of " + res.of + " right"));
    head.appendChild(el("p", "cl-summary", res.score === res.of ? "Clean sweep. Now go do it on the phone." : "Read the ones you missed — they're the point of the week."));
    card.appendChild(head);
    (res.results || []).forEach(function(r, i){
      var it = el("div", "cl-item " + (r.correct ? "ok" : "fix")); it.appendChild(el("p", null, (i + 1) + ". " + r.q));
      it.appendChild(el("div", "cl-lbl", r.correct ? "Right" : "Not quite")); it.appendChild(el("p", "cl-dim-text", r.why || "")); card.appendChild(it);
    });
    var done = el("button", "si-btn cl-primary", "Back to the desk"); done.type = "button"; done.addEventListener("click", close);
    var row = el("div", "cl-btns"); row.appendChild(done); card.appendChild(row);
  }

  function close(){ if(overlay){ overlay.remove(); overlay = null; } document.body.classList.remove("cl-locked"); }

  function check(){
    if(!jwt() && !code()) return;
    post("/api/va/coaching/class/current", {}).then(function(r){
      if(r.status !== 200 || !r.body || !r.body["class"]) return;
      current = r.body;
      if(!r.body.blocking) return;
      if(!r.body.overdue && snoozedUntil() > Date.now()) return;
      if(!overlay) render(r.body);
    }).catch(function(){});
  }

  function init(){ try { check(); setInterval(check, 30 * 60 * 1000); } catch(e){ /* desk keeps working */ } }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
