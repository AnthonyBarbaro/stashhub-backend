// static/main.js

document.addEventListener("DOMContentLoaded", () => {
  // ── Element refs ─────────────────────────────────────────────
  const loading      = document.getElementById("loading");
  const loadingMsg   = document.getElementById("loading-msg");
  const updateForm   = document.getElementById("update-form");
  const brandSection = document.getElementById("brand-section");
  const brandList    = document.getElementById("brand-list");
  const runForm      = document.getElementById("run-form");

  // ── Spinner helpers ───────────────────────────────────────────
  function showLoading(msg = "Loading…") {
    loadingMsg.textContent = msg;
    loading.classList.remove("hidden");
  }
  function hideLoading() {
    loading.classList.add("hidden");
  }

  // ── Load brands into the <select> ─────────────────────────────
  async function loadBrands() {
    const res = await fetch("/brands");
    if (!res.ok) throw new Error("Could not fetch brands");
    const brands = await res.json();

    brandList.innerHTML = "";
    brands.forEach(b => {
      const opt = document.createElement("option");
      opt.value = opt.textContent = b;
      brandList.appendChild(opt);
    });

    brandSection.classList.remove("hidden");
    runForm.classList.remove("hidden");
  }

  // ── “Update Files” handler ────────────────────────────────────
  updateForm.addEventListener("submit", async e => {
    e.preventDefault();
    showLoading("Running Selenium… this may take a minute");

    try {
      // 1) kick off scraping & await JSON { ok, msg }
      const res  = await fetch("/update-files", { method: "POST" });
      const json = await res.json();
      hideLoading();

      if (res.ok) {
        // only alert on success
        alert("✅ " + json.msg);
        // then load brands for step 2
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
    const brands = [...brandList.selectedOptions].map(o => o.value);

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
