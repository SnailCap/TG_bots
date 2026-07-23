import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from "electron";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { existsSync } from "node:fs";
import { realpath } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { ProjectOutputStream } from "../contracts";
import { assertApprovedProjectRoot, ideConfiguration, launchOpenCode, parseOpenCodeInput } from "./open-code";
import { prepareProjectEnvironment } from "./project-environment";
import { buildLocalRunCommand, parseRunProjectInput, resolveRunProject } from "./run-project";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const isDevelopment = Boolean(process.env.VITE_DEV_SERVER_URL);
const backendHost = process.env.BOT_STUDIO_BACKEND_HOST ?? "127.0.0.1";
const backendPort = process.env.BOT_STUDIO_BACKEND_PORT ?? "8000";
const backendBaseUrl = `http://${backendHost}:${backendPort}`;

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcessWithoutNullStreams | null = null;
const approvedRoots = new Set<string>();
const localRunProcesses = new Map<string, ChildProcessWithoutNullStreams>();
const environmentPreparations = new Map<string, Promise<string>>();
let projectOutputSequence = 0;

function emitProjectOutput(
  projectRoot: string,
  stream: ProjectOutputStream,
  text: string,
  state: { running?: boolean; pid?: number | null } = {},
): void {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.webContents.send("desktop:project-output", {
    sequence: ++projectOutputSequence,
    projectRoot,
    stream,
    text,
    timestamp: new Date().toISOString(),
    ...state,
  });
}

async function approvedProjectRoot(value: unknown): Promise<string> {
  if (typeof value !== "string" || !value.trim()) throw new Error("projectRoot is required.");
  const canonicalRoot = await realpath(path.resolve(value));
  await assertApprovedProjectRoot(canonicalRoot, approvedRoots);
  return canonicalRoot;
}

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
    ? { executable: "py", arguments: ["-3"] }
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

function stopLocalRuns(): void {
  for (const process of localRunProcesses.values()) process.kill();
  localRunProcesses.clear();
}

function ensureProjectEnvironment(target: Awaited<ReturnType<typeof resolveRunProject>>): Promise<string> {
  const existing = environmentPreparations.get(target.projectRoot);
  if (existing) return existing;
  const preparation = prepareProjectEnvironment(target, {
    stdout: (text) => emitProjectOutput(target.projectRoot, "stdout", text),
    stderr: (text) => emitProjectOutput(target.projectRoot, "stderr", text),
    lifecycle: (text) => emitProjectOutput(target.projectRoot, "lifecycle", text),
  }).finally(() => environmentPreparations.delete(target.projectRoot));
  environmentPreparations.set(target.projectRoot, preparation);
  return preparation;
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
ipcMain.handle("desktop:approve-project-root", async (_event, projectRoot: unknown) => {
  if (typeof projectRoot !== "string" || !projectRoot.trim()) throw new Error("projectRoot is required.");
  const canonicalRoot = await realpath(path.resolve(projectRoot));
  await assertApprovedProjectRoot(canonicalRoot, new Set([canonicalRoot]));
  approvedRoots.add(canonicalRoot);
});
ipcMain.handle("desktop:prepare-project", async (_event, input: unknown) => {
  const target = await resolveRunProject(parseRunProjectInput(input), approvedRoots);
  return { python: await ensureProjectEnvironment(target) };
});
ipcMain.handle("desktop:run-project", async (_event, input: unknown) => {
  const target = await resolveRunProject(parseRunProjectInput(input), approvedRoots);
  const existing = localRunProcesses.get(target.projectRoot);
  if (existing && !existing.killed && existing.exitCode === null) {
    emitProjectOutput(target.projectRoot, "lifecycle", `[studio] Bot is already running (PID ${existing.pid ?? "unknown"}).\n`, { running: true, pid: existing.pid ?? null });
    return { pid: existing.pid ?? 0, alreadyRunning: true };
  }

  await ensureProjectEnvironment(target);
  const command = buildLocalRunCommand(target);
  const displayCommand = [command.executable, ...command.args]
    .map((part) => /\s/.test(part) ? `"${part}"` : part)
    .join(" ");
  emitProjectOutput(target.projectRoot, "lifecycle", `[studio] Starting: ${displayCommand}\n`);
  const child = spawn(command.executable, command.args, {
    cwd: target.projectRoot,
    env: { ...process.env, BOT_PROJECT_ROOT: target.projectRoot, PYTHONUNBUFFERED: "1" },
    shell: false,
    stdio: "pipe",
    windowsHide: true,
  });
  try {
    await new Promise<void>((resolve, reject) => {
      const onError = (error: Error) => {
        child.removeListener("spawn", onSpawn);
        reject(error);
      };
      const onSpawn = () => {
        child.removeListener("error", onError);
        resolve();
      };
      child.once("error", onError);
      child.once("spawn", onSpawn);
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    emitProjectOutput(target.projectRoot, "stderr", `[studio] Failed to start bot: ${message}\n`, { running: false, pid: null });
    throw error;
  }
  localRunProcesses.set(target.projectRoot, child);
  emitProjectOutput(target.projectRoot, "lifecycle", `[studio] Bot started (PID ${child.pid ?? "unknown"}).\n`, { running: true, pid: child.pid ?? null });
  child.stdout.on("data", (chunk: Buffer) => {
    const text = chunk.toString();
    console.info(`[project:${target.packageName}] ${text.trimEnd()}`);
    emitProjectOutput(target.projectRoot, "stdout", text);
  });
  child.stderr.on("data", (chunk: Buffer) => {
    const text = chunk.toString();
    console.error(`[project:${target.packageName}] ${text.trimEnd()}`);
    emitProjectOutput(target.projectRoot, "stderr", text);
  });
  child.on("error", (error) => {
    console.error(`[project:${target.packageName}] Process error: ${error.message}`);
    emitProjectOutput(target.projectRoot, "stderr", `[studio] Bot process error: ${error.message}\n`);
  });
  child.on("exit", (code, signal) => {
    localRunProcesses.delete(target.projectRoot);
    console.info(`[project:${target.packageName}] exited (code=${code ?? "none"}, signal=${signal ?? "none"})`);
    emitProjectOutput(target.projectRoot, "lifecycle", `[studio] Bot stopped (code=${code ?? "none"}, signal=${signal ?? "none"}).\n`, { running: false, pid: null });
  });
  return { pid: child.pid ?? 0, alreadyRunning: false };
});
ipcMain.handle("desktop:stop-project", async (_event, projectRoot: unknown) => {
  const canonicalRoot = await approvedProjectRoot(projectRoot);
  const child = localRunProcesses.get(canonicalRoot);
  if (!child || child.killed || child.exitCode !== null) {
    emitProjectOutput(canonicalRoot, "lifecycle", "[studio] Bot is not running.\n", { running: false, pid: null });
    return;
  }
  emitProjectOutput(canonicalRoot, "lifecycle", `[studio] Stopping bot (PID ${child.pid ?? "unknown"})…\n`);
  if (!child.kill()) throw new Error("Could not stop the local bot process.");
});
ipcMain.handle("desktop:project-run-status", async (_event, projectRoot: unknown) => {
  const canonicalRoot = await approvedProjectRoot(projectRoot);
  const child = localRunProcesses.get(canonicalRoot);
  const running = Boolean(child && !child.killed && child.exitCode === null);
  return { running, pid: running ? child?.pid ?? null : null };
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

app.on("before-quit", () => {
  stopLocalRuns();
  stopBackend();
});
