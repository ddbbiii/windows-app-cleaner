const api = window.boostApi;

const panel = document.getElementById("panel");
const orb = document.getElementById("orb");
const orbCount = document.getElementById("orbCount");
const pinButton = document.getElementById("pinButton");
const subtitle = document.getElementById("subtitle");
const foregroundCount = document.getElementById("foregroundCount");
const backgroundCount = document.getElementById("backgroundCount");
const appList = document.getElementById("appList");
const emptyState = document.getElementById("emptyState");
const cleanForeground = document.getElementById("cleanForeground");
const cleanBackground = document.getElementById("cleanBackground");
const toast = document.getElementById("toast");

let latestState = null;
let isLoading = false;
let isRefreshing = false;
let dragState = null;
let ignoreNextOrbClick = false;

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

function beginDrag(event) {
  if (event.button !== 0) return;
  if (event.currentTarget.setPointerCapture && event.pointerId !== undefined) {
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  dragState = {
    startX: event.clientX,
    startY: event.clientY,
    moved: false,
  };
  api.dragStart();
  window.addEventListener("pointermove", updateDrag);
  window.addEventListener("pointerup", endDrag, { once: true });
  window.addEventListener("pointercancel", endDrag, { once: true });
  window.addEventListener("blur", endDrag, { once: true });
}

function updateDrag(event) {
  if (!dragState) return;
  const deltaX = event.clientX - dragState.startX;
  const deltaY = event.clientY - dragState.startY;
  if (Math.hypot(deltaX, deltaY) > 4) {
    dragState.moved = true;
  }
  api.dragMove();
}

function endDrag() {
  if (!dragState) return;
  ignoreNextOrbClick = dragState.moved;
  dragState = null;
  api.dragEnd();
  window.removeEventListener("pointermove", updateDrag);
  window.removeEventListener("blur", endDrag);
}

function setLoading(nextLoading) {
  isLoading = nextLoading;
  document.body.classList.toggle("loading", nextLoading);
  cleanForeground.disabled = nextLoading;
  cleanBackground.disabled = nextLoading;
}

function fallbackIcon(processName) {
  const letter = (processName || "?").replace(".exe", "").slice(0, 1).toUpperCase();
  return `<span class="fallback-icon">${letter}</span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function rowTemplate(item, index) {
  const stateClass = item.scope === "background" ? "background" : "foreground";
  const allowClass = item.allowed ? "allowed" : "";
  const icon = item.iconDataUrl
    ? `<img src="${item.iconDataUrl}" alt="" />`
    : fallbackIcon(item.processName);
  const displayName = item.processName || item.displayTitle;
  return `
    <div class="app-row ${allowClass}" data-index="${index}" title="${escapeHtml(item.displayTitle || displayName)}">
      <span class="app-icon">${icon}</span>
      <span class="state-pill ${stateClass}">${escapeHtml(item.state)}</span>
      <button class="row-action clean-one" data-action="clean" type="button" aria-label="立即清理 ${escapeHtml(displayName)}">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M13.2 2.2 4.8 13.4h6.1l-1.2 8.4 9.5-12.5h-6.3l.3-7.1Z" fill="currentColor"/>
        </svg>
      </button>
      <button class="row-action pin-one ${allowClass}" data-action="pin" type="button" aria-label="切换保留 ${escapeHtml(displayName)}">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M15.8 3.4 20.6 8.2l-2.5 2.5 1.5 1.5-1.5 1.5-3.1-3.1-4.6 4.6.4 3.4-1.4 1.4-3.2-5.3-5.3-3.2 1.4-1.4 3.4.4 4.6-4.6-3.1-3.1 1.5-1.5 1.5 1.5 2.5-2.5Z" fill="currentColor"/>
        </svg>
      </button>
    </div>
  `;
}

function render(state) {
  latestState = state;
  const counts = state.counts || {};
  const apps = state.apps || [];
  foregroundCount.textContent = counts.foreground ?? 0;
  backgroundCount.textContent = counts.background ?? 0;
  orbCount.textContent = counts.cleanable ?? 0;
  subtitle.textContent = `可清理 ${counts.cleanable ?? 0} | 前台 ${counts.foreground ?? 0} | 后台 ${counts.background ?? 0}`;
  emptyState.classList.toggle("visible", apps.length === 0);
  appList.innerHTML = apps.map(rowTemplate).join("");
}

async function refresh(silent = false) {
  if (isLoading || isRefreshing) return;
  isRefreshing = true;
  if (!silent) {
    setLoading(true);
  }
  try {
    const state = await api.getState();
    render(state);
    if (!silent && state.message) showToast(state.message);
  } catch (error) {
    if (!silent) {
      showToast(error.message || "读取应用失败");
    }
  } finally {
    isRefreshing = false;
    if (!silent) {
      setLoading(false);
    }
  }
}

async function toggleProcess(processName) {
  if (!processName || isLoading) return;
  setLoading(true);
  try {
    const state = await api.toggleAllow(processName);
    render(state);
    showToast(state.message || "已更新保留规则");
  } catch (error) {
    showToast(error.message || "保留规则更新失败");
  } finally {
    setLoading(false);
  }
}

async function closeApp(processName, scope) {
  if (!processName || isLoading) return;
  setLoading(true);
  try {
    const state = await api.closeApp(processName, scope);
    render(state);
    const attempted = state.result?.attemptedWindows ?? 0;
    const failed = state.result?.failures?.length ?? 0;
    showToast(`已请求关闭 ${attempted} 个窗口${failed ? `，失败 ${failed}` : ""}`);
  } catch (error) {
    showToast(error.message || "关闭应用失败");
  } finally {
    setLoading(false);
  }
}

async function clean(scope) {
  if (isLoading) return;
  setLoading(true);
  panel.classList.add("boosting");
  try {
    const state = await api.clean(scope);
    render(state);
    const attempted = state.result?.attemptedWindows ?? 0;
    const failed = state.result?.failures?.length ?? 0;
    showToast(`已发送关闭请求 ${attempted} 个窗口${failed ? `，失败 ${failed}` : ""}`);
  } catch (error) {
    showToast(error.message || "清理失败");
  } finally {
    window.setTimeout(() => panel.classList.remove("boosting"), 720);
    setLoading(false);
  }
}

appList.addEventListener("click", (event) => {
  const action = event.target.closest(".row-action");
  if (!action) return;
  const row = action.closest(".app-row");
  if (!row) return;
  const index = Number(row.dataset.index);
  const item = latestState?.apps?.[index];
  const processName = item?.processName;
  if (action.dataset.action === "clean") {
    closeApp(processName, item?.scope || "all");
  } else if (action.dataset.action === "pin") {
    toggleProcess(processName);
  }
});

orb.addEventListener("click", async () => {
  if (ignoreNextOrbClick) {
    ignoreNextOrbClick = false;
    return;
  }
  await api.expand();
  refresh(true);
});
orb.addEventListener("pointerdown", beginDrag);

panel.querySelector(".titlebar").addEventListener("pointerdown", (event) => {
  if (event.target.closest("button")) return;
  beginDrag(event);
});

pinButton.addEventListener("click", async () => {
  const mode = await api.togglePin();
  pinButton.classList.toggle("pinned", mode.pinned);
  showToast(mode.pinned ? "已置顶" : "已取消置顶，失焦后收起");
});

window.addEventListener("blur", () => {
  if (!dragState) {
    api.collapse();
  }
});

cleanForeground.addEventListener("click", () => clean("foreground"));
cleanBackground.addEventListener("click", () => clean("background"));

api.onPanelMode((mode) => {
  document.body.classList.toggle("collapsed", !mode.expanded);
  pinButton.classList.toggle("pinned", mode.pinned);
});

refresh(true);
window.setInterval(() => refresh(true), 5000);
