'use strict';

(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const arr = value => Array.isArray(value) ? value : [];
  const num = value => value !== null && value !== '' && value !== undefined && Number.isFinite(Number(value)) ? Number(value) : null;
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const today = () => localDate(new Date());
  const localDate = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const dateObj = value => new Date(`${String(value).slice(0, 10)}T12:00:00`);
  const dateLabel = (value, options = { day: 'numeric', month: 'short' }) => {
    const date = dateObj(value);
    return Number.isNaN(date.getTime()) ? 'Date not set' : date.toLocaleDateString(undefined, options);
  };
  const addDays = (value, count) => { const date = dateObj(value); date.setDate(date.getDate() + count); return localDate(date); };
  const time = value => {
    const seconds = num(value);
    if (seconds === null) return 'Not measured';
    const rounded = Math.max(0, Math.round(seconds));
    return rounded >= 3600 ? `${Math.floor(rounded / 3600)}:${String(Math.floor(rounded / 60) % 60).padStart(2, '0')}:${String(rounded % 60).padStart(2, '0')}` : `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')}`;
  };
  const parseTime = (value, label = 'Time') => {
    const text = String(value || '').trim();
    if (!/^\d+:[0-5]\d(?::[0-5]\d)?$/.test(text)) throw new Error(`${label}: use M:SS or H:MM:SS (for example 5:30 or 1:20:00).`);
    return text.split(':').map(Number).reduce((total, part) => total * 60 + part, 0);
  };
  const titleCase = value => String(value ?? '').replace(/[_-]/g, ' ').replace(/\b\w/g, character => character.toUpperCase());
  const resetToken = () => new URLSearchParams(location.search).get('token') || new URLSearchParams(location.search).get('reset');
  const words = value => {
    if (value == null) return '';
    if (typeof value === 'string' || typeof value === 'number') return String(value);
    if (Array.isArray(value)) return value.map(words).filter(Boolean).join(' · ');
    return Object.entries(value).map(([key, item]) => `${titleCase(key)}: ${words(item)}`).join(' · ');
  };
  const paths = {
    home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M9 21v-8h6v8"/>',
    plan: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2"/>',
    workout: '<path d="M6 7v10m-3-8v6m15-8v10m3-8v6M6 12h12"/>',
    progress: '<path d="M4 4v16h17M7 14l5-5 4 3 5-7"/>',
    team: '<circle cx="8" cy="8" r="3"/><path d="M2 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m3 10v-3a6 6 0 0 0-3-5"/>',
    coach: '<path d="m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3z"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    back: '<path d="M20 12H4m6-6-6 6 6 6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z"/>',
    flag: '<path d="M5 21V4m0 0c5-4 9 4 14 0v10c-5 4-9-4-14 0"/>',
    settings: '<circle cx="12" cy="8" r="4"/><path d="M4 22v-2a8 8 0 0 1 16 0v2"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
    moon: '<path d="M21 13a9 9 0 1 1-10-10 7 7 0 0 0 10 10z"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    sync: '<path d="M20 7A9 9 0 0 0 4 6L2 9m0-6v6h6m-4 8a9 9 0 0 0 16 1l2-3m0 6v-6h-6"/>',
    leaf: '<path d="M20 3C8 2 3 7 5 15s14 7 15-12ZM4 21l10-11"/>',
    send: '<path d="m22 2-7 20-4-9L2 9zM22 2 11 13"/>',
    copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>'
  };
  const icon = name => `<svg class="icon" aria-hidden="true" viewBox="0 0 24 24">${paths[name] || paths.info}</svg>`;
  const state = { session: null, dashboard: null, offline: false, queue: [], syncError: '', authMode: 'login', filter: 'all', selectedDate: today(), week: today(), chat: [], theme: 'light', loading: false };
  let dbPromise;
  let syncPromise;
  let toastTimer;
  let worker;
  const withPrivateLock = operation => navigator.locks?.request ? navigator.locks.request('pair-private-sync', operation) : operation();
  function invalidateOtherTabs() {
    try { localStorage.setItem('pair-account-event', `${Date.now()}:${Math.random()}`); } catch { /* The server still rejects invalidated sessions when storage events are unavailable. */ }
  }
  try { state.theme = localStorage.getItem('pair-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); } catch { /* Storage can be unavailable in private browsing. */ }
  document.documentElement.dataset.theme = state.theme;

  function openDB() {
    if (!dbPromise) dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open('pair-training-v1', 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        db.createObjectStore('private', { keyPath: 'key' });
        db.createObjectStore('queue', { keyPath: 'client_id' });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Local storage is unavailable. Offline saving is disabled.'));
    });
    return dbPromise;
  }
  async function store(operation, name, value) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(name, ['get', 'all', 'keys'].includes(operation) ? 'readonly' : 'readwrite');
      const objectStore = tx.objectStore(name);
      let request;
      if (operation === 'get') request = objectStore.get(value);
      if (operation === 'all') request = objectStore.getAll();
      if (operation === 'keys') request = objectStore.getAllKeys();
      if (operation === 'put') request = objectStore.put(value);
      if (operation === 'delete') request = objectStore.delete(value);
      if (operation === 'clear') request = objectStore.clear();
      let result;
      request.onsuccess = () => { result = request.result; };
      tx.oncomplete = () => resolve(result);
      tx.onerror = () => reject(new Error('Your device could not save this data. Free some storage and try again.'));
      tx.onabort = () => reject(new Error('Local save was interrupted. Please try again.'));
    });
  }
  async function cacheSession(session) {
    const id = String(session.user.id);
    await store('put', 'private', { key: `session:${id}`, value: session });
    await store('put', 'private', { key: 'active_user', value: id });
  }
  async function cacheDashboard(data) {
    await store('put', 'private', { key: `dashboard:${state.session.user.id}`, value: data, savedAt: new Date().toISOString() });
    const userId = state.session.user.id;
    const photos = new Set([...arr(data.logs), ...arr(data.plan), ...arr(data.external_classes)].map(item => item.photo_id).filter(Boolean));
    for (const key of await store('keys', 'private')) {
      if (key.startsWith(`photo:${userId}:`) && !photos.has(key.split(':').at(-1))) await store('delete', 'private', key);
    }
  }
  async function rememberPhoto(photoId, photo, userId = state.session?.user.id) {
    if (!photoId || !photo || String(state.session?.user.id) !== String(userId)) return;
    const db = await openDB();
    await new Promise((resolve, reject) => {
      const tx = db.transaction('private', 'readwrite');
      const target = tx.objectStore('private');
      const active = target.get('active_user');
      active.onsuccess = () => {
        if (String(active.result?.value) === String(userId) && String(state.session?.user.id) === String(userId)) target.put({ key: `photo:${userId}:${photoId}`, value: photo });
      };
      tx.oncomplete = resolve;
      tx.onerror = () => reject(new Error('Photo could not be cached on this device.'));
      tx.onabort = () => reject(new Error('Photo caching was interrupted.'));
    });
  }
  async function loadPhoto(photoId) {
    if (!/^[a-f0-9]{32}$/.test(photoId || '')) throw new Error('Photo unavailable.');
    const userId = state.session.user.id;
    const cached = await store('get', 'private', `photo:${userId}:${photoId}`).catch(() => null);
    if (cached?.value) return cached.value;
    const response = await fetch(`/api/photos/${photoId}`, { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok || response.headers.get('X-Athlete-ID') !== String(userId) || response.headers.get('Content-Type') !== 'image/jpeg' || String(state.session?.user.id) !== String(userId)) throw new Error('Connect as the original athlete to view this photo.');
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.length > 200000) throw new Error('Photo is too large.');
    const photo = btoa(Array.from(bytes, byte => String.fromCharCode(byte)).join(''));
    await rememberPhoto(photoId, photo, userId).catch(() => {});
    return photo;
  }
  function sourceDimensions(bytes) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    if (bytes[0] === 255 && bytes[1] === 216) {
      let offset = 2;
      while (offset + 9 < bytes.length) {
        if (bytes[offset++] !== 255) break;
        while (bytes[offset] === 255) offset++;
        const marker = bytes[offset++];
        const size = view.getUint16(offset);
        if (size < 2 || offset + size > bytes.length) break;
        if ([192, 193, 194].includes(marker)) return [view.getUint16(offset + 5), view.getUint16(offset + 3)];
        offset += size;
      }
    } else if (bytes.length >= 24 && bytes.slice(0, 8).join(',') === '137,80,78,71,13,10,26,10') {
      return [view.getUint32(16), view.getUint32(20)];
    } else if (bytes.length >= 30 && String.fromCharCode(...bytes.slice(0, 4)) === 'RIFF' && String.fromCharCode(...bytes.slice(8, 12)) === 'WEBP') {
      const kind = String.fromCharCode(...bytes.slice(12, 16));
      if (kind === 'VP8X') return [1 + bytes[24] + (bytes[25] << 8) + (bytes[26] << 16), 1 + bytes[27] + (bytes[28] << 8) + (bytes[29] << 16)];
      if (kind === 'VP8 ') return [view.getUint16(26, true) & 16383, view.getUint16(28, true) & 16383];
      if (kind === 'VP8L' && bytes[20] === 47) return [1 + bytes[21] + ((bytes[22] & 63) << 8), 1 + (bytes[22] >> 6) + (bytes[23] << 2) + ((bytes[24] & 15) << 10)];
    }
    throw new Error('Choose a valid JPEG, PNG or WebP image.');
  }
  async function normalizePhoto(file) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 12000000) throw new Error('Choose a JPEG, PNG or WebP photo under 12 MB.');
    const [width, height] = sourceDimensions(new Uint8Array(await file.arrayBuffer()));
    if (!width || !height || width > 12000 || height > 12000 || width * height > 40000000) throw new Error('Photo is too large to process safely (40 megapixels maximum).');
    const url = URL.createObjectURL(file);
    const image = new Image();
    try {
      image.src = url;
      await image.decode();
      if (image.naturalWidth * image.naturalHeight > 40000000) throw new Error('Image dimensions exceed the limit.');
      const canvas = document.createElement('canvas');
      let scale = Math.min(1, 1600 / Math.max(image.naturalWidth, image.naturalHeight));
      for (let attempt = 0; attempt < 6; attempt++) {
        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
        const context = canvas.getContext('2d');
        context.fillStyle = '#fff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const photo = canvas.toDataURL('image/jpeg', .8).split(',')[1];
        if (photo.length <= 266668 && atob(photo).length <= 200000) return photo;
        scale *= .75;
      }
      throw new Error('Photo cannot be reduced below 200 KB. Try a crop.');
    } finally { URL.revokeObjectURL(url); }
  }
  function mountPhoto(form, saved = {}, target = 'instructions') {
    const box = document.createElement('section');
    box.className = 'photo-field full';
    box.innerHTML = `<h3>Board photo (optional)</h3><p class="small muted">One private photo. Choose a photo or use your camera. OCR runs only on this server, not in the cloud. Review handwriting, reps and loads carefully; nothing is applied or saved automatically.</p><label>Choose photo<input type="file" accept="image/jpeg,image/png,image/webp" data-photo-file></label><label>Take photo<input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" data-photo-file></label><img class="board-preview" alt="Your workout board" hidden><div class="form-actions"><button type="button" class="btn outline" data-photo-remove>Remove photo</button><button type="button" class="btn secondary" data-photo-ocr>Extract board text</button></div><div data-photo-review hidden>${textareaField('ocr_review', 'Review extracted text (not yet applied)')}<button type="button" class="btn outline" data-photo-apply>Apply reviewed text to ${target === 'main' ? 'class' : 'workout'} instructions</button></div><p class="small muted" data-photo-message role="status"></p>`;
    $('.form-grid', form).append(box);
    $('[name="ocr_review"]', box).maxLength = 8000;
    if (target === 'main') $('[name="main"]', form).maxLength = 8000;
    form.photoChange = saved.photo === null ? null : saved.photo || undefined;
    let current = saved.photo || null;
    let version = 0;
    const preview = photo => {
      const image = $('img', box);
      image.hidden = !photo;
      if (photo) image.src = `data:image/jpeg;base64,${photo}`;
      else image.removeAttribute('src');
    };
    preview(current);
    if (!current && saved.photo_id && saved.photo !== null) loadPhoto(saved.photo_id).then(photo => { if (form.isConnected && !version) { current = photo; preview(photo); } }).catch(() => { $('[data-photo-message]', box).textContent = 'Saved photo unavailable offline until viewed online. It will be preserved unless replaced or removed.'; });
    box.addEventListener('change', async event => {
      if (!event.target.matches('[data-photo-file]') || !event.target.files[0]) return;
      const ownVersion = ++version;
      form.photoBusy = true;
      try {
        const photo = await normalizePhoto(event.target.files[0]);
        if (ownVersion !== version || !form.isConnected) return;
        current = photo; form.photoChange = photo; preview(photo);
        $('[data-photo-review]', box).hidden = true;
        $('[data-photo-message]', box).textContent = 'Photo ready. Save the form to attach it.';
      } catch (error) { errorText(form, error); }
      finally { if (ownVersion === version) form.photoBusy = false; event.target.value = ''; }
    });
    box.addEventListener('click', async event => {
      const button = event.target.closest('button');
      if (!button) return;
      try {
        if (form.photoBusy) throw new Error('Wait for photo processing to finish.');
        if (button.hasAttribute('data-photo-remove')) {
          version++; current = null; form.photoChange = null; preview(null);
          $('[data-photo-review]', box).hidden = true;
          $('[data-photo-message]', box).textContent = 'Photo will be removed when you save.';
        } else if (button.hasAttribute('data-photo-ocr')) {
          if (!current) throw new Error('Choose a photo, or connect to load the saved photo first.');
          const ownVersion = version;
          button.disabled = true;
          const result = await api('/api/photos/ocr', 'POST', { photo: current });
          if (!form.isConnected || ownVersion !== version) return;
          $('[name="ocr_review"]', box).value = result.text;
          $('[data-photo-review]', box).hidden = false;
          $('[data-photo-message]', box).textContent = result.text ? 'Check the entire photo: OCR can omit or misread text and is limited to 8000 characters. Correct it, then explicitly apply it. Duration, RPE and status are unchanged.' : 'No text found. Enter instructions manually.';
        } else if (button.hasAttribute('data-photo-apply')) {
          const text = $('[name="ocr_review"]', box).value;
          if (text.length > 8000 || (target === 'main' && (text.split('\n').filter(line => line.trim()).length > 30 || text.split('\n').some(line => line.length > 1000)))) throw new Error('Shorten instructions to 8000 characters (class: 30 lines, 1000 characters per line).');
          $(`[name="${target}"]`, form).value = text;
          $('[data-photo-message]', box).textContent = 'Reviewed text applied. Save the form when ready.';
        }
      } catch (error) { errorText(form, error); }
      finally { button.disabled = false; }
    });
  }
  function photoPayload(form) {
    if (form.photoBusy) throw new Error('Wait for photo processing to finish before saving.');
    return form.photoChange === undefined ? {} : { photo: form.photoChange };
  }
  async function loadQueue() {
    try {
      state.queue = (await store('all', 'queue')).filter(item => String(item.user_id) === String(state.session?.user.id));
      const failure = await store('get', 'private', `sync_error:${state.session?.user.id}`);
      if (failure?.value && !state.syncError) state.syncError = failure.value;
    }
    catch { state.queue = []; }
  }
  async function api(path, method = 'GET', payload, token = state.session?.csrf_token) {
    if (method !== 'GET' && !navigator.onLine) throw new Error('You’re offline. This change needs a connection. Workout logs can still be saved on this device.');
    let response;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      response = await fetch(path, { method, signal: controller.signal, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json', ...(payload !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(method !== 'GET' && token ? { 'X-CSRF-Token': token } : {}) }, ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}) });
    } catch {
      const error = new Error('Cannot reach the server. Check your connection and try again.');
      error.network = true;
      throw error;
    } finally { clearTimeout(timeout); }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(typeof data.error === 'string' ? data.error : data.error?.message || data.message || `Request failed (${response.status}). Please try again.`);
      error.status = response.status;
      throw error;
    }
    return data;
  }
  const notify = message => { const node = $('#toast'); node.textContent = message; node.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('show'), 5000); };
  function errorText(form, error) {
    const element = $('.form-error', form);
    if (element) element.textContent = error.message || 'Something went wrong. Please try again.';
    else notify(error.message);
  }
  function uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, char => (Number(char) ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> Number(char) / 4).toString(16));
  }
  async function refresh() {
    const session = await api('/api/session');
    if (state.session && String(session.user.id) !== String(state.session.user.id)) throw new Error('The signed-in account changed. Reload to securely open that account.');
    state.session = session;
    state.offline = false;
    try { await cacheSession(session); } catch { notify('Offline storage unavailable. Keep this app online to use your plan.'); }
    const dashboard = await api('/api/dashboard');
    if (dashboard.user && String(dashboard.user.id) !== String(session.user.id)) throw new Error('Account changed while loading. Reload to securely open your training data.');
    state.dashboard = dashboard;
    try { await cacheDashboard(dashboard); } catch { /* Online data remains usable without device storage. */ }
    await loadQueue();
  }
  async function init() {
    if (resetToken()) { state.authMode = 'confirm'; renderAuth(); setupWorker(); return; }
    try {
      state.session = await api('/api/session');
      await refresh();
      render();
      if (state.queue.length) await syncQueue();
    } catch (error) {
      if (error.status === 401) {
        state.session = null;
        state.dashboard = null;
        renderAuth();
      } else {
        try {
          const active = await store('get', 'private', 'active_user');
          const cached = active && await store('get', 'private', `session:${active.value}`);
          const dashboard = active && await store('get', 'private', `dashboard:${active.value}`);
          if (!cached?.value?.user || !dashboard?.value || String(cached.value.user.id) !== String(active.value)) throw new Error('No complete offline plan is available on this device. Connect to sign in and download your plan.');
          state.session = cached.value;
          state.dashboard = dashboard.value;
          state.offline = true;
          state.cachedAt = dashboard.savedAt;
          await loadQueue();
          render();
        } catch {
          state.session = null;
          state.dashboard = null;
          renderAuth('Connect to sign in. No complete offline training plan is available on this device.');
        }
      }
    }
    setupWorker();
  }
  async function setupWorker() {
    if (!('serviceWorker' in navigator)) return;
    try {
      worker = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      navigator.serviceWorker.addEventListener('message', async event => {
        if (event.data?.type !== 'QUEUE_CHANGED' || !state.session || String(event.data.userId) !== String(state.session.user.id)) return;
        await loadQueue();
        if (event.data.error) state.syncError = event.data.error;
        else try { await refresh(); state.syncError = ''; } catch (error) { state.syncError = error.message; }
        render();
      });
    } catch { /* Manual sync and IndexedDB work without service workers. */ }
  }
  async function syncQueue() {
    if (syncPromise) return syncPromise;
    if (!state.session || !navigator.onLine) return;
    const userId = String(state.session.user.id);
    syncPromise = withPrivateLock(async () => {
      try {
        if (String(state.session?.user.id) !== userId) throw new Error('Account changed. Your queued workouts are retained for the original account.');
        const session = await api('/api/session');
        if (String(session.user.id) !== userId) throw new Error('Account changed. Your queued workouts are retained for the original account.');
        state.session = session;
        await cacheSession(session);
        await loadQueue();
        for (const item of state.queue.sort((a, b) => a.created_at.localeCompare(b.created_at))) {
          if (String(state.session?.user.id) !== userId) throw new Error('Account changed; remaining workouts are retained.');
          if (!await store('get', 'queue', item.client_id)) continue;
          const result = await api('/api/workouts/log', 'POST', item.payload, session.csrf_token);
          const confirmed = result.log || { ...item.payload, id: item.payload.session_id || `planned:${item.payload.date}` };
          if (!result.duplicate) await rememberPhoto(confirmed.photo_id, item.payload.photo, userId).catch(() => {});
          state.dashboard = { ...state.dashboard, logs: mergeLog(arr(state.dashboard.logs), confirmed) };
          await cacheDashboard(state.dashboard);
          await store('delete', 'queue', item.client_id);
        }
        state.syncError = '';
        await store('put', 'private', { key: `sync_error:${session.user.id}`, value: '' });
        await refresh();
      } catch (error) {
        state.syncError = error.status === 401 ? 'Session expired. Sign in again to sync. Your saved workouts are retained.' : error.message;
        try { if (String(state.session?.user.id) === userId) await store('put', 'private', { key: `sync_error:${userId}`, value: state.syncError }); } catch { /* Keep the failure visible even if storage is full. */ }
        if (error.network) state.offline = true;
      } finally {
        await loadQueue();
        if (state.session && state.dashboard) render();
      }
    });
    try { await syncPromise; } finally { syncPromise = null; }
  }
  async function queueWorkout(payload) {
    await store('put', 'queue', { client_id: payload.client_id, user_id: String(state.session.user.id), created_at: new Date().toISOString(), payload });
    await loadQueue();
    try { if (worker?.sync) await worker.sync.register('pair-workout-sync'); } catch { /* The online event and Sync button are the fallback. */ }
  }
  const workouts = () => arr(state.dashboard?.plan).slice().sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const logKey = log => log.kind === 'additional' ? `additional:${log.session_id}` : `planned:${log.date}`;
  const mergeLog = (saved, log) => [...saved.filter(item => logKey(item) !== logKey(log)), log].sort((a, b) => a.date.localeCompare(b.date) || String(a.session_time || '').localeCompare(String(b.session_time || '')));
  const exercised = log => ['completed', 'modified'].includes(log.status) && num(log.duration) > 0;
  const logs = () => {
    return state.queue.slice().sort((a, b) => a.created_at.localeCompare(b.created_at)).reduce((saved, item) => {
      const log = { ...item.payload, queued: true, id: item.payload.session_id || `planned:${item.payload.date}` };
      const previous = saved.find(record => logKey(record) === logKey(log));
      // Attachment and instructions are patches; other log fields remain replacements.
      if (!Object.hasOwn(log, 'instructions') && Object.hasOwn(previous || {}, 'instructions')) log.instructions = previous.instructions;
      if (!Object.hasOwn(log, 'photo')) {
        for (const key of ['photo', 'photo_id']) {
          if (!Object.hasOwn(log, key) && Object.hasOwn(previous || {}, key)) log[key] = previous[key];
        }
      } else {
        delete log.photo_id;
      }
      return mergeLog(saved, log);
    }, arr(state.dashboard?.logs));
  };
  const workoutLog = date => logs().find(log => log.kind !== 'additional' && log.date === date);
  const isCompleted = date => exercised(workoutLog(date) || {});
  const currentWorkout = () => workouts().find(workout => workout.date === today()) || workouts().find(workout => workout.date >= today()) || workouts().at(-1);
  const profile = () => state.dashboard?.profile || state.session?.profile || {};
  const race = () => state.dashboard?.race || state.session?.race || {};
  const person = () => profile().person || profile().name || 'Athlete';
  const team = () => state.dashboard?.team || state.session?.team || {};
  const safety = () => '<footer class="safety">Train for the long game. This app offers training guidance, not medical advice. Stop for new or worsening pain, dizziness, chest symptoms or unusual breathlessness; seek appropriate medical care. Fuelling guidance supports your established plan, not prescribed medication or insulin dosing. Discuss medical or glucose-management decisions with your care team.</footer>';
  const navItems = [['home', 'Home'], ['plan', 'Plan'], ['workout', 'Workout'], ['progress', 'Progress'], ['team', 'Team'], ['coach', 'Coach']];
  function route() {
    const [page, id] = location.hash.replace(/^#\/?/, '').split('/');
    let decoded;
    try { decoded = id ? decodeURIComponent(id) : null; } catch { decoded = null; }
    return { page: page || 'home', id: decoded };
  }
  function link(page, label, symbol = 'arrow', classes = 'text-button') { return `<a class="${classes}" href="#/${page}">${esc(label)} ${icon(symbol)}</a>`; }
  function heading(eyebrow, title, description, action = '') {
    return `<div class="page-heading"><div><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1>${description ? `<p class="subtitle">${esc(description)}</p>` : ''}</div><div class="form-actions">${action || `<span class="date-label">${esc(dateLabel(today(), { weekday: 'long', day: 'numeric', month: 'long' }))}</span>`}<button class="btn secondary" data-action="additional" data-date="${esc(state.selectedDate)}">Log additional workout</button></div></div>`;
  }
  function empty(title, description, symbol = 'progress') { return `<div class="empty">${icon(symbol)}<h3>${esc(title)}</h3><p>${esc(description)}</p></div>`; }
  function stat(label, value, foot, symbol) { return `<article class="card stat"><span class="stat-icon">${icon(symbol)}</span><div class="eyebrow">${esc(label)}</div><div class="stat-value">${esc(value)}</div><div class="stat-foot">${esc(foot)}</div></article>`; }
  function render() {
    if (!state.session || !state.dashboard) return renderAuth();
    const { page, id } = route();
    const active = ['stations', 'simulations'].includes(page) ? 'progress' : page;
    const screens = { home: renderHome, plan: renderPlan, workout: () => renderWorkout(id), progress: renderProgress, team: renderTeam, coach: renderCoach, settings: renderSettings, stations: renderStations, simulations: renderSimulations };
    const navigation = navItems.map(([key, label]) => `<a href="#/${key}" class="nav-link${active === key ? ' active' : ''}"${active === key ? ' aria-current="page"' : ''}>${icon(key)}${label}</a>`).join('');
    const queued = state.queue.length;
    const status = state.offline || !navigator.onLine ? 'Offline · saved plan' : state.syncError ? 'Sync needs attention' : queued ? `${queued} queued` : 'Up to date';
    $('#app').innerHTML = `<aside class="sidebar"><a class="brand" href="#/home" aria-label="PAIR home"><span class="brand-mark">P<span>↗</span></span>PAIR</a><p class="brand-sub">TRAIN. TOGETHER.</p><nav aria-label="Main navigation">${navigation}</nav><div class="sidebar-bottom"><div class="sidebar-note"><strong>Your race. Your rhythm.</strong>One shared goal. Two athletes. A smarter way to get there.</div><button class="profile-button" data-action="settings"><span class="avatar">${esc(person().slice(0, 1))}</span><span><b>${esc(person())}</b><small>Profile & settings</small></span>${icon('settings')}</button></div></aside><div class="workspace"><header class="topbar"><div class="breadcrumb"><span class="home-label">Your training space</span><span aria-hidden="true">/</span><b>${esc(titleCase(page))}</b></div><div class="top-actions"><span class="connection"><i class="dot${state.offline || queued || state.syncError || !navigator.onLine ? ' warn' : ''}"></i>${esc(status)}</span><button class="icon-button" data-action="theme" aria-label="Switch to ${state.theme === 'dark' ? 'light' : 'dark'} theme">${icon(state.theme === 'dark' ? 'sun' : 'moon')}</button><button class="icon-button" data-action="settings" aria-label="Profile and settings">${icon('settings')}</button></div></header>${state.offline || !navigator.onLine || queued || state.syncError ? `<div class="offline-banner" role="status"><span>${esc(state.syncError || (state.offline || !navigator.onLine ? `Offline mode. Showing your last downloaded plan${state.cachedAt ? ` from ${new Date(state.cachedAt).toLocaleDateString()}` : ''}.` : `${queued} workout${queued === 1 ? '' : 's'} saved on this device, waiting to sync.`))}</span><button data-action="${state.syncError.includes('Sign in') ? 'reauth' : 'sync'}">${state.syncError.includes('Sign in') ? 'Sign in' : 'Sync now'}</button></div>` : ''}<main id="main" class="content" tabindex="-1">${(screens[page] || renderHome)()}${safety()}</main></div><nav class="bottom-nav" aria-label="Mobile navigation">${navItems.map(([key, label]) => `<a href="#/${key}" class="${active === key ? 'active' : ''}"${active === key ? ' aria-current="page"' : ''}>${icon(key)}<span>${label}</span></a>`).join('')}</nav>`;
  }
  function renderAuth(message = '') {
    const mode = state.authMode;
    const token = resetToken();
    if (token) state.authMode = 'confirm';
    const actualMode = token ? 'confirm' : mode;
    const isSignup = actualMode === 'signup';
    const isReset = actualMode === 'reset';
    const isConfirm = actualMode === 'confirm';
    $('#app').innerHTML = `<main id="main" class="auth-layout"><section class="auth-story"><a href="/" class="brand"><span class="brand-mark">P<span>↗</span></span>PAIR</a><div><div class="eyebrow">YOUR HYROX DOUBLES JOURNEY</div><h1>Better training.<br><em>Together.</em></h1><p>A plan that works around your life. A partner by your side. Eight stations. One finish line.</p><div class="row section"><span class="tag dark">BUILT FOR KENZA + ROB</span><span class="tag dark">8 KM · 8 STATIONS</span></div></div><footer>Consistency beats perfection. Let’s build yours.</footer></section><section class="auth-form-side"><div class="auth-form-inner"><a href="/" class="brand auth-mobile-brand"><span class="brand-mark">P<span>↗</span></span>PAIR</a>${!isReset && !isConfirm ? `<div class="auth-tabs" aria-label="Account access"><button data-action="auth-login" class="${!isSignup ? 'active' : ''}">Sign in</button><button data-action="auth-signup" class="${isSignup ? 'active' : ''}">Create account</button></div>` : ''}<h2>${isConfirm ? 'Choose a new password.' : isReset ? 'Let’s get you back in.' : isSignup ? 'Your next chapter starts here.' : 'Welcome back.'}</h2><p class="subtitle">${isConfirm ? 'Use at least 10 characters for your new password.' : isReset ? 'Enter your email to request a password reset.' : isSignup ? 'Create your personal account, then connect with your partner.' : 'A little stronger. A little closer. Let’s get to work.'}</p>${message ? `<div class="notice warning">${esc(message)}</div>` : ''}<form id="auth-form" data-mode="${esc(actualMode)}">${!isConfirm ? field('email', 'Email address', 'email', '', { required: true, autocomplete: 'email', placeholder: 'you@example.com' }) : ''}${!isReset ? field('password', isConfirm ? 'New password' : 'Password', 'password', '', { required: true, minlength: isSignup || isConfirm ? 10 : 1, autocomplete: isSignup || isConfirm ? 'new-password' : 'current-password', placeholder: 'Your password' }) : ''}${isSignup ? `<div class="form-grid">${selectField('person', 'I am', ['Kenza', 'Rob'], 'Kenza')}${field('invite_code', 'Team invite code', 'text', '', { placeholder: 'Optional', maxlength: 40 })}</div><p class="small muted">Have a partner already on PAIR? Use their invite code to share race settings, simulations and station data.</p>` : ''}<button class="btn full" type="submit">${isConfirm ? 'Update password' : isReset ? 'Request password reset' : isSignup ? 'Create my training space' : 'Sign in'} ${icon('arrow')}</button><p class="form-error" role="alert"></p></form>${!isSignup && !isConfirm ? `<button class="text-button" data-action="${isReset ? 'auth-login' : 'auth-reset'}">${isReset ? 'Back to sign in' : 'Forgot your password?'}</button>` : ''}<p class="auth-fine">Your baseline and race projection are separate. Progress starts with real training data, not promises. Not affiliated with HYROX.</p></div></section></main>`;
    if (actualMode === 'login') $('.auth-form-inner h2').textContent = 'Welcome to HYROX Coach.';
  }
  function renderHome() {
    const workout = currentWorkout();
    const r = race();
    const countdown = r.date ? Math.max(0, Math.ceil((dateObj(r.date) - dateObj(today())) / 86400000)) : null;
    const weekPlan = workouts().filter(item => item.date >= today() && item.date < addDays(today(), 7));
    const weekLogs = logs().filter(log => log.date >= addDays(today(), -6) && log.date <= today() && exercised(log));
    const projection = state.dashboard.projection;
    const projected = num(projection?.seconds ?? projection?.projected_seconds ?? projection?.total_seconds);
    const readiness = { ...(state.dashboard.readiness || {}) };
    const recentSignals = arr(state.dashboard.logs).some(log => ['completed', 'modified'].includes(log.status) && log.date >= addDays(today(), -6) && log.date <= today() && ['sleep', 'soreness', 'fatigue', 'pain', 'energy'].some(key => num(log[key] ?? log.metrics?.[key]) !== null));
    const score = Object.keys(state.dashboard.checkin || {}).length || recentSignals ? num(readiness.score) : null;
    if (score !== null) {
      readiness.label ||= { green: 'Ready for the planned work', yellow: 'Keep the effort controlled', amber: 'Take a lighter approach', orange: 'Take a lighter approach', red: 'Rest & reassess today' }[readiness.color];
      readiness.message ||= arr(readiness.reasons).join(' ');
    }
    return `${heading('YOUR DAILY STARTING LINE', `Let’s move forward, ${person()}.`, 'Small steps. Shared ambition. Your doubles journey, one session at a time.')}<div class="grid cols-2"><article class="card hero"><div class="row between"><div class="eyebrow">YOUR NEXT SESSION</div><span class="tag dark">${workout ? esc(titleCase(workout.intensity || workout.type)) : 'YOUR PLAN'}</span></div><h2>${esc(workout?.title || 'Your training starts here.')}</h2><p>${esc(workout?.objective || 'Set your race date and goals to build a plan around you and your partner.')}</p><div class="hero-footer"><div class="row small">${icon('clock')} ${workout ? `${esc(workout.duration)} min <span aria-hidden="true">·</span> ${esc(dateLabel(workout.date, { weekday: 'short', day: 'numeric', month: 'short' }))}` : 'Ready when you are'}</div>${link(workout ? `workout/${encodeURIComponent(workout.id || workout.date)}` : 'settings', workout ? isCompleted(workout.date) ? 'Review session' : 'View workout' : 'Set up your race', 'arrow', 'btn lime')}</div></article><article class="card"><div class="card-header"><h2>How are you arriving today?</h2>${icon('heart')}</div><div class="readiness-score"><div class="readiness-ring"><b>${score === null ? '—' : esc(Math.round(score))}</b><span>${score === null ? 'NO CHECK-IN' : 'READINESS'}</span></div><div class="readiness-copy"><strong>${esc(readiness.label || readiness.status || 'Check in with yourself')}</strong><p>${esc(readiness.message || readiness.summary || 'Sleep, soreness and fatigue help shape today’s training.')}</p></div></div><button class="btn secondary full" data-action="readiness">${state.dashboard.checkin ? 'Update daily check-in' : 'Complete daily check-in'} ${icon('arrow')}</button></article></div><div class="grid cols-4 stats">${stat('Race countdown', countdown === null ? '—' : `${countdown} days`, r.name || 'Set your race date', 'flag')}${stat('Your target', num(r.target_seconds) === null ? '—' : time(r.target_seconds), 'A goal, not a prediction', 'clock')}${stat('Current projection', projected === null ? '—' : time(projected), projected === null ? 'Needs measured training data' : 'Estimate · not a guaranteed result', 'progress')}${stat('Sessions this week', weekLogs.length, 'Completed in the last 7 days', 'check')}</div><div class="grid cols-2"><section class="card"><div class="card-header"><h2>Your next seven days</h2>${link('plan', 'Full plan')}</div>${weekPlan.length ? weekPlan.slice(0, 5).map(workoutRow).join('') : empty('Your schedule is taking shape', 'Set your race and plan start dates in settings.', 'plan')}</section><section class="card"><div class="card-header"><h2>The bigger picture</h2><span class="tag">DOUBLES</span></div><p class="small muted">You both run all eight 1 km legs together. You can share station work; you cannot divide the running.</p><div class="divider"></div><div class="metric-row"><span>Starting baseline</span><b>${esc(num(r.baseline_seconds) === null ? 'Not recorded' : time(r.baseline_seconds))}</b></div><p class="small muted">Your starting reference stays separate from the current projection. Measured simulations make the estimate more useful.</p><div class="divider"></div>${link('team', 'Build your race partnership', 'team')}${link('simulations', 'Log a simulation', 'arrow')}</section></div>${renderAdjustments()}`;
  }
  function workoutRow(workout) {
    const log = workoutLog(workout.date);
    return `<div class="workout-row"><div class="workout-date"><span>${esc(dateLabel(workout.date, { weekday: 'short' }))}</span><strong>${esc(dateLabel(workout.date, { day: 'numeric' }))}</strong></div><div class="workout-info"><h3><a href="#/workout/${encodeURIComponent(workout.id || workout.date)}">${esc(workout.title)}</a></h3><p>${esc(workout.duration)} min · ${esc(titleCase(workout.type))}${log?.queued ? ' · queued offline' : log ? ` · ${esc(titleCase(log.status))}` : ''}</p></div><span class="status-circle${isCompleted(workout.date) ? ' done' : ''}" aria-label="${isCompleted(workout.date) ? 'Completed' : 'Planned'}">${isCompleted(workout.date) ? '✓' : '·'}</span></div>`;
  }
  function renderAdjustments() {
    const adjustments = arr(state.dashboard.adjustments);
    return adjustments.length ? `<section class="section card"><div class="card-header"><h2>A plan that adapts to you</h2>${icon('coach')}</div><div class="stack">${adjustments.map(item => `<div><h3>${esc(typeof item === 'string' ? item : item.what || item.title || 'Training adjustment')}</h3><p class="small muted">${esc(typeof item === 'object' ? item.why || item.reason || words(item) : '')}</p>${item.effect ? `<p class="small">${esc(item.effect)}</p>` : ''}</div>`).join('')}</div></section>` : '';
  }
  function renderPlan() {
    const start = state.week;
    const end = addDays(start, 6);
    const all = workouts();
    const planned = all.filter(item => item.date >= start && item.date <= end && (state.filter === 'all' || String(item.type).toLowerCase().includes(state.filter)));
    return `${heading('THE WORK THAT GETS YOU THERE', 'Your training plan.', 'Structured, flexible, and built around real life.', '<button class="btn outline" data-action="external">Add / edit class</button>')}<div class="section-title"><h2>${esc(dateLabel(start))} — ${esc(dateLabel(end))}</h2><div class="date-controls"><button class="icon-button" data-action="week-prev" aria-label="Previous seven days">${icon('back')}</button><button class="icon-button" data-action="week-next" aria-label="Next seven days">${icon('arrow')}</button></div></div><div class="week-strip">${Array.from({ length: 7 }, (_, index) => {
      const day = addDays(start, index);
      return `<button class="day${day === state.selectedDate ? ' active' : ''}" data-action="day" data-date="${esc(day)}" aria-label="Show ${esc(dateLabel(day, { weekday: 'long', day: 'numeric', month: 'long' }))}" aria-pressed="${day === state.selectedDate}"><span>${esc(dateLabel(day, { weekday: 'short' }))}</span><b>${esc(dateLabel(day, { day: 'numeric' }))}</b>${all.some(item => item.date === day) ? '<i aria-hidden="true"></i>' : '<span aria-hidden="true">·</span>'}</button>`;
    }).join('')}</div><div class="filters" aria-label="Filter workout type">${[['all', 'All sessions'], ['run', 'Running'], ['strength', 'Strength'], ['hyrox', 'HYROX'], ['recovery', 'Recovery']].map(([value, label]) => `<button class="chip${state.filter === value ? ' active' : ''}" data-action="filter" data-filter="${value}" aria-pressed="${state.filter === value}">${label}</button>`).join('')}</div><div class="stack">${planned.length ? planned.map(workout => `<article class="card workout-card" id="day-${esc(workout.date)}"><div class="workout-date"><span>${esc(dateLabel(workout.date, { weekday: 'short' }))}</span><strong>${esc(dateLabel(workout.date, { day: 'numeric' }))}</strong></div><div><span class="tag${String(workout.intensity).toLowerCase().includes('high') ? ' orange' : ''}">${esc(titleCase(workout.type))}</span>${isCompleted(workout.date) ? ' <span class="tag">✓ COMPLETED</span>' : ''}<h3>${esc(workout.title)}</h3><p class="small muted">${esc(workout.objective || '')}</p><div class="workout-metadata"><span>${icon('clock')} ${esc(workout.duration)} min</span><span>${esc(titleCase(workout.intensity || 'Planned effort'))}</span>${workoutLog(workout.date)?.queued ? '<span>Saved on device · queued</span>' : ''}</div></div>${link(`workout/${encodeURIComponent(workout.id || workout.date)}`, 'Details', 'arrow', 'btn secondary')}</article>`).join('') : `<article class="card">${empty('No sessions in this view', 'Try a different filter or week. Your full downloaded plan is available offline.', 'plan')}</article>`}</div>${renderAdjustments()}`;
  }
  function findWorkout(id) { return id ? workouts().find(workout => String(workout.id) === id || workout.date === id) : currentWorkout(); }
  function renderWorkout(id) {
    const workout = findWorkout(id);
    return renderPlannedWorkout(id) + (workout ? photoRecord(workout) + photoRecord(workoutLog(workout.date) || {}) + `<div class="form-actions section"><button class="btn secondary" data-action="additional" data-date="${esc(workout.date)}">Log additional workout</button>${link('progress', 'View all session logs')}</div><p class="small muted">Keep the planned workout separate. Extra sessions count toward your training load.</p>` : '');
  }
  function photoRecord(record) {
    const photo = record.photo_id && record.photo !== null ? `<button type="button" class="text-button" data-action="view-photo" data-photo="${esc(record.photo_id)}">View private board photo</button>` : record.photo ? '<p class="small muted">Board photo saved locally; open the workout log to view it.</p>' : '';
    return record.instructions || photo ? `<section class="photo-record section"><h3>Reviewed board / workout instructions</h3>${record.instructions ? `<p class="board-text">${esc(record.instructions)}</p>` : ''}${photo}</section>` : '';
  }
  function renderPlannedWorkout(id) {
    const workout = findWorkout(id);
    if (!workout) return `${heading('YOUR TRAINING', 'No session selected.', 'Choose a workout from your plan.')}<div class="card">${empty('Your plan is ready for a date', 'Configure your race and plan start in settings to get going.', 'workout')}${link('plan', 'Open your plan', 'arrow', 'btn full')}</div>`;
    const log = workoutLog(workout.date);
    return `${link('plan', 'Back to plan', 'back')}<article class="card detail-hero section"><div class="row between"><span class="tag dark">${esc(titleCase(workout.type))}</span><span class="small muted">${esc(dateLabel(workout.date, { weekday: 'long', day: 'numeric', month: 'long' }))}</span></div><h1>${esc(workout.title)}</h1><p class="muted">${esc(workout.objective)}</p><div class="workout-metadata muted"><span>${icon('clock')} ${esc(workout.duration)} minutes</span><span>${esc(titleCase(workout.intensity))}</span>${log ? `<span>${esc(titleCase(log.status))}${log.queued ? ' · queued on device' : ''}</span>` : ''}</div></article>${workout.adjustment ? `<div class="notice warning section"><strong>${esc(workout.adjustment.what)}</strong><br>${esc(workout.adjustment.why)}${workout.adjustment.effect ? `<br>Expected effect: ${esc(workout.adjustment.effect)}` : ''}</div>` : ''}<div class="grid cols-2 section"><div class="stack"><section class="card"><div class="card-header"><h2>01 / Warm up</h2><span class="label-icon">${icon('sun')}</span></div><p class="instruction">${esc(words(workout.warmup) || 'Follow the warm-up agreed with your coach; begin gently and build gradually.')}</p></section><section class="card"><div class="card-header"><h2>02 / The main work</h2><span class="label-icon">${icon('workout')}</span></div>${arr(workout.main).length ? `<ol class="steps">${workout.main.map(item => `<li>${esc(words(item))}</li>`).join('')}</ol>` : `<p class="instruction">${esc(words(workout.main) || 'No detailed instructions available for this session.')}</p>`}</section><section class="card"><div class="card-header"><h2>03 / Cool down</h2><span class="label-icon">${icon('leaf')}</span></div><p class="instruction">${esc(words(workout.cooldown) || 'Ease down gently. Note how your body responds.')}</p></section></div><aside class="stack"><section class="card"><div class="card-header"><h2>Why this session matters</h2>${icon('coach')}</div><p class="small muted">${esc(workout.why || 'This session supports the wider training plan. Keep effort aligned with today’s readiness.')}</p><div class="divider"></div><button class="btn full" data-action="log" data-id="${esc(workout.id || workout.date)}">${log ? 'Update workout log' : 'Log this workout'} ${icon('check')}</button><button class="text-button" data-action="external" data-date="${esc(workout.date)}">Replace with an external class ${icon('arrow')}</button><p class="micro muted">Logs save to this device first. They sync securely when connected.</p></section>${log ? `<section class="card"><div class="card-header"><h2>Your session record</h2><span class="tag">${esc(titleCase(log.status))}</span></div><p class="small muted">${esc(log.duration ?? '—')} min · RPE ${esc(log.rpe ?? '—')}/10</p>${Object.keys(log.metrics || {}).length ? `<div class="metric-values">${Object.entries(log.metrics).map(([key, value]) => `<span>${esc(titleCase(key))}: <b>${esc(words(value))}</b></span>`).join('')}</div>` : '<p class="small muted">No measured metrics logged.</p>'}${log.notes ? `<div class="divider"></div><p class="small">${esc(log.notes)}</p>` : ''}${log.queued ? '<p class="small muted section">Saved locally · waiting for server confirmation.</p>' : ''}</section>` : ''}</aside></div><section class="card section"><div class="card-header"><h2>Fuel the work, support the recovery.</h2><span class="tag">YOUR ESTABLISHED PLAN</span></div><div class="fuelling-grid">${['before', 'during', 'after'].map((key, index) => `<div><span class="label-icon">${icon(['sun', 'heart', 'leaf'][index])}</span><h3>${titleCase(key)}</h3><p>${esc(workout.fuelling?.[key] || 'Follow your established fuelling plan and individual tolerances.')}</p></div>`).join('')}</div><p class="micro muted section">No medication dosing advice. Glucose or medical decisions belong with your care team.</p></section>`;
  }
  function chart(values, label, unit = 'min') {
    const clean = values.filter(item => num(item.value) !== null);
    if (!clean.length) return empty('No measured data yet', 'Your real session logs and simulations will appear here. No synthetic splits.', 'progress');
    const width = 540, height = 180, left = 36, bottom = 150, top = 18;
    const numbers = clean.map(item => Number(item.value));
    const min = Math.min(...numbers) * .9;
    const max = Math.max(...numbers) * 1.1 || 1;
    const point = (value, index) => [left + index * (width - left - 16) / Math.max(1, clean.length - 1), bottom - (value - min) / (max - min || 1) * (bottom - top)];
    const points = clean.map((item, index) => point(Number(item.value), index));
    return `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title><desc>${esc(clean.map(item => `${item.label}: ${Number(item.value).toFixed(1)} ${unit}`).join('; '))}</desc>${[0, 1, 2].map(index => `<line class="chart-grid" x1="${left}" y1="${top + index * 66}" x2="524" y2="${top + index * 66}"/><text class="chart-label" x="0" y="${top + index * 66 + 4}">${(max - index * (max - min) / 2).toFixed(0)}</text>`).join('')}<polyline class="chart-line" points="${points.map(point => point.join(',')).join(' ')}"/>${points.map(([x, y], index) => `<circle cx="${x}" cy="${y}" r="4" fill="#719157"/><text class="chart-label" x="${x}" y="176" text-anchor="${index === 0 ? 'start' : index === points.length - 1 ? 'end' : 'middle'}">${esc(clean[index].label)}</text>`).join('')}</svg>`;
  }
  function renderProgress() {
    const completed = logs().filter(exercised);
    const simulations = arr(state.dashboard.simulations);
    const minutes = completed.reduce((sum, log) => sum + (num(log.duration) || 0), 0);
    const rpe = completed.filter(log => num(log.rpe) !== null);
    const last = simulations.at(-1);
    const analysis = state.dashboard.analysis || {};
    return `${heading('PROGRESS, NOT PERFECTION', 'See the work adding up.', 'Real data. Useful patterns. A clearer path to your finish line.', '<button class="btn outline" data-action="simulation">Log simulation</button>')}<div class="grid cols-4 stats">${stat('Sessions completed', completed.length, 'Includes locally queued logs', 'check')}${stat('Training time', `${Math.round(minutes)} min`, 'Total logged duration', 'clock')}${stat('Average effort', rpe.length ? `${(rpe.reduce((sum, log) => sum + Number(log.rpe), 0) / rpe.length).toFixed(1)}/10` : '—', 'Only recorded RPE values', 'heart')}${stat('Latest simulation', last ? time(last.total_seconds) : '—', last ? dateLabel(last.date) : 'No simulation measured yet', 'flag')}</div><div class="grid equal-2"><section class="card"><div class="card-header"><h2>Session duration</h2><span class="small muted">Minutes</span></div>${chart(completed.slice(-8).map(log => ({ value: num(log.duration), label: dateLabel(log.date) })), 'Duration of your latest completed sessions')}</section><section class="card"><div class="card-header"><h2>Simulation trend</h2><span class="small muted">Minutes</span></div>${chart(simulations.slice(-6).map(simulation => ({ value: num(simulation.total_seconds) === null ? null : simulation.total_seconds / 60, label: dateLabel(simulation.date) })), 'Measured total times from race simulations')}</section></div><div class="grid equal-2 section"><article class="card"><div class="card-header"><h2>Every station, understood.</h2>${icon('workout')}</div><p class="small muted">Compare measured times, fatigue and transitions. Discover how to share the work effectively.</p>${link('stations', 'Station profiles & measurements', 'arrow', 'btn secondary section')}</article><article class="card"><div class="card-header"><h2>Rehearse your race.</h2>${icon('flag')}</div><p class="small muted">Log actual splits, test a scenario and keep a race strategy based on evidence.</p>${link('simulations', 'Simulations & race scenarios', 'arrow', 'btn secondary section')}</article></div>${Object.keys(analysis).length ? `<section class="card section"><div class="card-header"><h2>What your data is telling us</h2>${icon('coach')}</div>${renderInsights(analysis)}</section>` : ''}<section class="card section"><div class="card-header"><h2>Session history</h2><span class="small muted">${logs().length} records</span></div>${logs().length ? `<div class="stack">${logs().slice().reverse().slice(0, 30).map(historyRow).join('')}</div>` : empty('Your story is still being written', 'Complete a session and log what you actually did.', 'workout')}</section>`;
  }
  function historyRow(log) {
    const additional = log.kind === 'additional';
    const title = additional ? log.title : workouts().find(workout => workout.date === log.date)?.title || 'Planned workout';
    return `<article class="history-card"><div class="row between"><h3>${esc(title)}</h3><span class="tag${log.status === 'skipped' ? ' orange' : ''}">${esc(titleCase(log.status))}${log.queued ? ' · QUEUED' : ''}</span></div><p class="small muted">${esc(dateLabel(log.date, { weekday: 'short', day: 'numeric', month: 'short' }))}${log.session_time ? ` · ${esc(log.session_time)}` : ''} · ${additional ? `Additional · ${esc(titleCase(log.type))}` : 'Planned'}</p><div class="metric-values"><span>${esc(log.duration ?? '—')} minutes</span><span>RPE ${esc(log.rpe ?? '—')}/10</span>${Object.entries(log.metrics || {}).map(([key, value]) => `<span>${esc(titleCase(key))}: ${esc(words(value))}</span>`).join('')}</div>${log.notes ? `<p class="small muted section">${esc(log.notes)}</p>` : ''}${photoRecord(log)}${additional ? `<button class="text-button" data-action="additional" data-session="${esc(log.session_id)}">Edit additional workout</button>` : `<button class="text-button" data-action="log" data-id="${esc(log.date)}">Edit workout log</button>`}</article>`;
  }
  function renderInsights(value) {
    if (typeof value === 'string') return `<p class="instruction">${esc(value)}</p>`;
    if (Array.isArray(value)) return `<ul class="list">${value.map(item => `<li>${esc(words(item))}</li>`).join('')}</ul>`;
    return `<div class="stack">${Object.entries(value || {}).map(([key, item]) => `<div><h3>${esc(titleCase(key))}</h3><p class="small muted">${esc(words(item))}</p></div>`).join('')}</div>`;
  }
  function renderTeam() {
    const t = team();
    const members = arr(t.members);
    const strategy = state.dashboard.strategy;
    return `${heading('ONE FINISH LINE. TWO ATHLETES.', 'Your strongest partnership.', 'Share the work. Keep the rhythm. Get to the finish line together.')}<div class="grid cols-2"><section class="card"><div class="card-header"><h2>${esc(t.name || 'Kenza + Rob')}</h2><button class="text-button" data-action="team-name">Edit name</button></div>${members.length ? members.map((member, index) => `<div class="team-member"><span class="avatar${index ? ' alt' : ''}">${esc(String(member.person || member.name || 'A').slice(0, 1))}</span><div><h3>${esc(member.person || member.name || 'Athlete')}</h3><p class="small muted">${esc(member.email || 'Team member')}</p></div>${String(member.id) === String(state.session.user.id) ? '<span class="tag push-right">YOU</span>' : ''}</div>`).join('') : `<div class="team-member"><span class="avatar">${esc(person().slice(0, 1))}</span><div><h3>${esc(person())}</h3><p class="small muted">Signed-in athlete</p></div><span class="tag push-right">YOU</span></div><p class="small muted section">Invite your partner to connect their own account. Station measurements can cover both athletes even before they join.</p>`}<div class="notice section"><strong>Both athletes run the full 8 km.</strong><br>Each 1 km leg is completed together. Split station work to suit your strengths, and practise handovers.</div></section><section class="card"><div class="card-header"><h2>Bring your partner in</h2>${icon('team')}</div><p class="small muted">Your partner creates their own account and enters this invite code. Shared team data stays connected; personal logs stay with each athlete.</p>${t.invite_code ? `<div class="invite-code">${esc(t.invite_code)}</div><button class="btn secondary full" data-action="copy-invite">${icon('copy')} Copy invite code</button>` : '<div class="notice section">No invite code is available yet. Connect to refresh your team details.</div>'}</section></div><section class="card section"><div class="card-header"><h2>Make the handover your advantage.</h2><span class="tag">RACE STRATEGY</span></div>${Array.isArray(strategy) ? strategy.map(item => `<div class="station-row"><span class="pill-number">${icon('workout')}</span><div><h3>${esc(item.name || titleCase(item.station))}</h3><p>${esc(item.rationale)}</p></div><div class="station-share"><b>${item.kenza_share == null ? 'Unmeasured' : `${Math.round(item.kenza_share * 100)}% / ${100 - Math.round(item.kenza_share * 100)}%`}</b>${item.kenza_share == null ? 'No allocation guessed' : 'Kenza / Rob · estimate'}<br>${item.seconds == null ? '' : esc(time(item.seconds))}</div></div>`).join('') : strategy ? renderInsights(strategy) : '<p class="small muted">Record station times and fatigue for both athletes to build an evidence-based allocation. Don’t assume a 50/50 split is fastest.</p>'}<div class="form-actions">${link('stations', 'Measure your stations', 'workout', 'btn secondary')}${link('simulations', 'Practise your race', 'flag', 'btn outline')}</div></section>`;
  }
  function stations() {
    const data = state.dashboard.stations;
    if (Array.isArray(data)) return data.map((item, index) => typeof item === 'string' ? { id: item, name: titleCase(item), index } : { ...item, id: item.id || item.key || item.station || String(index), name: item.name || item.title || titleCase(item.id || item.key || item.station), index });
    return Object.entries(data || {}).map(([key, value], index) => ({ ...(typeof value === 'object' ? value : {}), id: key, name: typeof value === 'string' ? value : value.name || titleCase(key), index }));
  }
  function renderStations() {
    const measurements = state.dashboard.measurements || {};
    return `${link('progress', 'Back to progress', 'back')}${heading('EIGHT STATIONS. FIND YOUR EDGE.', 'The work between the runs.', 'Measured station profiles help you divide work, not guess.', '<button class="btn outline" data-action="station-settings">Edit race standards</button>')}<div class="notice">Confirm station loads and distances against your event division’s official rules. Training recommendations never override event standards. Missing values mean <strong>not measured</strong>, not zero.</div><div class="grid equal-2">${stations().map(station => {
      const measured = measurements[station.id] || {};
      return `<article class="card"><div class="card-header"><div class="row"><span class="pill-number">${String(station.index + 1).padStart(2, '0')}</span><h2>${esc(station.name)}</h2></div><button class="text-button" data-action="measure" data-station="${esc(station.id)}">Record data</button></div><p class="small muted">${esc(station.description || station.instructions || station.instruction || station.objective || 'Record full-station benchmarks in comparable conditions.')}</p><div class="metric-values">${station.distance != null ? `<span>Distance / reps: <b>${esc(station.distance)} ${esc(station.unit || '')}</b></span>` : ''}${station.load != null ? `<span>Load: <b>${esc(station.load)} ${esc(station.load_unit || 'kg')}</b></span>` : ''}${station.exercises ? `<span>Exercises: ${esc(words(station.exercises))}</span>` : ''}</div>${station.reference || station.notes ? `<p class="micro muted section">${esc(station.reference || '')} ${esc(station.notes || '')}</p>` : ''}<div class="divider"></div><div class="grid equal-2"><div><div class="eyebrow">KENZA</div><h3>${esc(time(measured.kenza_seconds))}</h3><p class="small muted">Fatigue: ${esc(measured.kenza_fatigue ?? 'Not recorded')}${measured.kenza_fatigue != null ? '/10' : ''}</p></div><div><div class="eyebrow">ROB</div><h3>${esc(time(measured.rob_seconds))}</h3><p class="small muted">Fatigue: ${esc(measured.rob_fatigue ?? 'Not recorded')}${measured.rob_fatigue != null ? '/10' : ''}</p></div></div><div class="metric-row"><span>Transition time</span><b>${esc(time(measured.transition_seconds))}</b></div><div class="metric-row"><span>Preferred Kenza share</span><b>${esc(measured.preferred_share != null ? `${Math.round(measured.preferred_share * 100)}%` : 'Not set')}</b></div></article>`;
    }).join('') || `<section class="card">${empty('No station profiles available', 'Connect to download your team’s station configuration.', 'workout')}</section>`}</div>`;
  }
  function renderSimulations() {
    const simulations = arr(state.dashboard.simulations);
    return `${link('progress', 'Back to progress', 'back')}${heading('REHEARSE. REFINE. REPEAT.', 'Race day, before race day.', 'Keep measured simulations separate from hypothetical scenarios.', '<button class="btn outline" data-action="simulation">Log simulation</button>')}<div class="grid equal-2"><section class="card"><div class="card-header"><h2>Your race references</h2>${icon('flag')}</div><div class="metric-row"><span>Starting baseline</span><b>${esc(time(race().baseline_seconds))}</b></div><div class="metric-row"><span>Target</span><b>${esc(time(race().target_seconds))}</b></div><p class="small muted section">A scenario is an arithmetic estimate, not a prediction. Measured simulations capture real fatigue, handovers and pacing.</p></section><section class="card"><div class="card-header"><h2>What if?</h2>${icon('coach')}</div><p class="small muted">Test your shared running pace, all eight station times and transitions. Both athletes still run every 1 km leg.</p><button class="btn secondary section" data-action="scenario">Build a race scenario ${icon('arrow')}</button></section></div><section class="card section"><div class="card-header"><h2>Measured simulations</h2><span class="small muted">${simulations.length} recorded</span></div>${simulations.length ? `<div class="stack">${simulations.slice().reverse().map(simulation => `<article class="history-card"><div class="row between"><div><div class="eyebrow">${esc(dateLabel(simulation.date, { day: 'numeric', month: 'long', year: 'numeric' }))}</div><h3>${esc(time(simulation.total_seconds))} total</h3></div><span class="tag">RPE ${esc(simulation.rpe ?? '—')}/10</span></div><div class="divider"></div><p class="small"><strong>Run splits:</strong> ${arr(simulation.runs).length ? arr(simulation.runs).map((split, index) => `${index + 1}: ${esc(time(split))}`).join(' · ') : '<span class="muted">No measured run splits</span>'}</p><p class="small section"><strong>Stations:</strong> ${Object.entries(simulation.stations || {}).length ? Object.entries(simulation.stations).map(([key, value]) => `${esc(titleCase(key))}: ${esc(time(value))}`).join(' · ') : '<span class="muted">No measured station splits</span>'}</p><p class="small section"><strong>Transitions:</strong> ${arr(simulation.transitions).length ? simulation.transitions.map(value => esc(time(value))).join(' · ') : '<span class="muted">No measured transitions</span>'}</p>${['notes', 'pacing_notes', 'fuelling_notes', 'difficulty'].filter(key => simulation[key]).map(key => `<p class="small muted section"><strong>${esc(titleCase(key))}:</strong> ${esc(simulation[key])}</p>`).join('')}${Object.keys(simulation.allocations || {}).length ? `<p class="small muted section"><strong>Kenza’s station shares:</strong> ${Object.entries(simulation.allocations).map(([key, value]) => `${esc(titleCase(key))} ${esc(value)}%`).join(' · ')}</p>` : ''}</article>`).join('')}</div>` : empty('Your first rehearsal awaits', 'Log the total time, and only the splits you actually measured. Incomplete split data is welcome.', 'flag')}</section>`;
  }
  function renderCoach() {
    return `${heading('CLARITY FOR THE NEXT STEP', 'A little guidance goes a long way.', 'Ask about your training, race pacing or how to adapt today’s session.')}<section class="card coach-welcome"><div class="row gap-bottom">${icon('coach')}<span class="tag dark">YOUR TRAINING COMPANION</span></div><h2>Let’s make the next session count.</h2><p>Guidance grounded in your plan and recorded data. No miracle predictions. No medical dosing advice. Just a practical next step.</p></section><div class="coach-prompts">${['What should I focus on this week?', 'How should we split the stations?', 'How do I adapt when I feel tired?'].map(question => `<button class="prompt" data-action="prompt" data-question="${esc(question)}">${icon('coach')}${esc(question)}</button>`).join('')}</div>${state.offline || !navigator.onLine ? '<div class="notice warning">Coach is unavailable offline. Your downloaded workout instructions and fuelling notes are still available. Connect to get a response; no server answer will be invented.</div>' : ''}<div class="chat" role="log" aria-label="Conversation with your training coach">${state.chat.map(message => `<article class="message ${message.role === 'user' ? 'user' : ''}"><div class="message-label">${message.role === 'user' ? esc(person()) : 'PAIR COACH'}</div>${esc(message.text)}</article>`).join('')}</div><form id="coach-form"><div class="coach-input">${textareaField('question', 'Your question', '', 'Ask a specific training question…', true)}<button class="btn" type="submit" aria-label="Send question">${icon('send')}</button></div><p class="form-error" role="alert"></p></form>`;
  }
  function renderSettings() {
    const p = profile(), r = race();
    return `${heading('MAKE IT YOURS', 'Your profile & race.', 'Personal training preferences. Shared race ambitions.')}
      <div class="grid equal-2"><section class="card"><div class="card-header"><h2>Athlete profile</h2><span class="tag">${esc(p.person || person())}</span></div>
      <form id="profile-form"><div class="form-grid">
      ${textareaField('goals', 'Personal goals', words(p.goals))}
      ${field('benchmark', 'Measured 10 km benchmark', 'text', num(p.benchmark_seconds) === null ? '' : time(p.benchmark_seconds), { placeholder: '49:15', hint: 'M:SS or H:MM:SS; optional' })}
      ${field('easy_pace', 'Easy-effort guidance', 'text', p.easy_pace || '', { maxlength: 1000 })}
      ${textareaField('fuelling_preferences', 'Fuelling preferences & established plan', words(p.fuelling_preferences), 'Foods you tolerate, your established plan, and relevant considerations.')}
      ${textareaField('notes', 'Athlete notes', p.notes || '', 'Relevant training preferences and limitations.')}
      </div><div class="form-actions"><button class="btn" type="submit">Save profile</button></div><p class="form-error" role="alert"></p></form></section>
      <section class="card"><div class="card-header"><h2>Your shared race</h2>${icon('flag')}</div><form id="race-form"><div class="form-grid">
      ${field('name', 'Race name', 'text', r.name, { maxlength: 100, required: true })}
      ${field('date', 'Race date', 'date', r.date, { required: true })}
      ${field('target', 'Target finish time', 'text', num(r.target_seconds) === null ? '' : time(r.target_seconds), { required: true, placeholder: '1:20:00', hint: 'H:MM:SS or M:SS' })}
      ${field('plan_start', 'Plan start date', 'date', r.plan_start, { required: true })}
      ${field('simulation_date', 'Simulation date', 'date', r.simulation_date, { required: true })}
      </div><div class="form-actions"><button class="btn" type="submit">Save race & refresh plan</button></div><p class="form-error" role="alert"></p></form>
      <div class="divider"></div><div class="metric-row"><span>Starting baseline</span><b>${esc(time(r.baseline_seconds))}</b></div><p class="micro muted">Your starting reference is separate from the live projection. Race settings are shared; changing dates refreshes the training plan.</p></section></div>
      <section class="card section"><div class="card-header"><h2>Your device & account</h2>${icon('settings')}</div><p class="small muted">Signed in as ${esc(state.session.user.email)}. Workout details, plan history and your queue are stored privately on this device for this account. Signing out clears all locally stored private data.</p><div class="form-actions"><button class="btn secondary" data-action="sync">${icon('sync')} Sync saved workouts${state.queue.length ? ` (${state.queue.length})` : ''}</button><button class="btn outline" data-action="theme">${icon('sun')} ${state.theme === 'dark' ? 'Light' : 'Dark'} appearance</button><button class="btn danger" data-action="logout">Sign out & clear device</button></div><p class="small muted section">Offline switching is disabled. Connect before signing out or signing into another account. Your queue is never discarded because of a sync or authentication error.</p></section>`;
  }
  function field(name, label, type = 'text', value = '', options = {}) {
    const attributes = Object.entries(options).filter(([key]) => key !== 'hint').map(([key, value]) => value === true ? esc(key) : `${esc(key)}="${esc(value)}"`).join(' ');
    return `<div class="field"><label for="f-${esc(name)}">${esc(label)}</label><input id="f-${esc(name)}" name="${esc(name)}" type="${esc(type)}" value="${esc(value)}" ${attributes}>${options.hint ? `<small>${esc(options.hint)}</small>` : ''}</div>`;
  }
  function selectField(name, label, options, value) {
    return `<div class="field"><label for="f-${esc(name)}">${esc(label)}</label><select name="${esc(name)}" id="f-${esc(name)}">${options.map(option => {
      const [key, text] = Array.isArray(option) ? option : [option, titleCase(option)];
      return `<option value="${esc(key)}"${String(value) === String(key) ? ' selected' : ''}>${esc(text)}</option>`;
    }).join('')}</select></div>`;
  }
  function textareaField(name, label, value = '', placeholder = '', required = false) {
    return `<div class="field span-2"><label for="f-${esc(name)}">${esc(label)}</label><textarea name="${esc(name)}" id="f-${esc(name)}" maxlength="4000" placeholder="${esc(placeholder)}"${required ? ' required' : ''}>${esc(value)}</textarea></div>`;
  }
  function showModal(title, content) {
    const modal = $('#modal');
    modal.innerHTML = `<div class="modal-header"><h2 id="modal-title">${esc(title)}</h2><button class="icon-button" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></div>${content}`;
    if (!modal.open) modal.showModal();
    const form = $('form', modal);
    if (form?.id === 'log-form') {
      const saved = form.dataset.kind === 'additional' ? logs().find(log => log.session_id === form.dataset.session) || {} : workoutLog(form.dataset.date) || {};
      $('.form-grid', form).insertAdjacentHTML('beforeend', textareaField('instructions', 'Reviewed board / workout instructions', saved.instructions || '', 'Optional: type or apply reviewed board text'));
      $('[name="instructions"]', form).maxLength = 8000;
      mountPhoto(form, saved);
    } else if (form?.id === 'external-form') {
      mountPhoto(form, arr(state.dashboard.external_classes).find(item => item.date === $('[name="date"]', form).value) || workouts().find(item => item.date === $('[name="date"]', form).value && item.type === 'external') || {}, 'main');
      $('[name="date"]', form).addEventListener('change', () => {
        // Open the selected class rather than carrying another date's private attachment.
        externalModal($('[name="date"]', form).value);
      });
    }
  }
  function modalForm(id, content, submit = 'Save', attributes = '') { return `<form id="${esc(id)}" ${attributes}><div class="form-grid">${content}</div><div class="form-actions"><button class="btn" type="submit">${esc(submit)}</button><button class="btn outline" type="button" data-action="close-modal">Cancel</button></div><p class="form-error" role="alert"></p></form>`; }
  function readinessModal() {
    const checkin = state.dashboard.checkin || {};
    showModal('Meet yourself where you are.', `<p class="small muted modal-intro">An honest check-in is more useful than a perfect score. Pain can change the plan: don’t train through warning signs.</p>${modalForm('readiness-form', field('sleep', 'Sleep (hours)', 'number', checkin.sleep ?? '', { required: true, min: 0, max: 24, step: .5 }) + field('soreness', 'Soreness (0–10)', 'number', checkin.soreness ?? '', { required: true, min: 0, max: 10, step: 1 }) + field('fatigue', 'Fatigue (0–10)', 'number', checkin.fatigue ?? '', { required: true, min: 0, max: 10, step: 1 }) + field('pain', 'Pain (0–10)', 'number', checkin.pain ?? '', { required: true, min: 0, max: 10, step: 1 }), 'Save check-in')}`);
  }
  const metricSpecs = {
    distance: ['Distance (km)', 'number', .01], distance_m: ['Distance (m)', 'number', 1], pace: ['Pace per km (M:SS)', 'text'], splits: ['Measured splits (M:SS, comma-separated)', 'text'], hr: ['Average heart rate (bpm)', 'number', 1], exercise: ['Exercise', 'text'], sets: ['Sets', 'number', 1], reps: ['Reps', 'number', 1], load: ['Load (kg)', 'number', .5], station: ['Station name', 'text'], time: ['Station time (M:SS)', 'text'], rest: ['Rest (seconds)', 'number', 1], stroke_rate: ['Stroke rate (strokes/min)', 'number', 1]
  };
  function logModal(id) {
    const workout = findWorkout(id);
    if (!workout) return notify('Choose a workout from the plan first.');
    const saved = workoutLog(workout.date) || {};
    const metrics = [...new Set([...arr(workout.metrics), 'distance', 'pace', 'splits', 'hr', 'exercise', 'sets', 'reps', 'load', 'station', 'time', 'rest', 'stroke_rate'])].filter(item => typeof item === 'string' && !['duration', 'rpe', 'notes', 'runs', 'stations', 'transitions'].includes(item));
    showModal('Record the work you did.', `<p class="small muted modal-intro">${esc(workout.title)} · ${esc(dateLabel(workout.date))}. Completed or modified work needs duration and RPE. Other metrics are optional: leave unmeasured values blank. Saving works offline.</p>${modalForm('log-form', selectField('status', 'Session status', ['completed', 'started', 'skipped', 'modified'], saved.status || 'completed') + field('duration', 'Duration (minutes)', 'number', saved.duration ?? workout.duration, { min: 0, max: 600, step: 1, required: true }) + field('rpe', 'Effort / RPE (1–10)', 'number', saved.rpe ?? '', { min: 1, max: 10, step: 1 }) + field('energy', 'Energy (0–10)', 'number', saved.energy ?? '', { min: 0, max: 10, step: 1 }) + field('soreness', 'Soreness (0–10)', 'number', saved.soreness ?? '', { min: 0, max: 10, step: 1 }) + field('sleep', 'Sleep (hours)', 'number', saved.sleep ?? '', { min: 0, max: 24, step: .5 }) + field('pain', 'Pain (0–10)', 'number', saved.pain ?? '', { min: 0, max: 10, step: 1 }) + field('session_time', 'Session time', 'time', saved.session_time || '') + metrics.map(key => {
      const spec = metricSpecs[key] || [titleCase(key), 'text'];
      const value = saved.metrics?.[key];
      return field(`metric_${key}`, spec[0], spec[1], Array.isArray(value) ? value.map(time).join(', ') : ['pace', 'time'].includes(key) && typeof value === 'number' ? time(value) : value ?? '', spec[1] === 'number' ? { min: 0, max: key === 'hr' ? 250 : 100000, step: spec[2] || .1 } : { maxlength: 1000 });
    }).join('') + textareaField('modification', 'If modified, what changed?', saved.modification || '', 'What did you do instead, and why?') + textareaField('notes', 'Session notes', saved.notes || '', 'How did it feel? What should your next session know?') + textareaField('pre_session_food', 'Pre-session food (optional)', saved.pre_session_food || '') + textareaField('glucose_notes', 'Glucose notes (optional)', saved.glucose_notes || '', 'Your observations only. No medication dosing advice.'), 'Save workout', `data-date="${esc(workout.date)}"`)}`);
  }
  function externalModal(date = state.selectedDate) {
    const existing = arr(state.dashboard.external_classes).find(item => item.date === date) || workouts().find(item => item.date === date);
    showModal('Make room for your class.', `<p class="small muted modal-intro">This replaces your personal planned session on the selected date. Include class instructions, sets, reps and loads so they’re available offline.</p>${modalForm('external-form', field('date', 'Class date', 'date', date || today(), { required: true }) + field('title', 'Class title', 'text', existing?.type === 'external' ? existing.title : '', { required: true, maxlength: 120 }) + field('duration', 'Duration (minutes)', 'number', existing?.type === 'external' ? existing.duration : 45, { required: true, min: 1, max: 180, step: 1 }) + selectField('intensity', 'Intensity', ['easy', 'moderate', 'hard', 'recovery'], existing?.type === 'external' ? existing.intensity : 'moderate') + textareaField('main', 'Class instructions (one step per line)', existing?.type === 'external' ? arr(existing.main).join('\n') : '', '4 sets × 8 reps\nExercise, load and rest instructions', true), 'Save class & update plan')}`);
  }
  function additionalModal(date = today(), sessionId) {
    const saved = sessionId ? logs().find(log => log.kind === 'additional' && log.session_id === sessionId) : {};
    if (!saved) throw new Error('This session is no longer available. Refresh your history.');
    showModal(sessionId ? 'Update additional workout.' : 'Log additional workout.', `<p class="small muted modal-intro">Record another session without replacing or completing your planned workout. Every session contributes to load and readiness. Saves work offline.</p>${modalForm('log-form',
      field('date', 'Session date', 'date', saved.date || date || today(), { required: true, max: today() }) +
      field('title', 'Workout title', 'text', saved.title || '', { required: true, maxlength: 150, placeholder: 'Evening easy run' }) +
      field('type', 'Workout type', 'text', saved.type || 'run', { required: true, maxlength: 60, placeholder: 'run, strength, hyrox, class, recovery…' }) +
      selectField('status', 'Session status', ['completed', 'started', 'skipped', 'modified'], saved.status || 'completed') +
      field('duration', 'Duration (minutes)', 'number', saved.duration ?? 30, { required: true, min: 0, max: 600, step: 1 }) +
      field('rpe', 'Effort / RPE (1–10)', 'number', saved.rpe || '', { min: 1, max: 10, step: 1 }) +
      field('session_time', 'Session time (optional)', 'time', saved.session_time || '') +
      textareaField('modification', 'If modified, what changed?', saved.modification || '') +
      textareaField('notes', 'Session notes', saved.notes || ''),
      'Save workout', `data-kind="additional" data-session="${esc(sessionId || uuid())}"`)}`);
  }
  function measurementModal(id) {
    const station = stations().find(item => item.id === id);
    if (!station) return;
    const measured = state.dashboard.measurements?.[id] || {};
    showModal(`${station.name}: real measurements`, `<p class="small muted modal-intro">Use comparable full-station tests. Fatigue is rated 0–10. Share is Kenza’s percentage of station work, not running. Blank values remove a previous measurement.</p>${modalForm('measurement-form', field('kenza_time', 'Kenza station time', 'text', measured.kenza_seconds == null ? '' : time(measured.kenza_seconds), { placeholder: 'M:SS' }) + field('rob_time', 'Rob station time', 'text', measured.rob_seconds == null ? '' : time(measured.rob_seconds), { placeholder: 'M:SS' }) + field('kenza_fatigue', 'Kenza fatigue (0–10)', 'number', measured.kenza_fatigue ?? '', { min: 0, max: 10, step: 1 }) + field('rob_fatigue', 'Rob fatigue (0–10)', 'number', measured.rob_fatigue ?? '', { min: 0, max: 10, step: 1 }) + field('transition_time', 'Transition time', 'text', measured.transition_seconds == null ? '' : time(measured.transition_seconds), { placeholder: 'M:SS' }) + field('preferred_share', 'Kenza preferred share (%)', 'number', measured.preferred_share == null ? '' : Math.round(measured.preferred_share * 100), { min: 0, max: 100, step: 1 }), 'Save measurements', `data-station="${esc(id)}"`)}`);
  }
  function simulationModal() {
    const stationFields = stations().map(station => field(`station_${station.id}`, `${station.name} time`, 'text', '', { placeholder: 'M:SS · optional' }) + field(`allocation_${station.id}`, `${station.name}: Kenza share (%)`, 'number', '', { min: 0, max: 100, step: 1 })).join('');
    showModal('Your race rehearsal, recorded.', `<p class="small muted modal-intro">Total time is required. Only enter splits that were measured. Eight run splits and eight transition splits if available; leave blank if not recorded.</p>${modalForm('simulation-form', field('date', 'Simulation date', 'date', today(), { required: true, max: today() }) + field('total', 'Total time', 'text', '', { placeholder: '1:25:00', required: true }) + field('rpe', 'Overall RPE (1–10)', 'number', '', { min: 1, max: 10, step: 1 }) + field('difficulty', 'Difficulty (0–10, optional)', 'number', '', { min: 0, max: 10, step: 1 }) + textareaField('runs', 'Eight run splits (comma-separated)', '', '5:30, 5:35, 5:40, …') + textareaField('transitions', 'Eight transitions (comma-separated)', '', '0:20, 0:25, 0:20, …') + stationFields + textareaField('notes', 'Session notes') + textareaField('pacing_notes', 'Pacing observations') + textareaField('fuelling_notes', 'Fuelling observations'), 'Save measured simulation')}`);
  }
  function scenarioModal() {
    showModal('A scenario, not a promise.', `<p class="small muted modal-intro">The same shared pace is applied to eight 1 km runs. Enter all eight station and transition times. This arithmetic scenario is not stored as a measured simulation.</p>${modalForm('scenario-form', field('pace', 'Shared pace per km', 'text', '5:30', { required: true, placeholder: 'M:SS' }) + '<div></div>' + stations().map(station => field(`station_${station.id}`, station.name, 'text', '', { required: true, placeholder: 'M:SS' })).join('') + textareaField('transitions', 'Eight transition times (comma-separated)', '', '0:20, 0:20, 0:20, 0:20, 0:20, 0:20, 0:20, 0:20', true), 'Calculate scenario')}<div id="scenario-result" aria-live="polite"></div>`);
  }
  function stationSettingsModal() {
    showModal('Confirm your race standards.', `<p class="small muted modal-intro">Confirm distances and loads against your division’s official event rules. Sled loads include the sled. Only distances, loads and your notes are changed; station instructions remain available offline.</p>${modalForm('station-settings-form', stations().map(station => `<div class="span-2"><h3>${esc(station.name)}</h3><p class="micro muted">${esc(station.reference || station.instruction || '')}</p></div>${field(`distance_${station.id}`, `Distance / reps (${station.unit || 'm'})`, 'number', station.distance, { min: 0, max: 2000, step: 1, required: true })}${field(`load_${station.id}`, `Load (${station.load_unit || 'kg'})`, 'number', station.load ?? '', { min: 0, max: 2000, step: .5 })}${textareaField(`notes_${station.id}`, `${station.name} notes`, station.notes || '')}`).join(''), 'Save station standards')}`);
  }
  function splitTimes(value, label, required = false) {
    const text = String(value || '').trim();
    if (!text && !required) return [];
    const parts = text.split(',').map(item => item.trim());
    if (parts.length !== 8 || parts.some(item => !item)) throw new Error(`${label}: enter all eight values, separated by commas, or leave the entire field blank.`);
    return parts.map((item, index) => parseTime(item, `${label} ${index + 1}`));
  }
  async function saveOnline(path, method, data, message) {
    const session = await api('/api/session');
    if (String(session.user.id) !== String(state.session.user.id)) throw new Error('Your signed-in account changed. Reload before making changes.');
    state.session = session;
    await api(path, method, data);
    await refresh();
    $('#modal').close();
    render();
    notify(message);
  }
  async function logout() {
    if (!navigator.onLine || state.offline) return notify('Connect before signing out so your server session can be closed securely.');
    let allQueued;
    try { allQueued = await store('all', 'queue'); } catch { allQueued = state.queue; }
    const content = `<p class="small muted">${allQueued.length ? `You have ${allQueued.length} unsynced workout${allQueued.length === 1 ? '' : 's'} on this device. Signing out will permanently discard these local records. Sync first to keep them.` : 'Signing out closes your session and clears this device’s cached plan, history and private data.'}</p><div class="form-actions">${allQueued.length ? '<button class="btn secondary" data-action="sync-close">Sync first</button>' : ''}<button class="btn danger" data-action="confirm-logout">${allQueued.length ? 'Discard & sign out' : 'Sign out & clear device'}</button><button class="btn outline" data-action="close-modal">Cancel</button></div><p class="form-error" role="alert"></p>`;
    showModal('Sign out of this device?', content);
  }
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    try {
      if (action === 'theme') {
        state.theme = state.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = state.theme;
        try { localStorage.setItem('pair-theme', state.theme); } catch { /* Theme remains applied for this visit. */ }
        if (state.session) render();
      } else if (action === 'settings') location.hash = '#/settings';
      else if (action.startsWith('auth-')) { if (!navigator.onLine) return notify('Connect to access an account. Offline account switching is not allowed.'); state.authMode = action.slice(5); renderAuth(); }
      else if (action === 'close-modal') $('#modal').close();
      else if (action === 'readiness') readinessModal();
      else if (action === 'log') logModal(button.dataset.id);
      else if (action === 'additional') additionalModal(button.dataset.date || today(), button.dataset.session);
      else if (action === 'external') externalModal(button.dataset.date);
      else if (action === 'view-photo') {
        const userId = state.session.user.id;
        const photo = await loadPhoto(button.dataset.photo);
        if (String(state.session?.user.id) !== String(userId)) return;
        showModal('Your private workout board.', '<img class="board-preview" alt="Your saved workout board"><p class="small muted">Edit the workout log or class to replace or remove this photo.</p>');
        $('#modal img').src = `data:image/jpeg;base64,${photo}`;
      }
      else if (action === 'simulation') simulationModal();
      else if (action === 'scenario') scenarioModal();
      else if (action === 'station-settings') stationSettingsModal();
      else if (action === 'measure') measurementModal(button.dataset.station);
      else if (action === 'filter') { state.filter = button.dataset.filter; render(); }
      else if (action === 'week-prev' || action === 'week-next') { state.week = addDays(state.week, action === 'week-next' ? 7 : -7); state.selectedDate = state.week; render(); }
      else if (action === 'day') { state.selectedDate = button.dataset.date; render(); document.getElementById(`day-${state.selectedDate}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
      else if (action === 'sync' || action === 'sync-close') {
        button.disabled = true;
        if (action === 'sync-close') $('#modal').close();
        await syncQueue();
        notify(state.syncError || (!navigator.onLine ? 'Still offline. Your saved workouts are safe on this device.' : 'Your training data is up to date.'));
      } else if (action === 'reauth') { if (!navigator.onLine) throw new Error('Connect before signing in again. Your queue is retained.'); state.session = null; state.dashboard = null; state.authMode = 'login'; renderAuth('Sign in again to replay your saved workout queue.'); }
      else if (action === 'logout') await logout();
      else if (action === 'confirm-logout') {
        button.disabled = true;
        if (syncPromise) await syncPromise;
        await withPrivateLock(async () => {
          const session = await api('/api/session');
          await api('/api/logout', 'POST', {}, session.csrf_token);
          state.session = null;
          await store('clear', 'private');
          await store('clear', 'queue');
          state.session = null; state.dashboard = null; state.queue = []; state.chat = []; state.syncError = ''; state.offline = false; state.authMode = 'login';
          invalidateOtherTabs();
          $('#modal').close(); location.hash = ''; renderAuth(); notify('Signed out. Private device data cleared.');
        });
      } else if (action === 'copy-invite') {
        const code = team().invite_code;
        if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(code); notify('Invite code copied.'); }
        else showModal('Your invite code', `<p class="invite-code">${esc(code)}</p><p class="small muted">Select and copy this code to share it with your partner.</p>`);
      } else if (action === 'team-name') showModal('Your team, your name.', modalForm('team-form', field('name', 'Team name', 'text', team().name || 'Kenza + Rob', { required: true, maxlength: 100 }), 'Save team name'));
      else if (action === 'prompt') { const input = $('#coach-form textarea'); input.value = button.dataset.question; input.focus(); }
    } catch (error) {
      button.disabled = false;
      const modalError = $('#modal .form-error');
      if ($('#modal').open && modalError) modalError.textContent = error.message;
      else notify(error.message);
    }
  });
  document.addEventListener('submit', async event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    event.preventDefault();
    if (!form.reportValidity()) return;
    const button = $('button[type="submit"]', form);
    const values = Object.fromEntries(new FormData(form));
    $('.form-error', form)?.replaceChildren();
    if (button) button.disabled = true;
    try {
      if (form.id === 'auth-form') {
        if (!navigator.onLine) throw new Error('Connect to sign in. Offline account switching is not allowed.');
        const mode = form.dataset.mode;
        if (mode === 'reset') {
          await api('/api/password-reset', 'POST', { email: values.email });
          $('.form-error', form).textContent = 'If an account exists and email delivery is configured, reset instructions will be sent. If you cannot receive email, contact the service administrator.';
        } else if (mode === 'confirm') {
          await api('/api/password-reset/confirm', 'POST', { token: resetToken(), password: values.password });
          history.replaceState(null, '', '/');
          state.authMode = 'login'; renderAuth('Password updated. Sign in with your new password.');
        } else {
          await withPrivateLock(async () => {
            const data = await api(`/api/${mode === 'signup' ? 'signup' : 'login'}`, 'POST', mode === 'signup' ? { email: values.email, password: values.password, person: values.person, ...(values.invite_code ? { invite_code: values.invite_code.trim() } : {}) } : { email: values.email, password: values.password });
            state.session = data;
            state.chat = [];
            state.offline = false;
            await refresh();
            invalidateOtherTabs();
          });
          render(); if (state.queue.length) await syncQueue();
        }
      } else if (form.id === 'log-form') {
        const additional = form.dataset.kind === 'additional';
        const date = additional ? values.date : form.dataset.date;
        if (date > today()) throw new Error('Record this workout on or after its session date, not in advance.');
        const payload = { client_id: uuid(), athlete_id: state.session.user.id, date, status: values.status, duration: Number(values.duration), metrics: {} };
        Object.assign(payload, photoPayload(form), { instructions: values.instructions || '' });
        if (additional) {
          Object.assign(payload, { kind: 'additional', session_id: form.dataset.session, title: values.title.trim(), type: values.type.trim().toLowerCase() });
          if (!payload.title || !payload.type) throw new Error('Enter a workout title and type.');
        }
        ['rpe', 'energy', 'soreness', 'sleep', 'pain'].forEach(key => { if (values[key] != null && values[key] !== '') payload[key] = Number(values[key]); });
        ['notes', 'session_time', 'pre_session_food', 'glucose_notes', 'modification'].forEach(key => { if (values[key]) payload[key] = values[key]; });
        Object.entries(values).filter(([key, value]) => key.startsWith('metric_') && value !== '').forEach(([key, value]) => {
          const metric = key.slice(7);
          if (metric === 'splits') payload.metrics[metric] = value.split(',').map((item, index) => parseTime(item, `Split ${index + 1}`));
          else if (['pace', 'time'].includes(metric)) payload.metrics[metric] = parseTime(value, titleCase(metric));
          else payload.metrics[metric] = metricSpecs[metric]?.[1] === 'number' ? Number(value) : value;
        });
        if (payload.metrics.distance != null) payload.metrics.unit = 'km';
        if (['completed', 'modified'].includes(payload.status) && (!(payload.duration > 0) || !(payload.rpe >= 1 && payload.rpe <= 10))) throw new Error('Completed or modified sessions need a positive duration and an RPE between 1 and 10.');
        if (payload.status === 'modified' && !payload.modification) throw new Error('Describe what changed for a modified workout.');
        await queueWorkout(payload);
        $('#modal').close(); render(); notify('Workout saved on this device.');
        if (navigator.onLine) await syncQueue();
      } else if (form.id === 'readiness-form') {
        await saveOnline('/api/readiness', 'POST', Object.fromEntries(Object.entries(values).map(([key, value]) => [key, Number(value)])), 'Check-in saved. Your plan has been refreshed.');
      } else if (form.id === 'profile-form') {
        const data = { goals: values.goals, fuelling_preferences: values.fuelling_preferences, notes: values.notes, easy_pace: values.easy_pace };
        if (values.benchmark) data.benchmark_seconds = parseTime(values.benchmark, '10 km benchmark');
        await saveOnline('/api/profile', 'PUT', data, 'Profile updated.');
      } else if (form.id === 'race-form') {
        if (values.plan_start >= values.date) throw new Error('Plan start must be before race day.');
        if (values.simulation_date <= values.plan_start || values.simulation_date >= values.date) throw new Error('Simulation date must be after plan start and before race day.');
        const data = { name: values.name, date: values.date, plan_start: values.plan_start, target_seconds: parseTime(values.target, 'Target finish time'), simulation_date: values.simulation_date };
        await saveOnline('/api/race', 'PUT', data, 'Race settings saved. Your training plan is refreshed.');
      } else if (form.id === 'external-form') {
        const data = { date: values.date, title: values.title, duration: Number(values.duration), intensity: values.intensity, main: values.main.split('\n').map(line => line.trim()).filter(Boolean), ...photoPayload(form) };
        const result = await api('/api/workouts/external', 'POST', data);
        await rememberPhoto(result.workout?.photo_id, data.photo).catch(() => {});
        await refresh(); $('#modal').close(); render(); notify('Class saved to your plan (not marked complete).');
      } else if (form.id === 'measurement-form') {
        const measured = {};
        ['kenza_time', 'rob_time', 'transition_time'].forEach(key => { if (values[key]) measured[key.replace('_time', '_seconds')] = parseTime(values[key], titleCase(key)); });
        ['kenza_fatigue', 'rob_fatigue', 'preferred_share'].forEach(key => { if (values[key] !== '') measured[key] = Number(values[key]) / (key === 'preferred_share' ? 100 : 1); });
        await saveOnline('/api/measurements', 'PUT', { measurements: { ...(state.dashboard.measurements || {}), [form.dataset.station]: measured } }, 'Station measurements saved.');
      } else if (form.id === 'simulation-form') {
        const data = { date: values.date, total_seconds: parseTime(values.total, 'Total simulation time'), runs: splitTimes(values.runs, 'Run splits'), transitions: splitTimes(values.transitions, 'Transitions'), stations: {}, allocations: {}, notes: values.notes, pacing_notes: values.pacing_notes, fuelling_notes: values.fuelling_notes };
        if (values.difficulty !== '') data.difficulty = Number(values.difficulty);
        if (values.rpe !== '') data.rpe = Number(values.rpe);
        stations().forEach(station => {
          if (values[`station_${station.id}`]) data.stations[station.id] = parseTime(values[`station_${station.id}`], station.name);
          if (values[`allocation_${station.id}`] !== '') data.allocations[station.id] = Number(values[`allocation_${station.id}`]);
        });
        await saveOnline('/api/simulations', 'POST', data, 'Measured simulation saved.');
        location.hash = '#/simulations';
      } else if (form.id === 'scenario-form') {
        const session = await api('/api/session');
        if (String(session.user.id) !== String(state.session.user.id)) throw new Error('Account changed. Reload before requesting a scenario.');
        state.session = session;
        const data = await api('/api/scenario', 'POST', { run_pace_seconds: parseTime(values.pace, 'Shared run pace'), station_seconds: stations().map(station => parseTime(values[`station_${station.id}`], station.name)), transition_seconds: splitTimes(values.transitions, 'Transitions', true) });
        $('#scenario-result').innerHTML = `<div class="notice section"><strong>Hypothetical finish: ${esc(time(data.seconds))}</strong><br>Running ${esc(time(data.run_seconds ?? data.breakdown?.runs))} · Stations ${esc(time(data.station_seconds ?? data.breakdown?.stations))} · Transitions ${esc(time(data.transition_seconds ?? data.breakdown?.transitions))}<br>Arithmetic scenario only. Not saved as measured data or a guaranteed projection.</div>`;
      } else if (form.id === 'station-settings-form') {
        const data = stations().map(({ index, ...station }) => ({ ...station, distance: Number(values[`distance_${station.id}`]), load: values[`load_${station.id}`] === '' ? null : Number(values[`load_${station.id}`]), notes: values[`notes_${station.id}`] }));
        await saveOnline('/api/stations', 'PUT', { stations: data }, 'Station standards updated.');
      } else if (form.id === 'team-form') {
        await saveOnline('/api/team', 'PUT', { name: values.name }, 'Team name updated.');
      } else if (form.id === 'coach-form') {
        if (!navigator.onLine || state.offline) throw new Error('Coach is unavailable offline. Open your downloaded workout for the last saved guidance.');
        const question = values.question.trim();
        if (!question) throw new Error('Enter a training question first.');
        const session = await api('/api/session');
        if (String(session.user.id) !== String(state.session.user.id)) throw new Error('Account changed. Reload before asking the coach.');
        state.session = session;
        const answer = await api('/api/coach', 'POST', { question });
        state.chat.push({ role: 'user', text: question }, { role: 'coach', text: typeof answer.answer === 'string' ? answer.answer : words(answer.answer) || 'No answer was returned. Please try again.' });
        render(); $('#coach-form textarea').focus();
      }
    } catch (error) { errorText(form, error); }
    finally { if (button) button.disabled = false; }
  });
  window.addEventListener('hashchange', () => {
    if (state.session && state.dashboard) { render(); window.scrollTo(0, 0); $('#main')?.focus({ preventScroll: true }); }
  });
  window.addEventListener('offline', () => { state.offline = true; if (state.session && state.dashboard) render(); });
  window.addEventListener('online', () => { if (state.session) syncQueue(); else renderAuth(); });
  window.addEventListener('storage', event => {
    if (event.key !== 'pair-account-event') return;
    state.session = null; state.dashboard = null; state.queue = []; state.chat = []; state.syncError = ''; state.offline = false; state.authMode = 'login';
    $('#modal').close();
    renderAuth('The account session changed in another tab. Connect and sign in to securely reopen your training space.');
  });
  $('#modal').addEventListener('click', event => { if (event.target === $('#modal') && event.clientX && (event.clientX < $('#modal').getBoundingClientRect().left || event.clientX > $('#modal').getBoundingClientRect().right || event.clientY < $('#modal').getBoundingClientRect().top || event.clientY > $('#modal').getBoundingClientRect().bottom)) $('#modal').close(); });
  init();
})();
