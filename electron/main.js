const { app, BrowserWindow, ipcMain, screen } = require("electron");
const { execFile } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const APP_ROOT = process.env.APP_CLEANER_ROOT || path.resolve(__dirname, "..");
const COLLAPSED_SIZE = { width: 108, height: 108 };
const EXPANDED_SIZE = { width: 430, height: 650 };

let win;
let isExpanded = false;
let isPinned = false;
let dragSession = null;
let dragTimer = null;
let collapseCheckTimer = null;
const iconCache = new Map();

function pythonExe() {
  if (process.env.APP_CLEANER_PYTHON) return process.env.APP_CLEANER_PYTHON;
  const bundled = "E:\\program\\language\\python\\Python-3.11.0\\python.exe";
  if (fs.existsSync(bundled)) return bundled;
  return "python";
}

function runBridge(args) {
  return new Promise((resolve, reject) => {
    execFile(
      pythonExe(),
      ["-m", "app_cleaner.bridge", ...args],
      {
        cwd: APP_ROOT,
        windowsHide: true,
        env: {
          ...process.env,
          PYTHONUTF8: "1",
          PYTHONIOENCODING: "utf-8",
        },
        maxBuffer: 1024 * 1024 * 4,
      },
      (error, stdout, stderr) => {
        const text = String(stdout || "").trim();
        try {
          const payload = JSON.parse(text);
          if (!payload.ok && error) {
            reject(new Error(payload.error || stderr || error.message));
            return;
          }
          resolve(payload);
        } catch (parseError) {
          reject(new Error(stderr || error?.message || parseError.message));
        }
      },
    );
  });
}

async function enrichIcons(payload) {
  if (!payload?.apps) return payload;
  await Promise.all(
    payload.apps.map(async (item) => {
      if (!item.exePath) return;
      if (iconCache.has(item.exePath)) {
        item.iconDataUrl = iconCache.get(item.exePath);
        return;
      }
      try {
        const image = await app.getFileIcon(item.exePath, { size: "normal" });
        const dataUrl = image.toDataURL();
        iconCache.set(item.exePath, dataUrl);
        item.iconDataUrl = dataUrl;
      } catch {
        iconCache.set(item.exePath, "");
      }
    }),
  );
  return payload;
}

function placeInitialWindow() {
  const display = screen.getPrimaryDisplay().workArea;
  const x = display.x + Math.max(24, display.width - COLLAPSED_SIZE.width - 56);
  const y = display.y + Math.max(24, Math.round(display.height * 0.16));
  win.setBounds(clampWindowBounds(x, y, COLLAPSED_SIZE.width, COLLAPSED_SIZE.height), false);
}

function setExpanded(nextExpanded) {
  if (!win || isExpanded === nextExpanded) return;
  const bounds = win.getBounds();
  isExpanded = nextExpanded;
  const nextSize = nextExpanded ? EXPANDED_SIZE : COLLAPSED_SIZE;
  const nextX = nextExpanded
    ? bounds.x - EXPANDED_SIZE.width + COLLAPSED_SIZE.width + 16
    : bounds.x + EXPANDED_SIZE.width - COLLAPSED_SIZE.width - 16;
  const nextY = nextExpanded ? bounds.y - 216 : bounds.y + 216;
  win.setBounds(clampWindowBounds(nextX, nextY, nextSize.width, nextSize.height), true);
  win.webContents.send("panel-mode", { expanded: isExpanded, pinned: isPinned });
}

function collapseIfUnpinned() {
  if (!win || isPinned || dragSession || !isExpanded) return;
  setExpanded(false);
}

function displayForBounds(x, y, width, height) {
  return screen.getDisplayMatching({ x, y, width, height }).workArea;
}

function displayForPoint(point) {
  return screen.getDisplayNearestPoint({
    x: Math.round(Number(point?.x) || 0),
    y: Math.round(Number(point?.y) || 0),
  }).workArea;
}

function clampWindowBounds(x, y, width, height, area = displayForBounds(x, y, width, height)) {
  const maxX = area.x + Math.max(0, area.width - width);
  const maxY = area.y + Math.max(0, area.height - height);
  return {
    x: Math.min(Math.max(x, area.x), maxX),
    y: Math.min(Math.max(y, area.y), maxY),
    width,
    height,
  };
}

function stopDrag() {
  dragSession = null;
  if (dragTimer !== null) {
    clearInterval(dragTimer);
    dragTimer = null;
  }
}

function moveDraggedWindow() {
  if (!win || !dragSession) return;
  const cursor = screen.getCursorScreenPoint();
  const x = cursor.x - dragSession.offsetX;
  const y = cursor.y - dragSession.offsetY;
  const clamped = clampWindowBounds(
    x,
    y,
    dragSession.bounds.width,
    dragSession.bounds.height,
    displayForPoint(cursor),
  );
  win.setPosition(clamped.x, clamped.y, false);
}

function createWindow() {
  win = new BrowserWindow({
    ...COLLAPSED_SIZE,
    frame: false,
    transparent: true,
    show: false,
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    hasShadow: false,
    backgroundColor: "#00000000",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, "index.html"));
  placeInitialWindow();
  win.once("ready-to-show", () => {
    isExpanded = false;
    win.show();
    win.webContents.send("panel-mode", { expanded: false, pinned: isPinned });
  });
  win.on("blur", collapseIfUnpinned);
  win.webContents.on("blur", collapseIfUnpinned);
  collapseCheckTimer = setInterval(() => {
    if (!win || isPinned || dragSession || !isExpanded) return;
    if (!win.isFocused() && !win.webContents.isFocused()) {
      setExpanded(false);
    }
  }, 350);
}

ipcMain.handle("state", async () => enrichIcons(await runBridge(["state"])));
ipcMain.handle("toggle", async (_event, processName) => enrichIcons(await runBridge(["toggle", processName])));
ipcMain.handle("clean", async (_event, scope) => enrichIcons(await runBridge(["clean", scope])));
ipcMain.handle("close-app", async (_event, processName, scope = "all") => {
  return enrichIcons(await runBridge(["close-app", processName, scope]));
});
ipcMain.handle("expand", () => {
  setExpanded(true);
  if (win) {
    win.show();
    win.focus();
  }
  return { expanded: isExpanded, pinned: isPinned };
});
ipcMain.handle("collapse", () => {
  collapseIfUnpinned();
  return { expanded: isExpanded, pinned: isPinned };
});
ipcMain.handle("toggle-pin", () => {
  isPinned = !isPinned;
  win.setAlwaysOnTop(true, "floating");
  win.webContents.send("panel-mode", { expanded: isExpanded, pinned: isPinned });
  return { expanded: isExpanded, pinned: isPinned };
});
ipcMain.on("drag-start", () => {
  if (!win) return;
  stopDrag();
  const cursor = screen.getCursorScreenPoint();
  const bounds = win.getBounds();
  dragSession = {
    offsetX: cursor.x - bounds.x,
    offsetY: cursor.y - bounds.y,
    bounds,
  };
  moveDraggedWindow();
  dragTimer = setInterval(moveDraggedWindow, 16);
});
ipcMain.on("drag-move", () => {
  moveDraggedWindow();
});
ipcMain.on("drag-end", () => {
  stopDrag();
});

app.whenReady().then(createWindow);

app.on("browser-window-blur", (_event, blurredWindow) => {
  if (blurredWindow === win) {
    collapseIfUnpinned();
  }
});

app.on("window-all-closed", () => {
  if (collapseCheckTimer !== null) {
    clearInterval(collapseCheckTimer);
    collapseCheckTimer = null;
  }
  if (process.platform !== "darwin") app.quit();
});
