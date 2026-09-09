/* Umuve Call Desk — service worker.
   Served from /va/desk-sw.js (Service-Worker-Allowed: /va/) so it controls /va/calls.
   App shell: network-first with cache fallback. API: always network. Push → notification. */
var VERSION = "desk-shell-v1";
var SHELL = ["/va/calls", "/va/app.css", "/va/calls.css", "/va/calls.js", "/static/desk-growth.js"];

function isShell(url) {
  var p = url.pathname;
  if (p === "/va/calls" || p === "/va/app.css" || p === "/va/calls.css" || p === "/va/calls.js") return true;
  if (p.indexOf("/static/desk-") === 0 && p.slice(-3) === ".js") return true;
  return false;
}

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(VERSION).then(function (c) {
      return Promise.all(SHELL.map(function (u) {
        return fetch(u, {cache: "no-cache"}).then(function (r) { if (r.ok) return c.put(u, r); }).catch(function () {});
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.indexOf("/api/") === 0) return;            // API: always network
  if (!isShell(url)) return;
  var key = url.pathname;                                      // ignore ?v= busters
  e.respondWith(
    fetch(req).then(function (r) {
      if (r && r.ok) {
        var copy = r.clone();
        caches.open(VERSION).then(function (c) { c.put(key, copy); }).catch(function () {});
      }
      return r;
    }).catch(function () {
      return caches.match(key).then(function (hit) {
        return hit || new Response("Offline — the desk needs a connection.", {status: 503, headers: {"Content-Type": "text/plain"}});
      });
    })
  );
});

self.addEventListener("push", function (e) {
  var data = {};
  try { data = e.data ? e.data.json() : {}; } catch (err) { data = {body: e.data ? e.data.text() : ""}; }
  var title = data.title || "Call Desk";
  var opts = {
    body: data.body || "",
    tag: data.tag || "desk-reply",
    renotify: true,
    icon: "/static/icon-192.png",
    badge: "/static/icon-192.png",
    data: {url: (data.data && data.data.url) || "/va/calls"}
  };
  e.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || "/va/calls";
  e.waitUntil(
    self.clients.matchAll({type: "window", includeUncontrolled: true}).then(function (list) {
      for (var i = 0; i < list.length; i++) {
        if (list[i].url.indexOf("/va/calls") !== -1 && "focus" in list[i]) return list[i].focus();
      }
      return self.clients.openWindow(url);
    })
  );
});
