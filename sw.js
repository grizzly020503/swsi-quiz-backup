/* 社工題庫 Service Worker
   策略：
   - HTML（index.html / 導覽請求）：網路優先 → 線上一定拿最新版，離線才用快取。
     （這樣可避免「卡在舊版」的問題：只要有網路，更新就會生效。）
   - 靜態檔（圖示、manifest）：快取優先，速度快。
   - 跨網域（Supabase 題庫、AI 評分）：完全不攔截，永遠走網路，功能照常。
   每次改版只要把下面 VERSION 數字 +1，舊快取就會自動清除。
*/
const VERSION = 'v1';
const CACHE = 'swsi-shell-' + VERSION;
const SHELL = [
  './',
  './index.html',
  './manifest.json',
  './apple-touch-icon.png',
  './icons/icon-192.png',
  './icons/icon-512.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE)
      .then(function (c) { return c.addAll(SHELL); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.map(function (k) {
          if (k !== CACHE) { return caches.delete(k); }
        }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') { return; }

  var url;
  try { url = new URL(req.url); } catch (err) { return; }

  // 只處理同網域；Supabase / Groq 等外部 API 一律放行走網路
  if (url.origin !== self.location.origin) { return; }

  var isDoc = req.mode === 'navigate'
    || req.destination === 'document'
    || url.pathname.endsWith('.html')
    || url.pathname === '/'
    || url.pathname.endsWith('/');

  if (isDoc) {
    // 網路優先：拿最新；失敗（離線）才用快取
    e.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
        return res;
      }).catch(function () {
        return caches.match(req).then(function (r) {
          return r || caches.match('./index.html');
        });
      })
    );
    return;
  }

  // 靜態檔：快取優先
  e.respondWith(
    caches.match(req).then(function (r) {
      return r || fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
        return res;
      });
    })
  );
});
