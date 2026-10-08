'use strict';

(async () => {
  const { state, logs, logModal, additionalModal, store, cacheSession, rememberPhoto, loadQueue, photoRecord } = window.testApp;
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const waitFor = async (condition, message) => {
    for (let i = 0; i < 200; i++) {
      if (condition()) return;
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    throw new Error(message);
  };
  const date = '2020-01-01';
  const photoId = 'a'.repeat(32);
  const otherId = 'b'.repeat(32);
  const saved = { date, status: 'started', duration: 30, photo_id: photoId, instructions: 'Original board', notes: 'Old note' };
  const extra = { ...saved, kind: 'additional', session_id: 'extra-1', title: 'Extra', type: 'run', photo_id: otherId, instructions: 'Extra board' };
  const second = { ...extra, session_id: 'extra-2', instructions: 'Second board' };
  const queued = (payload, index) => ({ created_at: `2020-01-01T00:00:0${index}Z`, payload });
  const planned = () => logs().find(log => log.kind !== 'additional');
  const additional = id => logs().find(log => log.session_id === id);
  try {
    state.dashboard = { logs: [saved, extra, second], plan: [{ date, title: 'Planned', duration: 30, metrics: [] }] };
    state.queue = [queued({ date, status: 'started', duration: 40 }, 1)];
    assert(planned().photo_id === photoId && planned().instructions === saved.instructions, 'Omitted metadata must retain saved values');
    assert(!planned().notes, 'Ordinary omitted log fields must remain replacement semantics');
    assert(additional('extra-1').photo_id === otherId, 'Planned edit must not affect additional sessions');

    state.queue.push(queued({ date, photo: 'replacement', instructions: 'New board' }, 2));
    state.queue.push(queued({ date, duration: 50 }, 3));
    state.queue.reverse();
    assert(planned().photo === 'replacement' && !planned().photo_id, 'Sequential omitted photo must retain replacement, not stale ID');
    assert(planned().instructions === 'New board', 'Sequential omitted instructions must retain latest text');
    assert(!photoRecord(planned()).includes('data-photo='), 'Replacement record must not offer old photo');
    state.queue.push(queued({ date, photo: null, instructions: '' }, 4));
    state.queue.push(queued({ date, duration: 60 }, 5));
    assert(planned().photo === null && !planned().photo_id, 'Removal must persist through later omitted photo');
    assert(planned().instructions === '' && photoRecord(planned()) === '', 'Blank instructions must clear, not restore');
    assert(additional('extra-1').instructions === 'Extra board', 'Planned clear must not affect additional instructions');

    state.queue.push(queued({ ...extra, photo: 'extra replacement', instructions: '' }, 6));
    state.queue.push(queued({ date, kind: 'additional', session_id: 'extra-1', duration: 70 }, 7));
    assert(additional('extra-1').photo === 'extra replacement' && !additional('extra-1').photo_id, 'Additional replacement must clear stale ID');
    assert(additional('extra-1').instructions === '', 'Additional blank instructions must persist');
    assert(additional('extra-2').instructions === 'Second board' && additional('extra-2').photo_id === otherId, 'Same-date additional sessions must remain separate');
    assert(saved.photo_id === photoId && saved.instructions === 'Original board', 'Overlay must not mutate dashboard');

    // Exercise actual IndexedDB, form submit and modal reopening without any API access.
    state.queue = [];
    state.session = { user: { id: 1 } };
    state.offline = true;
    Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false });
    let fetches = 0;
    window.fetch = async () => { fetches++; throw new Error('Offline'); };
    history.replaceState(null, '', '#/progress');
    await cacheSession(state.session);
    const photo = document.createElement('canvas');
    photo.width = photo.height = 2;
    const original = photo.toDataURL('image/jpeg').split(',')[1];
    photo.getContext('2d').fillRect(0, 0, 2, 2);
    const replacement = photo.toDataURL('image/jpeg').split(',')[1];
    await rememberPhoto(photoId, original);
    await rememberPhoto(otherId, replacement);

    const preview = () => document.querySelector('#modal .board-preview');
    const close = () => document.querySelector('#modal').close();
    const save = async () => {
      const form = document.querySelector('#log-form');
      form.requestSubmit();
      await waitFor(() => !document.querySelector('#modal').open, 'Offline form did not save');
      assert(!form.querySelector('.form-error').textContent, 'Offline form error');
      await loadQueue();
    };
    logModal(date);
    await waitFor(() => !preview().hidden && preview().src.endsWith(original), 'Initial cached photo did not load offline');
    await save();
    assert(!Object.hasOwn(state.queue[0].payload, 'photo'), 'Unchanged photo must remain omitted from request');
    logModal(date);
    await waitFor(() => !preview().hidden && preview().src.endsWith(original), 'Cached photo lost on offline reopen after edit');
    assert(document.querySelector('[name="instructions"]').value === saved.instructions, 'Saved instructions lost on reopen');
    close();
    additionalModal(date, 'extra-1');
    await waitFor(() => !preview().hidden && preview().src.endsWith(replacement), 'Additional cached photo lost after planned edit');
    await save();
    additionalModal(date, 'extra-1');
    await waitFor(() => !preview().hidden && preview().src.endsWith(replacement), 'Additional unchanged photo lost on reopen');
    close();

    logModal(date);
    const input = document.querySelector('[data-photo-file]');
    const transfer = new DataTransfer();
    transfer.items.add(new File([Uint8Array.from(atob(replacement), c => c.charCodeAt(0))], 'replacement.jpg', { type: 'image/jpeg' }));
    input.files = transfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await waitFor(() => document.querySelector('#log-form').photoChange && !document.querySelector('#log-form').photoBusy, 'Replacement did not normalize');
    const normalized = document.querySelector('#log-form').photoChange;
    await save();
    assert(!planned().photo_id, 'Queued upload kept old photo ID');
    logModal(date);
    assert(!preview().hidden && preview().src.endsWith(normalized), 'Offline replacement reopen shows stale or missing photo');
    await save();
    logModal(date);
    assert(preview().src.endsWith(normalized), 'Second offline edit lost queued replacement');
    document.querySelector('[data-photo-remove]').click();
    document.querySelector('[name="instructions"]').value = '';
    await save();
    logModal(date);
    assert(preview().hidden && !preview().hasAttribute('src'), 'Removed photo reappeared on reopen');
    assert(document.querySelector('[name="instructions"]').value === '', 'Blank instructions restored old text');
    close();
    additionalModal(date, 'extra-2');
    await waitFor(() => !preview().hidden && preview().src.endsWith(replacement), 'Another same-date session photo was changed');
    assert(document.querySelector('[name="instructions"]').value === 'Second board', 'Another session instructions were changed');
    close();
    assert(fetches === 0, 'Offline retained/replaced/removed photos must not fetch stale server data');
    document.querySelector('#result').textContent = 'PASS';
  } catch (error) {
    document.querySelector('#result').textContent = `FAIL: ${error.stack}`;
  }
})();
