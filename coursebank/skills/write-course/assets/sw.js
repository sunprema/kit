/* CourseBank service worker — makes the course fully offline after one visit.
 * Copy verbatim into <course-dir>/sw.js; gen_offline_manifest.py stamps
 * CACHE_NAME with the course id + a content hash on every build, which is what
 * invalidates old caches when the course is regenerated. Scope is the course
 * directory (registered as './sw.js'), so many courses coexist on one origin.
 *
 * Strategy: precache the whole course (the offline.json file list) on install;
 * serve cache-first; anything fetched past the precache list is added to the
 * cache opportunistically. Courses are small, self-contained sites — total
 * precache is typically well under a few MB. */

var CACHE_NAME = 'cb-unstamped'; // stamped by gen_offline_manifest.py — do not edit

self.addEventListener('install', function (e) {
  e.waitUntil(
    fetch('./offline.json')
      .then(function (r) { return r.json(); })
      .then(function (m) {
        return caches.open(CACHE_NAME).then(function (c) { return c.addAll(m.files); });
      })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  // Drop this course's stale caches (older content hashes), leave other
  // courses' caches on the shared origin alone.
  var prefix = CACHE_NAME.replace(/-[^-]*$/, '-');
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys
        .filter(function (k) { return k.indexOf(prefix) === 0 && k !== CACHE_NAME; })
        .map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then(function (hit) {
      if (hit) return hit;
      return fetch(e.request).then(function (resp) {
        if (resp && resp.ok && new URL(e.request.url).origin === self.location.origin) {
          var copy = resp.clone();
          caches.open(CACHE_NAME).then(function (c) { c.put(e.request, copy); });
        }
        return resp;
      });
    })
  );
});
