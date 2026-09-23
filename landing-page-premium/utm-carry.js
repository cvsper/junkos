/* Keep the ad's tracking tag on the way into the app.
   An ad lands people on goumuve.com/?utm_source=meta&…; the Book button
   goes to app.goumuve.com/book with nothing, so the booking funnel called
   those visitors "direct". This remembers the utm_* values for the session
   and appends them to every link into the app. */
(function () {
  var KEY = "umuve_utm";
  var keep = {};
  try {
    var q = new URLSearchParams(location.search);
    q.forEach(function (v, k) { if (/^utm_/.test(k) && v) keep[k] = v; });
    // Meta appends fbclid to every ad click even when the ad link carried no tag.
    if (!keep.utm_source && q.get("fbclid")) { keep.utm_source = "meta"; keep.utm_medium = "paid"; }
    if (Object.keys(keep).length) sessionStorage.setItem(KEY, JSON.stringify(keep));
    else keep = JSON.parse(sessionStorage.getItem(KEY) || "{}");
  } catch (e) { keep = {}; }
  if (!Object.keys(keep).length) return;
  function decorate(a) {
    var href = a.getAttribute("href") || "";
    if (!/app\.goumuve\.com|^\/book/.test(href)) return;
    try {
      var u = new URL(href, location.origin);
      Object.keys(keep).forEach(function (k) { if (!u.searchParams.has(k)) u.searchParams.set(k, keep[k]); });
      a.setAttribute("href", u.toString());
    } catch (e) {}
  }
  function run() { Array.prototype.forEach.call(document.querySelectorAll("a[href]"), decorate); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();
