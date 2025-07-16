// static/main.js

// ── Global DOM references (declared first so helpers can access them) ──
let loading, loadingMsg;

// ── Global helpers ─────────────────────────────────────────────
function showLoading(msg = "Loading…") {
  loadingMsg.textContent = msg;
  loading.classList.remove("hidden");
}
function hideLoading() {
  loading.classList.add("hidden");
}
function showStatus(msg, isError = false) {
  const el = document.getElementById("status-message");
  el.textContent = msg;
  el.className = `status-message visible ${isError ? "error" : "success"}`;
}
function clearStatus() {
  const el = document.getElementById("status-message");
  el.textContent = "";
  el.className = "status-message";
}
async function pollStatusAndLoadBrands() {
  let last = "";
  while (true) {
    const res = await fetch("/status");
    const txt = await res.text();
    if (txt !== last) {
      showStatus(txt, txt.startsWith("❌"));
      last = txt;
    }
    if (txt.startsWith("✅ All stores") || txt.startsWith("❌")) {
      hideLoading();
      if (txt.startsWith("✅")) await loadBrands();
      break;
    }
    await new Promise(r => setTimeout(r, 2000));
  }
}

// ── Main entrypoint ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // ✅ Assign global DOM references now that DOM is loaded
  loading      = document.getElementById("loading");
  loadingMsg   = document.getElementById("loading-msg");
  const updateForm   = document.getElementById("update-form");
  const brandSection = document.getElementById("brand-section");
  const brandList    = document.getElementById("brand-list");
  const runForm      = document.getElementById("run-form");

  const brandPicker = new Choices(brandList, {
    removeItemButton: true,
    placeholderValue: 'Type to search brands',
    searchPlaceholderValue: 'Filter brands…',
    shouldSort: false,
    duplicateItemsAllowed: false,
  });

  async function loadBrands() {
    try {
      const res = await fetch("/brands");
      if (!res.ok) throw new Error("Could not fetch brands");
      const brands = await res.json();

      if (!Array.isArray(brands) || brands.length === 0) {
        showStatus("❌ No brands found in CSV folder.", true);
        return;
      }

      brandPicker.clearChoices();
      brandPicker.setChoices(
        brands.map(b => ({ value: b, label: b })),
        'value',
        'label',
        true
      );

      brandSection.classList.remove("hidden");
      runForm.classList.remove("hidden");
    } catch (err) {
      showStatus("❌ Failed to load brands: " + err.message, true);
    }
  }

  // Try loading brands immediately (if already downloaded)
  loadBrands();

  updateForm.addEventListener("submit", async e => {
    e.preventDefault();
    clearStatus();
    showLoading("Running Selenium… this may take a minute");

    try {
      const res = await fetch("/update-files", { method: "POST" });
      const json = await res.json();

      if (!res.ok || !json.ok) {
        hideLoading();
        showStatus("❌ Catalog scrape failed: " + (json.msg || ""), true);
        return;
      }

      pollStatusAndLoadBrands();
    } catch (err) {
      hideLoading();
      showStatus("❌ Network error: " + err.message, true);
    }
  });
  document.getElementById("select-all-brands").addEventListener("click", () => {
    const allValues = Array.from(brandList.options).map(opt => opt.value);
    brandPicker.setChoiceByValue(allValues);
  });
  
  document.getElementById("clear-all-brands").addEventListener("click", () => {
    brandPicker.removeActiveItems();
  });
  runForm.addEventListener("submit", async e => {
    e.preventDefault(); 
    console.log("Submitting run form...");
    const emails = document.getElementById("emails").value.trim();
    const brands = brandPicker.getValue(true); // returns list of selected brand values

    if (!emails) {
      showStatus("❌ Please enter at least one email.", true);
      return;
    }
    if (!brands.length) {
      showStatus("❌ Please select at least one brand.", true);
      return;
    }

    showLoading("Generating reports & sending email…");

    try {
      const res = await fetch("/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emails, brands })
      });
      const json = await res.json();
      hideLoading();

      if (json.ok) {
        showStatus("✅ " + json.msg);
      } else {
        showStatus("❌ " + json.msg, true);
      }
    } catch (err) {
      hideLoading();
      showStatus("❌ Pipeline error: " + err.message, true);
    }
  });
});
