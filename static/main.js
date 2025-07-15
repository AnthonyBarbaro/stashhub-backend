// static/main.js

document.addEventListener("DOMContentLoaded", () => {
  // ── Element refs ─────────────────────────────────────────────
  const loading      = document.getElementById("loading");
  const loadingMsg   = document.getElementById("loading-msg");
  const updateForm   = document.getElementById("update-form");
  const brandSection = document.getElementById("brand-section");
  const brandList    = document.getElementById("brand-list");
  const runForm      = document.getElementById("run-form");

  // ── Initialize Choices on the multi-select ───────────────────
  const brandPicker = new Choices(brandList, {
    removeItemButton: true,
    placeholderValue: 'Type to search brands',
    searchPlaceholderValue: 'Filter brands…',
    shouldSort: false,            // keep server order
    duplicateItemsAllowed: false,
  });

  // ── Spinner helpers ───────────────────────────────────────────
  function showLoading(msg = "Loading…") {
    loadingMsg.textContent = msg;
    loading.classList.remove("hidden");
  }
  function hideLoading() {
    loading.classList.add("hidden");
  }

  // ── Load brands into the Choices instance ─────────────────────
  async function loadBrands() {
    const res = await fetch("/brands");
    if (!res.ok) throw new Error("Could not fetch brands");
    const brands = await res.json();

    // feed Choices a fresh list
    brandPicker.clearChoices();
    brandPicker.setChoices(
      brands.map(b => ({ value: b, label: b })),
      'value',
      'label',
      true
    );

    brandSection.classList.remove("hidden");
    runForm.classList.remove("hidden");
  }

  // ── “Update Files” handler ────────────────────────────────────
  updateForm.addEventListener("submit", async e => {
    e.preventDefault();
    showLoading("Running Selenium… this may take a minute");

    try {
      const res  = await fetch("/update-files", { method: "POST" });
      const json = await res.json();
      hideLoading();

      if (res.ok) {
        alert("✅ " + json.msg);
        await loadBrands();
      } else {
        console.error("Catalog scrape failed:", json.msg);
      }
    } catch (err) {
      hideLoading();
      console.error("Network error starting catalog scrape:", err);
    }
  });

  // ── “Run Pipeline” handler ────────────────────────────────────
  runForm.addEventListener("submit", async e => {
    e.preventDefault();

    const emails = document.getElementById("emails").value.trim();
    // get array of selected brand values
    const brands = brandPicker.getValue(true);

    if (!emails) {
      alert("Please enter at least one email address.");
      return;
    }
    if (!brands.length) {
      alert("Please select at least one brand.");
      return;
    }

    showLoading("Generating reports & sending email…");

    try {
      const res  = await fetch("/run", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ emails, brands })
      });
      const json = await res.json();
      hideLoading();

      if (json.ok) {
        alert("✅ " + json.msg);
      } else {
        console.error("Pipeline error:", json.msg);
      }
    } catch (err) {
      hideLoading();
      console.error("Pipeline network error:", err);
    }
  });
});
