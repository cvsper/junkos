/* Sign-in gate corridor: builds the two rails of Umuve cards behind the
   form. Nothing here touches the form or its script hooks. Styles live in
   /static/desk-gate.css (the desk CSP is style-src 'self'). */
(function(){
  "use strict";
  var CARDS = 9, IMAGES = 7;
  function build(){
    var gate = document.getElementById("gate");
    if(!gate || !gate.classList.contains("gate") || gate.querySelector(".gc")) return;
    var gc = document.createElement("div"); gc.className = "gc"; gc.setAttribute("aria-hidden", "true");
    var stage = document.createElement("div"); stage.className = "gc-stage";
    ["gc-r", "gc-l"].forEach(function(side){
      var rail = document.createElement("div"); rail.className = "gc-rail " + side;
      for(var i = 0; i < CARDS; i++){
        var card = document.createElement("div"); card.className = "gc-card";
        var img = document.createElement("img");
        img.src = "/static/gate/card-" + ((i % IMAGES) + 1) + ".jpg"; img.alt = ""; img.loading = "lazy"; img.decoding = "async"; img.draggable = false;
        card.appendChild(img); rail.appendChild(card);
      }
      stage.appendChild(rail);
    });
    gc.appendChild(stage);
    var veil = document.createElement("div"); veil.className = "gc-veil"; gc.appendChild(veil);
    gate.insertBefore(gc, gate.firstChild);
  }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", build); else build();
})();
