const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

const BACKEND_URL = "http://127.0.0.1:8765";
let backendProcess = null;

function repoRoot() {
  return path.resolve(__dirname, "..", "..", "..");
}

function startBackend() {
  if (backendProcess) return;
  const args = [
    "-m",
    "uvicorn",
    "apps.backend.autoreview_backend.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8765"
  ];
  backendProcess = spawn("python", args, {
    cwd: repoRoot(),
    stdio: "ignore",
    windowsHide: true
  });
  backendProcess.on("exit", () => {
    backendProcess = null;
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1120,
    minHeight: 720,
    title: "AutoReview",
    backgroundColor: "#f5f5f5",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (app.isPackaged) {
    win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  } else {
    win.loadURL("http://127.0.0.1:5173");
  }
}

app.whenReady().then(() => {
  startBackend();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
});

ipcMain.handle("dialog:selectDirectory", async () => {
  const result = await dialog.showOpenDialog({ properties: ["openDirectory", "createDirectory"] });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle("dialog:selectFiles", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile", "multiSelections"],
    filters: [
      { name: "Review Inputs", extensions: ["pdf", "csv", "xlsx", "xlsm", "docx", "txt"] },
      { name: "All Files", extensions: ["*"] }
    ]
  });
  return result.canceled ? [] : result.filePaths;
});

ipcMain.handle("shell:openPath", async (_, targetPath) => {
  return shell.openPath(targetPath);
});

ipcMain.handle("backend:url", async () => BACKEND_URL);
