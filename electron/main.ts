import { app, BrowserWindow } from "electron";
import fs from "fs";
import path from "path";
import {
  startBackend,
  stopBackend,
  waitForBackendReady,
  type BackendHandle,
} from "./python-manager";

let mainWindow: BrowserWindow | null = null;
let backendHandle: BackendHandle | null = null;

const syncBundledEnvToDataDir = (dataDir: string) => {
  if (!app.isPackaged) return;

  const bundledEnvPath = path.join(process.resourcesPath, "config", "default.env");
  if (!fs.existsSync(bundledEnvPath)) {
    console.warn(`Bundled env file not found at ${bundledEnvPath}`);
    return;
  }

  const runtimeEnvPath = path.join(dataDir, ".env");
  try {
    // MVP behavior: always sync bundled env so end users can run without manual setup.
    fs.copyFileSync(bundledEnvPath, runtimeEnvPath);
  } catch (error) {
    console.error(`Failed to sync bundled env to ${runtimeEnvPath}:`, error);
  }
};

const buildFallbackHtml = (message: string, detail?: string) => {
  const safeDetail = detail ? `<pre>${detail}</pre>` : "";
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ADHD Timebox</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background: #f7f5f2; color: #2a2825; padding: 48px; }
      h1 { margin: 0 0 12px; font-size: 22px; }
      p { margin: 0 0 12px; }
      code { background: #eee8de; padding: 2px 6px; border-radius: 4px; }
      pre { background: #f0ece6; padding: 12px; border-radius: 8px; overflow: auto; }
    </style>
  </head>
  <body>
    <h1>Renderer not ready</h1>
    <p>${message}</p>
    ${safeDetail}
    <p>Dev quick fix: run <code>pnpm dev</code> then restart Electron.</p>
  </body>
</html>`;
};

const createWindow = async () => {
  const preloadPath = path.join(app.getAppPath(), "electron", "dist", "preload.js");
  const window = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const debugEnabled = process.env.ELECTRON_DEBUG === "1";
  if (debugEnabled) {
    window.webContents.openDevTools({ mode: "detach" });
  }

  window.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    const levelLabel = ["log", "warn", "error"][level] ?? String(level);
    console.log(`[renderer:${levelLabel}] ${message} (${sourceId}:${line})`);
  });

  window.webContents.on(
    "did-fail-load",
    (_event, errorCode, errorDescription, validatedURL) => {
      console.error(
        `Renderer failed to load ${validatedURL}: ${errorDescription} (${errorCode})`
      );
    }
  );

  window.webContents.on("render-process-gone", (_event, details) => {
    console.error("Renderer process gone:", details);
  });

  if (debugEnabled) {
    window.webContents.on("did-finish-load", async () => {
      try {
        const bodyText = await window.webContents.executeJavaScript(
          "document.body && document.body.innerText ? document.body.innerText.slice(0, 200) : ''"
        );
        console.log("[renderer] body text preview:", bodyText);
      } catch (error) {
        console.error("Failed to read renderer body text:", error);
      }
    });
  }

  const forceStatic = process.env.ELECTRON_STATIC === "1";

  try {
    if (app.isPackaged || forceStatic) {
      const indexPath = path.join(app.getAppPath(), "out", "index.html");
      await window.loadFile(indexPath);
    } else {
      await window.loadURL("http://localhost:3000");
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    const message = app.isPackaged
      ? "Static export not found. Run the build step before packaging."
      : "Next.js dev server is not reachable at http://localhost:3000.";
    const html = buildFallbackHtml(message, detail);
    await window.loadURL(`data:text/html,${encodeURIComponent(html)}`);
  }

  const forceShowTimer = setTimeout(() => {
    if (!window.isDestroyed() && !window.isVisible()) {
      window.show();
    }
  }, 2000);

  window.once("ready-to-show", () => {
    clearTimeout(forceShowTimer);
    window.show();
  });

  window.webContents.once("did-finish-load", () => {
    if (!window.isDestroyed() && !window.isVisible()) {
      window.show();
    }
  });

  window.on("closed", () => {
    mainWindow = null;
  });

  mainWindow = window;
};

const boot = async () => {
  const dataDir = path.join(app.getPath("userData"), "data");
  fs.mkdirSync(dataDir, { recursive: true });
  syncBundledEnvToDataDir(dataDir);

  backendHandle = startBackend({
    dataDir,
    isPackaged: app.isPackaged,
  });

  const isReady = await waitForBackendReady(backendHandle.baseUrl);
  if (!isReady) {
    console.error("Backend did not become ready in time.");
  }

  await createWindow();
};

app.whenReady().then(boot);

app.on("before-quit", async () => {
  await stopBackend(backendHandle);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
