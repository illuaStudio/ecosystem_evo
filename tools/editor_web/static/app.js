const API = "";

let kind = "species";
let catalog = { species: [], object_types: [] };
let currentId = null;
let dirty = false;

const els = {
  tabs: document.querySelectorAll(".tab"),
  search: document.getElementById("search"),
  catalog: document.getElementById("catalog"),
  empty: document.getElementById("empty"),
  panel: document.getElementById("panel"),
  title: document.getElementById("item-title"),
  path: document.getElementById("item-path"),
  editor: document.getElementById("json-editor"),
  mapSelection: document.getElementById("map-selection"),
  validate: document.getElementById("btn-validate"),
  save: document.getElementById("btn-save"),
  reload: document.getElementById("btn-reload"),
  newItem: document.getElementById("btn-new"),
  deleteItem: document.getElementById("btn-delete"),
  sidebarStatus: document.getElementById("sidebar-status"),
  message: document.getElementById("message"),
  errors: document.getElementById("errors"),
};

function resourcePath(id) {
  if (kind === "species") {
    return `/api/v1/species/${encodeURIComponent(id)}`;
  }
  return `/api/v1/object-types/${encodeURIComponent(id)}`;
}

function validatePath(id) {
  if (kind === "species") {
    return `/api/v1/species/${encodeURIComponent(id)}/validate`;
  }
  return `/api/v1/object-types/${encodeURIComponent(id)}/validate`;
}

function configPathLabel(id) {
  if (kind === "species") {
    return `config/game/species/${id}.json`;
  }
  return `config/game/object_types/${id}.json`;
}

function showSidebarStatus(text, ok) {
  if (!els.sidebarStatus) return;
  els.sidebarStatus.textContent = text || "";
  els.sidebarStatus.className = "sidebar-status" + (text ? (ok ? " ok" : " err") : "");
}

function showMessage(text, ok) {
  showSidebarStatus(text, ok);
  if (!els.message) return;
  els.message.hidden = false;
  els.message.textContent = text;
  els.message.className = "message " + (ok ? "ok" : "err");
}

function hideMessage() {
  showSidebarStatus("", true);
  if (els.message) els.message.hidden = true;
  if (els.errors) els.errors.hidden = true;
}

function showErrors(list) {
  els.errors.hidden = !list.length;
  els.errors.innerHTML = list.map((e) => `<li>${escapeHtml(e)}</li>`).join("");
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function parseEditorJson() {
  try {
    return { ok: true, data: JSON.parse(els.editor.value) };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

async function fetchJson(url, options = {}) {
  const init = {
    headers: { "Content-Type": "application/json" },
    ...options,
  };
  if (init.body !== undefined && typeof init.body !== "string") {
    init.body = JSON.stringify(init.body);
  }
  const res = await fetch(API + url, init);
  const text = await res.text();
  let body = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text };
    }
  }
  if (!res.ok) {
    const detail = body.detail || body.errors || res.statusText;
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail)
    );
  }
  return body;
}

async function loadCatalog() {
  catalog = await fetchJson("/api/v1/catalog");
  renderCatalog();
}

function filteredItems() {
  const items = catalog[kind] || [];
  const q = els.search.value.trim().toLowerCase();
  if (!q) return items;
  return items.filter(
    (it) =>
      it.id.toLowerCase().includes(q) ||
      (it.label && it.label.toLowerCase().includes(q)) ||
      (it.summary && it.summary.toLowerCase().includes(q))
  );
}

function renderCatalog() {
  const items = filteredItems();
  els.catalog.innerHTML = items
    .map(
      (it) => `
    <li>
      <button type="button" data-id="${escapeHtml(it.id)}" class="${it.id === currentId ? "active" : ""}">
        ${escapeHtml(it.label || it.id)}
        <span class="summary">${escapeHtml(it.summary || "")}</span>
      </button>
    </li>`
    )
    .join("");

  els.catalog.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => selectItem(btn.dataset.id));
  });
}

function scrollCatalogToActive() {
  const btn = els.catalog.querySelector("button.active");
  if (btn) btn.scrollIntoView({ block: "nearest" });
}

async function openItem(id) {
  currentId = id;
  dirty = false;
  els.search.value = "";
  await loadCatalog();
  renderCatalog();
  await loadItem(id);
  scrollCatalogToActive();
}

async function selectItem(id) {
  if (dirty && !confirm("未保存の変更があります。破棄してよいですか？")) {
    return;
  }
  await openItem(id);
}

async function loadItem(id) {
  hideMessage();
  const data = await fetchJson(resourcePath(id));
  els.empty.classList.add("hidden");
  els.panel.classList.remove("hidden");
  els.title.textContent = id;
  els.path.textContent = configPathLabel(id);
  els.editor.value = JSON.stringify(data, null, 2);
}

async function refreshMapSelection() {
  try {
    const sel = await fetchJson("/api/v1/map/selection");
    if (!sel || sel.uid == null) {
      els.mapSelection.textContent = "（未選択）";
      return;
    }
    els.mapSelection.textContent = JSON.stringify(sel, null, 2);
  } catch {
    els.mapSelection.textContent = "（マップエディタ未接続）";
  }
}

