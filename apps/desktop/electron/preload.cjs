const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("autoreview", {
  selectDirectory: () => ipcRenderer.invoke("dialog:selectDirectory"),
  selectFiles: () => ipcRenderer.invoke("dialog:selectFiles"),
  openPath: (targetPath) => ipcRenderer.invoke("shell:openPath", targetPath),
  backendUrl: () => ipcRenderer.invoke("backend:url")
});
