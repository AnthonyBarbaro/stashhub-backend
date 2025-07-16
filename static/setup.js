document.addEventListener("DOMContentLoaded", () => {
    const tbody     = document.querySelector("#store-table tbody");
    const addRowBtn = document.getElementById("add-row");
    const saveBtn   = document.getElementById("save-setup");
    const msg       = document.getElementById("setup-msg");
  
    const addRow = (n = "", a = "") => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td><input value="${n}"></td>
                      <td><input value="${a}"></td>
                      <td><button class="del">✕</button></td>`;
      tbody.appendChild(tr);
      tr.querySelector(".del").onclick = () => tr.remove();
    };
    addRowBtn.onclick = () => addRow();
  
    saveBtn.onclick = async () => {
      msg.textContent = "";
      const username = document.getElementById("du-user").value.trim();
      const password = document.getElementById("du-pass").value.trim();
      const store_map = {};
      tbody.querySelectorAll("tr").forEach(tr => {
        const name = tr.cells[0].firstElementChild.value.trim();
        const abbr = tr.cells[1].firstElementChild.value.trim();
        if (name && abbr) store_map[name] = abbr;
      });
      const res = await fetch("/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, store_map })
      });
      const j = await res.json();
      msg.textContent = j.msg;
      if (j.ok) location.href = "/";
    };
  });
  