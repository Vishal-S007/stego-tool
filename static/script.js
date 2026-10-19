const $ = (id) => document.getElementById(id);

// ---- Tabs ----
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    $(t.dataset.tab).classList.add("active");
  });
});

// ---- Drag & drop helper ----
function wireDrop(dropEl, inputEl, onFile) {
  dropEl.addEventListener("click", () => inputEl.click());
  ["dragover", "dragenter"].forEach((e) =>
    dropEl.addEventListener(e, (ev) => { ev.preventDefault(); dropEl.classList.add("hover"); })
  );
  ["dragleave", "drop"].forEach((e) =>
    dropEl.addEventListener(e, (ev) => { ev.preventDefault(); dropEl.classList.remove("hover"); })
  );
  dropEl.addEventListener("drop", (ev) => {
    const file = ev.dataTransfer.files[0];
    if (file) { inputEl.files = ev.dataTransfer.files; onFile(file); }
  });
  inputEl.addEventListener("change", () => {
    if (inputEl.files[0]) onFile(inputEl.files[0]);
  });
}

function preview(dropEl, file) {
  const url = URL.createObjectURL(file);
  dropEl.innerHTML = `<img src="${url}" alt="preview">`;
}

// ================= ENCODE =================
let encCapacity = 0;

wireDrop($("encDrop"), $("encFile"), async (file) => {
  preview($("encDrop"), file);
  $("encBtn").disabled = false;
  $("encMeta").textContent = "Checking capacity...";

  const fd = new FormData();
  fd.append("image", file);
  try {
    const r = await fetch("/api/capacity", { method: "POST", body: fd });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    encCapacity = d.capacity_bytes;
    $("encMeta").textContent =
      `${d.width}×${d.height}px · capacity ≈ ${encCapacity.toLocaleString()} chars`;
    updateCounter();
  } catch (e) {
    $("encMeta").textContent = "⚠ " + e.message;
  }
});

function updateCounter() {
  const len = new TextEncoder().encode($("encMsg").value).length;
  const c = $("encCounter");
  c.textContent = `${len} / ${encCapacity} bytes`;
  c.classList.toggle("over", encCapacity > 0 && len > encCapacity);
}
$("encMsg").addEventListener("input", updateCounter);

$("encBtn").addEventListener("click", async () => {
  const file = $("encFile").files[0];
  const msg = $("encMsg").value;
  if (!file || !msg) return;

  const st = $("encStatus");
  st.className = "status work";
  st.textContent = "Embedding...";
  $("encBtn").disabled = true;

  const fd = new FormData();
  fd.append("image", file);
  fd.append("message", msg);
  fd.append("password", $("encPass").value);

  try {
    const r = await fetch("/api/encode", { method: "POST", body: fd });
    if (!r.ok) {
      const d = await r.json();
      throw new Error(d.error || "Encode failed");
    }
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "stego.png";
    a.click();
    st.className = "status ok";
    st.textContent = "✓ Downloaded stego.png" +
      ($("encPass").value ? " (AES-256 encrypted)" : "");
  } catch (e) {
    st.className = "status err";
    st.textContent = "✗ " + e.message;
  } finally {
    $("encBtn").disabled = false;
  }
});

// ================= DECODE =================
wireDrop($("decDrop"), $("decFile"), (file) => {
  preview($("decDrop"), file);
  $("decBtn").disabled = false;
});

$("decBtn").addEventListener("click", async () => {
  const file = $("decFile").files[0];
  if (!file) return;

  const st = $("decStatus");
  st.className = "status work";
  st.textContent = "Extracting...";
  $("decResult").hidden = true;
  $("decBtn").disabled = true;

  const fd = new FormData();
  fd.append("image", file);
  fd.append("password", $("decPass").value);

  try {
    const r = await fetch("/api/decode", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || "Decode failed");
    st.className = "status ok";
    st.textContent = "✓ Message recovered";
    $("decOut").textContent = d.message;
    $("decResult").hidden = false;
  } catch (e) {
    st.className = "status err";
    st.textContent = "✗ " + e.message;
  } finally {
    $("decBtn").disabled = false;
  }
});