async function onValidate() {
  hideMessage();
  const parsed = parseEditorJson();
  if (!parsed.ok) {
    showMessage("JSON の構文エラー: " + parsed.error, false);
    return;
  }
  const result = await fetchJson(validatePath(currentId), {
    method: "POST",
    body: JSON.stringify(parsed.data),
  });
  if (result.ok) {
    showMessage("検証 OK", true);
    showErrors([]);
  } else {
    showMessage("検証エラー", false);
    showErrors(result.errors || []);
  }
}

async function onSave() {
  hideMessage();
  const parsed = parseEditorJson();
  if (!parsed.ok) {
    showMessage("JSON の構文エラー: " + parsed.error, false);
    return;
  }
  const result = await fetchJson(resourcePath(currentId), {
    method: "PUT",
    body: parsed.data,
  });
  if (!result.ok) {
    showMessage("保存できませんでした", false);
    showErrors(result.errors || []);
    return;
  }
  dirty = false;
  showMessage("保存しました", true);
  showErrors([]);
  await loadCatalog();
}

async function onReload() {
  if (!currentId) return;
  if (dirty && !confirm("未保存の変更を破棄して再読込しますか？")) {
    return;
  }
  dirty = false;
  await loadItem(currentId);
  showMessage("再読込しました", true);
}

function newItemPromptLabel() {
  if (kind === "species") {
    return "種族 ID（name、ファイル名にもなります）\n例: my_ant";
  }
  return "オブジェクト型 ID（ファイル名にもなります）\n例: my_rock";
}

function errorsIncludeAlreadyExists(errors) {
  return (errors || []).some((e) => /already exists/i.test(e));
}

async function onNew() {
  const id = prompt(newItemPromptLabel())?.trim();
  if (!id) return;
  showSidebarStatus("作成中…", true);
  try {
    const result = await fetchJson(resourcePath(id), {
      method: "POST",
      body: {},
    });
    if (!result.ok) {
      if (errorsIncludeAlreadyExists(result.errors)) {
        await openItem(id);
        showMessage(`「${id}」は既にあります。開きました。`, true);
        showErrors([]);
        return;
      }
      showMessage("作成できませんでした", false);
      showErrors(result.errors || []);
      return;
    }
    await openItem(id);
    showMessage(`「${id}」を作成しました（テンプレート）`, true);
    showErrors([]);
  } catch (e) {
    const msg = e.message || String(e);
    showMessage("エラー: " + msg, false);
    console.error("onNew failed", e);
  }
}

async function onDelete() {
  if (!currentId) return;
  const path = configPathLabel(currentId);
  if (
    !confirm(
      `「${currentId}」を削除しますか？\n${path}\nこの操作は元に戻せません。`
    )
  ) {
    return;
  }
  showSidebarStatus("削除中…", true);
  try {
    const result = await fetchJson(resourcePath(currentId), {
      method: "DELETE",
    });
    if (!result.ok) {
      showMessage("削除できませんでした", false);
      showErrors(result.errors || []);
      return;
    }
    currentId = null;
    dirty = false;
    els.panel.classList.add("hidden");
    els.empty.classList.remove("hidden");
    await loadCatalog();
    showMessage("削除しました", true);
    showErrors([]);
  } catch (e) {
    showMessage(String(e.message), false);
  }
}

els.tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    const next = tab.dataset.kind;
    if (next === kind) return;
    if (dirty && !confirm("未保存の変更があります。タブを切り替えますか？")) {
      return;
    }
    kind = next;
    currentId = null;
    dirty = false;
    els.tabs.forEach((t) => t.classList.toggle("active", t === tab));
    els.empty.classList.remove("hidden");
    els.panel.classList.add("hidden");
    renderCatalog();
  });
});

els.search.addEventListener("input", renderCatalog);
els.editor.addEventListener("input", () => {
  dirty = true;
});
els.validate.addEventListener("click", () => currentId && onValidate());
els.save.addEventListener("click", () => currentId && onSave());
els.reload.addEventListener("click", onReload);
els.newItem.addEventListener("click", onNew);
els.deleteItem.addEventListener("click", () => currentId && onDelete());

async function checkApiVersion() {
  try {
    const health = await fetchJson("/api/health");
    const ver = health.api_version || 0;
    const features = health.features || [];
    const ok =
      ver >= 2 || (features.includes("create") && features.includes("delete"));
    if (!ok) {
      showSidebarStatus(
        "古い API です。run_dev_editor.py を再起動してください（ポート競合の可能性）",
        false
      );
      return false;
    }
    return true;
  } catch (e) {
    showSidebarStatus("API に接続できません: " + e.message, false);
    return false;
  }
}

checkApiVersion().then((ok) => {
  if (ok) loadCatalog().catch((e) => showMessage("一覧の読込失敗: " + e.message, false));
});
setInterval(refreshMapSelection, 1500);
refreshMapSelection();
