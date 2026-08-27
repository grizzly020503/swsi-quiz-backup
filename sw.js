/* 社工題庫 Service Worker
   策略：
   - HTML（index.html / 導覽請求）：強制 no-store 網路優先 → 線上拿最新版，離線才用快取。
   - auto/ 考選部增量題庫：網路優先 → 有新考次立即更新，離線使用最近快取。
   - 會影響判題／內容的可變靜態檔（monthly patch、essay guides、manifest）：no-store 網路優先。
   - 圖示等真正靜態資產：快取優先。
   - 跨網域（Cloudflare 題庫 shard、Supabase、AI）：完全不攔截，永遠走網路；題庫離線由 IndexedDB 處理。
*/
const VERSION = 'v6';
const CACHE = 'swsi-shell-' + VERSION;
const SHELL = [
  './',
  './index.html',
  './monthly_patch.js',
  './essay_guides.js',
  './manifest.json',
  './apple-touch-icon.png',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './auto/questions_auto.json',
  './auto/essays_auto.json',
  './auto/sync_state.json'
];

function cleanupStaleCaches() {
  return caches.keys().then(function (keys) {
    return Promise.all(keys.map(function (k) {
      if (k !== CACHE) return caches.delete(k);
      return false;
    }));
  });
}

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE)
      .then(function (c) { return c.addAll(SHELL); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  // 先清一次，再 claim clients 後再清一次。舊 worker 可能在交接瞬間完成
  // 尚未結束的 cache write；第二次清理用來關掉這個 upgrade race。
  e.waitUntil(
    cleanupStaleCaches()
      .then(function () { return self.clients.claim(); })
      .then(function () { return cleanupStaleCaches(); })
  );
});

function networkFirst(req, fallback, noStore) {
  var init = noStore ? { cache: 'no-store' } : undefined;
  return fetch(req, init).then(function (res) {
    if (res && res.ok) {
      var copy = res.clone();
      caches.open(CACHE).then(function (c) { c.put(req, copy); });
    }
    return res;
  }).catch(function () {
    return caches.match(req).then(function (r) {
      if (r) return r;
      return fallback ? caches.match(fallback) : undefined;
    });
  });
}

function networkFirstAfterCleanup(req, fallback, noStore) {
  return cleanupStaleCaches().then(function () {
    return networkFirst(req, fallback, noStore);
  });
}

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') { return; }

  var url;
  try { url = new URL(req.url); } catch (err) { return; }

  // 只處理同網域；Cloudflare shard / Supabase / AI 等外部 API 一律放行走網路。
  if (url.origin !== self.location.origin) { return; }

  var isDoc = req.mode === 'navigate'
    || req.destination === 'document'
    || url.pathname.endsWith('.html')
    || url.pathname === '/'
    || url.pathname.endsWith('/');

  var isAuto = url.pathname.includes('/auto/');
  var isMutableStatic = url.pathname.endsWith('/monthly_patch.js')
    || url.pathname.endsWith('/essay_guides.js')
    || url.pathname.endsWith('/manifest.json');

  if (isDoc) {
    e.respondWith(networkFirstAfterCleanup(req, './index.html', true));
    return;
  }

  if (isAuto) {
    e.respondWith(networkFirstAfterCleanup(req, null, true));
    return;
  }

  if (isMutableStatic) {
    e.respondWith(networkFirstAfterCleanup(req, null, true));
    return;
  }

  // 真正靜態資產仍採快取優先，同時利用請求生命週期清掉任何晚到的舊 cache。
  e.waitUntil(cleanupStaleCaches());
  e.respondWith(
    caches.match(req).then(function (r) {
      return r || fetch(req).then(function (res) {
        if (res && res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, copy); });
        }
        return res;
      });
    })
  );
});