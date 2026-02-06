import { spawn, type ChildProcess } from "child_process";
import fs from "fs";
import path from "path";
import { app } from "electron";

const DEFAULT_PORT = 8000;
const HEALTH_ENDPOINT = "/api/health";

export type BackendHandle = {
  process: ChildProcess;
  port: number;
  baseUrl: string;
};

type StartOptions = {
  dataDir: string;
  port?: number;
  isPackaged: boolean;
};

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const resolveBackendCommand = (
  options: StartOptions
): { command: string; args: string[]; cwd?: string; env: NodeJS.ProcessEnv } => {
  const port = options.port ?? DEFAULT_PORT;
  const env = {
    ...process.env,
    ADHD_DATA_DIR: options.dataDir,
    PYTHONUNBUFFERED: "1",
  };

  if (options.isPackaged) {
    const resourcesPath = process.resourcesPath;
    const exeName = process.platform === "win32" ? "adhd-backend.exe" : "adhd-backend";
    const backendPath = path.join(resourcesPath, "backend", exeName);
    if (!fs.existsSync(backendPath)) {
      throw new Error(`Backend executable not found at ${backendPath}`);
    }
    return {
      command: backendPath,
      args: ["--host", "127.0.0.1", "--port", String(port), "--data-dir", options.dataDir],
      env,
    };
  }

  const projectRoot = app.getAppPath();
  const backendDir = path.join(projectRoot, "backend");
  const pythonBin =
    process.env.PYTHON_BIN ||
    (process.platform === "win32" ? "python" : "python3");

  return {
    command: pythonBin,
    args: [
      "-m",
      "uvicorn",
      "server:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
      "--reload",
    ],
    cwd: backendDir,
    env,
  };
};

export const startBackend = (options: StartOptions): BackendHandle => {
  const port = options.port ?? DEFAULT_PORT;
  const baseUrl = `http://127.0.0.1:${port}`;
  const { command, args, cwd, env } = resolveBackendCommand(options);
  const child = spawn(command, args, {
    cwd,
    env,
    stdio: options.isPackaged ? "ignore" : "inherit",
  });

  child.on("error", (error) => {
    console.error("Backend process failed to start:", error);
  });

  child.on("exit", (code, signal) => {
    if (options.isPackaged) return;
    console.log(`Backend exited (code=${code}, signal=${signal})`);
  });

  return { process: child, port, baseUrl };
};

export const waitForBackendReady = async (
  baseUrl: string,
  timeoutMs = 15000,
  intervalMs = 500
): Promise<boolean> => {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${baseUrl}${HEALTH_ENDPOINT}`, {
        cache: "no-store",
      });
      if (res.ok) return true;
    } catch {
      // Ignore until timeout.
    }
    await sleep(intervalMs);
  }
  return false;
};

export const stopBackend = async (handle: BackendHandle | null): Promise<void> => {
  if (!handle?.process || handle.process.killed) return;

  handle.process.kill("SIGTERM");
  const exitPromise = new Promise<void>((resolve) => {
    handle.process.once("exit", () => resolve());
  });
  const timeoutPromise = sleep(4000);
  await Promise.race([exitPromise, timeoutPromise]);

  if (!handle.process.killed) {
    handle.process.kill("SIGKILL");
  }
};
