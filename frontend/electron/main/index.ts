import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from "electron";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync } from "node:fs";
import { realpath } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { ideConfiguration, launchOpenCode, parseOpenCodeInput } from "./open-code";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const isDevelopment = Boolean(process.env.VITE_DEV_SERVER_URL);
const backendHost = process.env.BOT_STUDIO_BACKEND_HOST ?? "127.0.0.1";
const backendPort = process.env.BOT_STUDIO_BACKEND_PORT ?? "8000";
const backendBaseUrl = `http://${backendHost}:${backendPort}`;

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcessWithoutNullStreams | null = null;
const approvedRoots = new Set<string>();

function backendDirectory(): string {
  if (process.env.BOT_STUDIO_BACKEND_DIR) {
    return path.resolve(process.env.BOT_STUDIO_BACKEND_DIR);
  }
  return path.resolve(app.getAppPath(), "..", "backend");
}

function pythonCommand(root: string): { executable: string; arguments: string[] } {
  if (process.env.BOT_STUDIO_PYTHON) {
    return { executable: process.env.BOT_STUDIO_PYTHON, arguments: [] };
  }

  const workspacePython = path.resolve(root, "..", ".venv", "Scripts", "python.exe");
  if (existsSync(workspacePython)) {
    return { executable: workspacePython, arguments: [] };
  }

  return process.platform === "win32"
    ? { executable: "py", arguments: ["-3.12"] }
    : { executable: "python3", arguments: [] };
}

function startBackend(): void {
  if (backendProcess || process.env.BOT_STUDIO_SKIP_BACKEND === "1") return;

  const root = backendDirectory();
  if (!existsSync(root)) {
    console.error(`[desktop] Backend directory does not exist: ${root}`);
    return;
  }

  const python = pythonCommand(root);
  backendProcess = spawn(
    python.executable,
    [
      ...python.arguments,
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      backendHost,
      "--port",
      backendPort,
    ],
    {
      cwd: root,
      env: { ...process.env, BOT_STUDIO_DESKTOP: "1" },
      windowsHide: true,
    },
  );

  backendProcess.stdout.on("data", (chunk: Buffer) => {
    console.info(`[backend] ${chunk.toString().trimEnd()}`);
  });
  backendProcess.stderr.on("data", (chunk: Buffer) => {
    console.error(`[backend] ${chunk.toString().trimEnd()}`);
  });
  backendProcess.on("error", (error) => {
    console.error(`[desktop] Could not start backend: ${error.message}`);
  });
  backendProcess.on("exit", (code, signal) => {
    console.info(`[desktop] Backend exited (code=${code ?? "none"}, signal=${signal ?? "none"})`);
    backendProcess = null;
  });
}

function stopBackend(): void {
  backendProcess?.kill();
  backendProcess = null;
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 760,
    minWidth: 800,
    minHeight: 560,
    backgroundColor: "#24282e",
    title: "Telegram Bot Studio",
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#00000000",
      symbolColor: "#c3ccd6",
      height: 42,
    },
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(currentDirectory, "index.mjs"),
    },
  });

  if (isDevelopment && process.env.VITE_DEV_SERVER_URL) {
    await mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    return;
  }

  await mainWindow.loadFile(path.join(currentDirectory, "../dist/index.html"));
}

ipcMain.handle("desktop:backend-info", () => ({ baseUrl: backendBaseUrl }));
ipcMain.handle("desktop:select-directory", async () => {
  const result = mainWindow
    ? await dialog.showOpenDialog(mainWindow, { properties: ["openDirectory", "createDirectory"] })
    : await dialog.showOpenDialog({ properties: ["openDirectory", "createDirectory"] });
  const selected = result.canceled ? null : result.filePaths[0] ?? null;
  if (!selected) return null;
  const canonical = await realpath(selected);
  approvedRoots.add(canonical);
  return canonical;
});
ipcMain.handle("desktop:open-code", async (_event, input: unknown) => {
  await launchOpenCode(parseOpenCodeInput(input), ideConfiguration(process.env), {
    openPath: (filePath) => shell.openPath(filePath),
    spawnProcess: (command, args, options) => spawn(command, args, options),
  }, approvedRoots);
});

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null);
  startBackend();
  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) await createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", stopBackend);
