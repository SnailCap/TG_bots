import type { ChildProcess, SpawnOptions } from "node:child_process";
import { realpath, stat } from "node:fs/promises";
import path from "node:path";

import type { IdeAdapter, OpenCodeInput } from "../contracts";

export interface IdeConfiguration {
  adapter: IdeAdapter;
  executable?: string;
}

export interface ResolvedCodeTarget {
  projectRoot: string;
  filePath: string;
  line?: number;
  column?: number;
  adapter?: IdeAdapter;
}

export interface IdeCommand {
  executable: string;
  args: string[];
}

interface LaunchDependencies {
  openPath(filePath: string): Promise<string>;
  spawnProcess(command: string, args: readonly string[], options: SpawnOptions): ChildProcess;
}

const ADAPTERS = new Set<IdeAdapter>(["system", "vscode", "jetbrains", "custom"]);

export function parseOpenCodeInput(value: unknown): OpenCodeInput {
  if (!value || typeof value !== "object") throw new Error("Open-code request must be an object.");
  const input = value as { projectRoot?: unknown; filePath?: unknown; line?: unknown; column?: unknown; adapter?: unknown };
  if (typeof input.projectRoot !== "string" || !input.projectRoot.trim()) throw new Error("projectRoot is required.");
  if (typeof input.filePath !== "string" || !input.filePath.trim()) throw new Error("filePath is required.");
  if (input.line !== undefined && (!Number.isInteger(input.line) || Number(input.line) < 1)) throw new Error("line must be a positive integer.");
  if (input.column !== undefined && (!Number.isInteger(input.column) || Number(input.column) < 1)) throw new Error("column must be a positive integer.");
  if (input.adapter !== undefined && (typeof input.adapter !== "string" || !ADAPTERS.has(input.adapter as IdeAdapter))) throw new Error("Unknown IDE adapter.");
  return {
    projectRoot: input.projectRoot,
    filePath: input.filePath,
    line: input.line as number | undefined,
    column: input.column as number | undefined,
    adapter: input.adapter as IdeAdapter | undefined,
  };
}

export async function resolveCodeTarget(input: OpenCodeInput): Promise<ResolvedCodeTarget> {
  const parsed = parseOpenCodeInput(input);
  const canonicalRoot = await realpath(path.resolve(parsed.projectRoot));
  const rootStats = await stat(canonicalRoot);
  if (!rootStats.isDirectory()) throw new Error("Project root is not a directory.");

  const requested = path.isAbsolute(parsed.filePath)
    ? parsed.filePath
    : path.resolve(canonicalRoot, parsed.filePath);
  const canonicalFile = await realpath(requested);
  const relative = path.relative(canonicalRoot, canonicalFile);
  if (!relative || relative.startsWith(`..${path.sep}`) || relative === ".." || path.isAbsolute(relative)) {
    throw new Error("Source file must be inside the open project root.");
  }
  if (path.extname(canonicalFile).toLowerCase() !== ".py") throw new Error("Only Python source files can be opened.");
  const fileStats = await stat(canonicalFile);
  if (!fileStats.isFile()) throw new Error("Source path is not a file.");
  return { ...parsed, projectRoot: canonicalRoot, filePath: canonicalFile };
}

export async function assertApprovedProjectRoot(
  projectRoot: string,
  approvedRoots: ReadonlySet<string>,
): Promise<void> {
  const canonicalRoot = await realpath(projectRoot);
  const approved = [...approvedRoots].some((base) => {
    const relative = path.relative(base, canonicalRoot);
    return !relative || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
  });
  if (!approved) throw new Error("Project root was not approved through the directory picker.");
  const manifest = await stat(path.join(canonicalRoot, "resources", "bot.json")).catch(() => null);
  if (!manifest?.isFile()) throw new Error("Approved directory is not a schema v3 bot project.");
}

export function buildIdeCommand(target: ResolvedCodeTarget, configuration: IdeConfiguration): IdeCommand {
  const adapter = target.adapter ?? configuration.adapter;
  if (adapter === "system") throw new Error("System adapter uses the operating-system file association.");
  const executable = configuration.executable || (adapter === "vscode" ? "code" : "");
  if (!executable) throw new Error(`${adapter === "jetbrains" ? "JetBrains" : "Custom"} IDE executable is not configured.`);
  if (adapter === "vscode") {
    const position = target.line
      ? `${target.filePath}:${target.line}${target.column ? `:${target.column}` : ""}`
      : target.filePath;
    return { executable, args: ["--goto", position] };
  }
  if (adapter === "jetbrains") {
    return { executable, args: target.line ? ["--line", String(target.line), target.filePath] : [target.filePath] };
  }
  return { executable, args: [target.filePath] };
}

export async function launchOpenCode(
  input: OpenCodeInput,
  configuration: IdeConfiguration,
  dependencies: LaunchDependencies,
  approvedRoots: ReadonlySet<string>,
): Promise<void> {
  const target = await resolveCodeTarget(input);
  await assertApprovedProjectRoot(target.projectRoot, approvedRoots);
  const adapter = target.adapter ?? configuration.adapter;
  if (adapter === "system") {
    const error = await dependencies.openPath(target.filePath);
    if (error) throw new Error(error);
    return;
  }
  const command = buildIdeCommand(target, { ...configuration, adapter });
  await new Promise<void>((resolve, reject) => {
    const child = dependencies.spawnProcess(command.executable, command.args, {
      shell: false,
      windowsHide: true,
      detached: true,
      stdio: "ignore",
    });
    child.once("error", reject);
    child.once("spawn", () => {
      child.unref();
      resolve();
    });
  });
}

export function ideConfiguration(environment: NodeJS.ProcessEnv): IdeConfiguration {
  const requested = environment.BOT_STUDIO_IDE;
  const adapter = requested && ADAPTERS.has(requested as IdeAdapter) ? requested as IdeAdapter : "vscode";
  return { adapter, executable: environment.BOT_STUDIO_IDE_EXECUTABLE || undefined };
}
