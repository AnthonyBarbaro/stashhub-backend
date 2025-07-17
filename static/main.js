/*  static/main.js  */

/* ─────────────────────────  Global refs ───────────────────────── */
let loading, loadingMsg, runButton, brandPicker;

/* ────────────────────────  UI helpers  ───────────────────────── */
function showLoading(msg = 'Loading…') {
  loadingMsg.textContent = msg;
  loading.classList.remove('hidden');
}
function hideLoading() {
  loading.classList.add('hidden');
}
function showStatus(msg, isError = false) {
  const el = document.getElementById('status-message');
  el.textContent = msg;
  el.className = `status-message visible ${isError ? 'error' : 'success'}`;
}
function clearStatus() {
  const el = document.getElementById('status-message');
  el.textContent = '';
  el.className  = 'status-message';
}

/* ───────────────────  fetch brands → Choices.js  ────────────────── */
async function loadBrands() {
  try {
    const res = await fetch('/brands');
    if (!res.ok) throw new Error('Could not fetch brands');
    const brands = await res.json();

    if (!Array.isArray(brands) || brands.length === 0) {
      showStatus('❌ No brands found in CSV folder.', true);
      return;
    }

    brandPicker.clearChoices();
    brandPicker.setChoices(
      brands.map(b => ({ value: b, label: b })),
      'value',
      'label',
      true
    );

    /* reveal brand section + run form */
    document.getElementById('brand-section').classList.remove('hidden');
    document.getElementById('run-form').classList.remove('hidden');
  } catch (err) {
    showStatus(`❌ Failed to load brands: ${err.message}`, true);
  }
}

/* ────── poll /status every 2 s until ✅ or ❌, then refresh UI ───── */
async function pollStatusAndLoadBrands() {
  let last = '';
  while (true) {
    const res = await fetch('/status');
    const txt = await res.text();

    if (txt !== last) {               /* new line => show it */
      showStatus(txt, txt.startsWith('❌'));
      last = txt;
    }
    if (txt.startsWith('✅') || txt.startsWith('❌')) {
      hideLoading();
      runButton.disabled = false;
      if (txt.startsWith('✅')) await loadBrands();  /* refresh brand list */
      break;
    }
    await new Promise(r => setTimeout(r, 2000));
  }
}

/* ───────────────────────  Main entrypoint  ─────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  /* cache DOM handles */
  loading     = document.getElementById('loading');
  loadingMsg  = document.getElementById('loading-msg');
  runButton   = document.getElementById('run-button');

  const updateForm = document.getElementById('update-form');
  const brandList  = document.getElementById('brand-list');
  const runForm    = document.getElementById('run-form');

  /* Choices multi‑select */
  brandPicker = new Choices(brandList, {
    removeItemButton      : true,
    placeholderValue      : 'Type to search brands',
    searchPlaceholderValue: 'Filter brands…',
    shouldSort            : false,
    duplicateItemsAllowed : false,
  });

  /* load any brands that may already be present */
  loadBrands();

  /* ──────── Update‑Files click ───────── */
  updateForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearStatus();
    showLoading('Running Selenium… this may take a minute');

    try {
      const res  = await fetch('/update-files', { method: 'POST' });
      const json = await res.json();

      if (!res.ok || !json.ok) {
        hideLoading();
        showStatus(`❌ Catalog scrape failed: ${json.msg || ''}`, true);
        return;
      }
      /* start polling; when finished loadBrands() will run */
      await pollStatusAndLoadBrands();
    } catch (err) {
      hideLoading();
      showStatus(`❌ Network error: ${err.message}`, true);
    }
  });

  /* select‑all / clear actions */
  document.getElementById('select-all-brands').addEventListener('click', () => {
    const values = Array.from(brandList.options).map(o => o.value);
    brandPicker.setChoiceByValue(values);
  });
  document.getElementById('clear-all-brands').addEventListener('click', () => {
    brandPicker.removeActiveItems();
  });

  /* ──────── Run click ───────── */
  runForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    runButton.disabled = true;
    const emails = document.getElementById('emails').value.trim();
    const brands = brandPicker.getValue(true);      // array of selected values

    if (!emails) {
      showStatus('❌ Please enter at least one email.', true);
      runButton.disabled = false;
      return;
    }
    if (brands.length === 0) {
      showStatus('❌ Please select at least one brand.', true);
      runButton.disabled = false;
      return;
    }

    clearStatus();
    showLoading('Generating reports & uploading to Drive…');

    try {
      const res  = await fetch('/run', {
        method : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body   : JSON.stringify({ emails, brands })
      });
      const json = await res.json();

      if (!res.ok || !json.ok) {
        hideLoading();
        runButton.disabled = false;
        showStatus(`❌ Pipeline failed: ${json.msg || ''}`, true);
        return;
      }

      /* start live polling */
      await pollStatusAndLoadBrands();
      /* runButton re‑enabled by poll loop */
    } catch (err) {
      hideLoading();
      runButton.disabled = false;
      showStatus(`❌ Pipeline error: ${err.message}`, true);
    }
  });
});
