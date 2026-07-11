import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const isDevelopment = Boolean(process.env.VITE_DEV_SERVER_URL);
const backendHost = process.env.BOT_STUDIO_BACKEND_HOST ?? "127.0.0.1";
const backendPort = process.env.BOT_STUDIO_BACKEND_PORT ?? "8000";
const backendBaseUrl = `http://${backendHost}:${backendPort}`;

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcessWithoutNullStreams | null = null;

function backendDirectory(): string {
  if (process.env.BOT_STUDIO_BACKEND_DIR) {
    return path.resolve(process.env.BOT_STUDIO_BACKEND_DIR);
  }
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : path.resolve(app.getAppPath(), "..", "backend");
}

function pythonExecutable(root: string): string {
  if (process.env.BOT_STUDIO_PYTHON) return process.env.BOT_STUDIO_PYTHON;
  const workspacePython = path.resolve(root, "..", ".venv", "Scripts", "python.exe");
  return existsSync(workspacePython) ? workspacePython : "python";
}

function startBackend(): void {
  if (process.env.BOT_STUDIO_SKIP_BACKEND === "1" || backendProcess) return;

  const root = backendDirectory();
  if (!existsSync(root)) {
    console.warn(`[desktop] Backend directory does not exist: ${root}`);
    return;
  }

  const modulePath = process.env.BOT_STUDIO_BACKEND_APP ?? "app.main:app";
  backendProcess = spawn(
    pythonExecutable(root),
    ["-m", "uvicorn", modulePath, "--host", backendHost, "--port", backendPort],
    {
      cwd: root,
      env: { ...process.env, BOT_STUDIO_DESKTOP: "1" },
      windowsHide: true,
    },
  );

  backendProcess.stdout.on("data", (chunk) => console.info(`[backend] ${chunk.toString().trimEnd()}`));
  backendProcess.stderr.on("data", (chunk) => console.error(`[backend] ${chunk.toString().trimEnd()}`));
  backendProcess.on("exit", (code, signal) => {
    console.info(`[desktop] Backend exited (code=${code ?? "none"}, signal=${signal ?? "none"})`);
    backendProcess = null;
  });
}

function stopBackend(): void {
  if (!backendProcess) return;
  backendProcess.kill();
  backendProcess = null;
}

async function waitForBackend(timeoutMs = 15_000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${backendBaseUrl}/api/v1/health`, {
        signal: AbortSignal.timeout(1_000),
      });
      if (response.ok) return true;
    } catch {
      // The Python process may still be importing dependencies.
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  console.error(`[desktop] Backend did not become ready at ${backendBaseUrl}`);
  return false;
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1040,
    minHeight: 680,
    backgroundColor: "#10131a",
    title: "Telegram Bot Studio",
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(currentDirectory, "index.mjs"),
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow?.show());

  if (isDevelopment && process.env.VITE_DEV_SERVER_URL) {
    await mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    await mainWindow.loadFile(path.join(currentDirectory, "../dist/index.html"));
  }
}

ipcMain.handle("desktop:select-directory", async () => {
  const options: Electron.OpenDialogOptions = {
    properties: ["openDirectory", "createDirectory"],
  };
  const result = mainWindow
    ? await dialog.showOpenDialog(mainWindow, options)
    : await dialog.showOpenDialog(options);
  return result.canceled ? null : result.filePaths[0] ?? null;
});

ipcMain.handle("desktop:reveal-path", async (_event, targetPath: string) => {
  if (targetPath) shell.showItemInFolder(path.resolve(targetPath));
});

ipcMain.handle("desktop:backend-info", () => ({ baseUrl: backendBaseUrl }));

app.whenReady().then(async () => {
  startBackend();
  await waitForBackend();
  await createWindow();
  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) await createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", stopBackend);
