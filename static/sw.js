'use strict';

const SHELL_CACHE = 'pair-shell-v1';
const SHELL = ['/', '/static/index.html', '/static/app.js', '/static/style.css', '/static/icon.svg', '/static/manifest.webmanifest'];
const STATIC_PATHS = new Set(SHELL.filter(path => path !== '/'));

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    const index = await fetch('/', { cache: 'reload', credentials: 'omit' });
    if (index.ok && index.headers.get('content-type')?.includes('text/html')) await cache.put('/', index);
    await Promise.all(SHELL.filter(path => path !== '/').map(async path => {
      const response = await fetch(path, { cache: 'reload', credentials: 'omit' });
      if (response.ok) await cache.put(path, response);
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith('pair-shell-') && key !== SHELL_CACHE).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || event.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  if (STATIC_PATHS.has(url.pathname)) {
    event.respondWith((async () => {
      const cached = await caches.match(url.pathname, { cacheName: SHELL_CACHE });
      if (cached) return cached;
      const response = await fetch(event.request);
      if (response.ok) {
        const cache = await caches.open(SHELL_CACHE);
        await cache.put(url.pathname, response.clone());
      }
      return response;
    })());
  } else if (event.request.mode === 'navigate' && url.pathname === '/') {
    event.respondWith((async () => {
      try {
        const response = await fetch(event.request);
        // Never persist a server-rendered authenticated page. The installed public shell is the only fallback.
        if (response.ok) return response;
      } catch { /* Fall back to the public app shell, not an API response. */ }
      return await caches.match('/', { cacheName: SHELL_CACHE }) || await caches.match('/static/index.html', { cacheName: SHELL_CACHE }) || new Response('Connect to download your training app.', { status: 503, headers: { 'Content-Type': 'text/plain' } });
    })());
  }
});

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('pair-training-v1', 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore('private', { keyPath: 'key' });
      request.result.createObjectStore('queue', { keyPath: 'client_id' });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
async function store(db, name, operation, value) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(name, ['get', 'all'].includes(operation) ? 'readonly' : 'readwrite');
    const target = tx.objectStore(name);
    const request = operation === 'get' ? target.get(value) : operation === 'all' ? target.getAll() : operation === 'put' ? target.put(value) : target.delete(value);
    let result;
    request.onsuccess = () => { result = request.result; };
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}
async function replay() {
  const db = await openDB();
  try {
    const active = await store(db, 'private', 'get', 'active_user');
    if (!active?.value) return;
    const response = await fetch('/api/session', { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Authentication required; queued workouts retained.');
    const session = await response.json();
    if (!session.user || String(session.user.id) !== String(active.value) || !session.csrf_token) throw new Error('Account mismatch; queued workouts retained.');
    await store(db, 'private', 'put', { key: `session:${active.value}`, value: session });
    const queue = (await store(db, 'queue', 'all')).filter(item => String(item.user_id) === String(active.value)).sort((a, b) => a.created_at.localeCompare(b.created_at));
    for (const item of queue) {
      const current = await store(db, 'private', 'get', 'active_user');
      if (String(current?.value) !== String(active.value)) throw new Error('Account changed; remaining queue retained.');
      const saved = await fetch('/api/workouts/log', { method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': session.csrf_token }, body: JSON.stringify(item.payload) });
      if (!saved.ok) throw new Error(`Sync failed (${saved.status}); queued workout retained.`);
      await store(db, 'queue', 'delete', item.client_id);
    }
    const dashboardResponse = await fetch('/api/dashboard', { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
    if (dashboardResponse.ok) {
      const dashboard = await dashboardResponse.json();
      const current = await store(db, 'private', 'get', 'active_user');
      if (String(current?.value) === String(active.value)) await store(db, 'private', 'put', { key: `dashboard:${active.value}`, value: dashboard, savedAt: new Date().toISOString() });
    }
  } finally {
    db.close();
    const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    clients.forEach(client => client.postMessage({ type: 'QUEUE_CHANGED' }));
  }
}
self.addEventListener('sync', event => {
  if (event.tag === 'pair-workout-sync') event.waitUntil(replay());
});
