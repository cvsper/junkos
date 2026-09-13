/* Sign-in gate: drops the aurora layer behind the form. Nothing here
   touches the form or its script hooks. Styles: /static/desk-gate.css. */
(function(){
  "use strict";
  function build(){
    var gate = document.getElementById("gate");
    if(!gate || !gate.classList.contains("gate") || gate.querySelector(".au-wrap")) return;
    var wrap = document.createElement("div"); wrap.className = "au-wrap"; wrap.setAttribute("aria-hidden", "true");
    var au = document.createElement("div"); au.className = "au"; wrap.appendChild(au);
    gate.insertBefore(wrap, gate.firstChild);
  }
  if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", build); else build();
})();
