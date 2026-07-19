const { app, BrowserWindow } = require("electron");
const path = require("node:path");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");

// Handle Squirrel.Windows install/update events quickly.
if (require("electron-squirrel-startup")) {
  app.quit();
}

let backendProcess = null;
const API_PORT = Number(process.env.LOCALCODER_API_PORT || 8000);
const API_HOST = process.env.LOCALCODER_API_HOST || "127.0.0.1";

function backendBinaryPath() {
  const exeName =
    process.platform === "win32" ? "localcoder-api.exe" : "localcoder-api";

  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend", exeName);
  }

  return path.join(__dirname, "..", "resources", "backend", exeName);
}

function waitForApi(timeoutMs = 45000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(
        `http://${API_HOST}:${API_PORT}/health`,
        (res) => {
          res.resume();
          if (res.statusCode && res.statusCode < 500) {
            resolve();
            return;
          }
          retry();
        }
      );
      req.on("error", retry);
      req.setTimeout(2000, () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      if (Date.now() - started > timeoutMs) {
        reject(new Error("Timed out waiting for Localcoder API to start."));
        return;
      }
      setTimeout(attempt, 400);
    };

    attempt();
  });
}

function startBackend() {
  const binary = backendBinaryPath();
  if (!fs.existsSync(binary)) {
    console.warn(
      `Backend binary not found at ${binary}. ` +
        "Start the API manually with: uvicorn api:app --host 127.0.0.1 --port 8000"
    );
    return null;
  }

  const child = spawn(binary, [], {
    env: {
      ...process.env,
      LOCALCODER_API_HOST: API_HOST,
      LOCALCODER_API_PORT: String(API_PORT),
    },
    stdio: "ignore",
    windowsHide: true,
  });

  child.on("error", (err) => {
    console.error("Failed to start backend:", err);
  });

  child.on("exit", (code, signal) => {
    console.log(`Backend exited code=${code} signal=${signal}`);
    if (backendProcess === child) {
      backendProcess = null;
    }
  });

  return child;
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) return;
  try {
    if (process.platform === "win32") {
      spawn("taskkill", ["/pid", String(backendProcess.pid), "/f", "/t"]);
    } else {
      backendProcess.kill("SIGTERM");
    }
  } catch (err) {
    console.error("Failed to stop backend:", err);
  }
  backendProcess = null;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    title: "Localcoder",
    webPreferences: {
      preload: path.join(__dirname, "..", "preload", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (!app.isPackaged) {
    win.loadURL("http://localhost:5173");
  } else {
    win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

app.whenReady().then(async () => {
  backendProcess = startBackend();
  try {
    await waitForApi();
  } catch (err) {
    console.warn(String(err));
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("before-quit", () => {
  stopBackend();
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});
