const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("boostApi", {
  getState: () => ipcRenderer.invoke("state"),
  toggleAllow: (processName) => ipcRenderer.invoke("toggle", processName),
  clean: (scope) => ipcRenderer.invoke("clean", scope),
  closeApp: (processName, scope) => ipcRenderer.invoke("close-app", processName, scope),
  expand: () => ipcRenderer.invoke("expand"),
  collapse: () => ipcRenderer.invoke("collapse"),
  togglePin: () => ipcRenderer.invoke("toggle-pin"),
  dragStart: () => ipcRenderer.send("drag-start"),
  dragMove: () => ipcRenderer.send("drag-move"),
  dragEnd: () => ipcRenderer.send("drag-end"),
  onPanelMode: (callback) => {
    ipcRenderer.on("panel-mode", (_event, payload) => callback(payload));
  },
});
