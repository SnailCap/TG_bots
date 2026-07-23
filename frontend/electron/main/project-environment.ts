import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";

import type { ResolvedRunProject } from "./run-project";

const PYTHON_COMPATIBILITY_CHECK = [
  "import sys",
  "raise SystemExit(0 if (3, 12) <= sys.version_info[:2] < (3, 14) else 1)",
].join("; ");
const ENVIRONMENT_MARKER_VERSION = 1;
const LEGACY_CORE_PIN = "git+https://github.com/SnailCap/TG_bots.git@core-v3.0.0#subdirectory=packages/tg-bot-core";
const CURRENT_CORE_PIN = "git+https://github.com/SnailCap/TG_bots.git@b183a173a3f46f2b096a0b6ec877ad5cba41566a#subdirectory=packages/tg-bot-core";

export interface PythonCommand {
  executable: string;
  args: string[];
}

export interface EnvironmentOutput {
  stdout(text: string): void;
  stderr(text: string): void;
  lifecycle(text: string): void;
}

interface EnvironmentMarker {
  version: number;
  projectHash: string;
}

export function projectEnvironmentPython(projectRoot: string, platform = process.platform): string {
  return platform === "win32"
    ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
    : path.join(projectRoot, ".venv", "bin", "python");
}

export function compatiblePythonCandidates(
  platform = process.platform,
  environment: NodeJS.ProcessEnv = process.env,
): PythonCommand[] {
  const configured = environment.BOT_STUDIO_PYTHON?.trim();
  const candidates: PythonCommand[] = configured ? [{ executable: configured, args: [] }] : [];
  if (platform === "win32") {
    candidates.push(
      { executable: "py", args: ["-3.13"] },
      { executable: "py", args: ["-3.12"] },
    );
  } else {
    candidates.push(
      { executable: "python3.13", args: [] },
      { executable: "python3.12", args: [] },
      { executable: "python3", args: [] },
    );
  }
  return candidates.filter((candidate, index, all) => all.findIndex(
    (item) => item.executable === candidate.executable && item.args.join("\0") === candidate.args.join("\0"),
  ) === index);
}

export function migrateLegacyCorePin(pyproject: string): string {
  return pyproject.replace(LEGACY_CORE_PIN, CURRENT_CORE_PIN);
}

export async function prepareProjectEnvironment(
  target: ResolvedRunProject,
  output: EnvironmentOutput,
): Promise<string> {
  const pyprojectPath = path.join(target.projectRoot, "pyproject.toml");
  let pyproject = await readFile(pyprojectPath, "utf8");
  const migratedPyproject = migrateLegacyCorePin(pyproject);
  if (migratedPyproject !== pyproject) {
    const temporaryPyproject = `${pyprojectPath}.${process.pid}.tmp`;
    await writeFile(temporaryPyproject, migratedPyproject, "utf8");
    await rename(temporaryPyproject, pyprojectPath);
    pyproject = migratedPyproject;
    output.lifecycle("[studio] Updated the legacy tg-bot-core dependency pin.\n");
  }
  const projectHash = createHash("sha256").update(pyproject).digest("hex");
  const environmentRoot = path.join(target.projectRoot, ".venv");
  const environmentPython = projectEnvironmentPython(target.projectRoot);
  const markerPath = path.join(environmentRoot, ".studio-environment.json");

  let compatibleEnvironment = existsSync(environmentPython)
    && await commandSucceeds({ executable: environmentPython, args: [] }, ["-c", PYTHON_COMPATIBILITY_CHECK]);
  if (!compatibleEnvironment) {
    if (existsSync(environmentRoot)) {
      output.lifecycle("[studio] Recreating the incompatible Python environment...\n");
      await rm(environmentRoot, { recursive: true, force: true });
    }
    const python = await findCompatiblePython();
    output.lifecycle(`[studio] Creating .venv with ${displayCommand(python)}...\n`);
    await runCommand(python, ["-m", "venv", environmentRoot], output);
    compatibleEnvironment = true;
  }

  const existingMarker = compatibleEnvironment ? await readMarker(markerPath) : null;
  if (existingMarker?.version === ENVIRONMENT_MARKER_VERSION && existingMarker.projectHash === projectHash) {
    return environmentPython;
  }

  output.lifecycle("[studio] Installing project dependencies...\n");
  await runCommand(
    { executable: environmentPython, args: [] },
    ["-m", "pip", "install", "--disable-pip-version-check", "-e", ".[dev]"],
    output,
    target.projectRoot,
  );
  const marker: EnvironmentMarker = { version: ENVIRONMENT_MARKER_VERSION, projectHash };
  const temporaryMarker = `${markerPath}.${process.pid}.tmp`;
  await writeFile(temporaryMarker, `${JSON.stringify(marker, null, 2)}\n`, "utf8");
  await rename(temporaryMarker, markerPath);
  output.lifecycle("[studio] Python environment is ready.\n");
  return environmentPython;
}

async function findCompatiblePython(): Promise<PythonCommand> {
  for (const candidate of compatiblePythonCandidates()) {
    if (await commandSucceeds(candidate, ["-c", PYTHON_COMPATIBILITY_CHECK])) return candidate;
  }
  throw new Error(
    "Studio could not find a compatible Python runtime. Install Python 3.12 or 3.13, "
      + "or set BOT_STUDIO_PYTHON to its executable.",
  );
}

async function readMarker(markerPath: string): Promise<EnvironmentMarker | null> {
  try {
    const value: unknown = JSON.parse(await readFile(markerPath, "utf8"));
    if (!value || typeof value !== "object") return null;
    const marker = value as Partial<EnvironmentMarker>;
    return typeof marker.version === "number" && typeof marker.projectHash === "string"
      ? { version: marker.version, projectHash: marker.projectHash }
      : null;
  } catch {
    return null;
  }
}

async function commandSucceeds(command: PythonCommand, args: string[]): Promise<boolean> {
  try {
    await runCommand(command, args);
    return true;
  } catch {
    return false;
  }
}

async function runCommand(
  command: PythonCommand,
  args: string[],
  output?: EnvironmentOutput,
  cwd?: string,
): Promise<void> {
  const child = spawn(command.executable, [...command.args, ...args], {
    cwd,
    env: process.env,
    shell: false,
    stdio: "pipe",
    windowsHide: true,
  });
  let stderrTail = "";
  child.stdout.on("data", (chunk: Buffer) => output?.stdout(chunk.toString()));
  child.stderr.on("data", (chunk: Buffer) => {
    const text = chunk.toString();
    stderrTail = `${stderrTail}${text}`.slice(-4000);
    output?.stderr(text);
  });
  await new Promise<void>((resolve, reject) => {
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) {
        resolve();
        return;
      }
      const detail = stderrTail.trim();
      reject(new Error(
        `${displayCommand(command)} exited with code ${code ?? "none"}`
          + (signal ? ` (signal ${signal})` : "")
          + (detail ? `: ${detail}` : ""),
      ));
    });
  });
}

function displayCommand(command: PythonCommand): string {
  return [command.executable, ...command.args]
    .map((part) => /\s/.test(part) ? `"${part}"` : part)
    .join(" ");
}
