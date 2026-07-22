import { existsSync } from "node:fs";
import { realpath, stat } from "node:fs/promises";
import path from "node:path";

import { assertApprovedProjectRoot } from "./open-code";
import type { RunProjectInput } from "../contracts";

const PACKAGE_NAME = /^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$/;

export interface ResolvedRunProject {
  projectRoot: string;
  packageName: string;
}

export interface LocalRunCommand {
  executable: string;
  args: string[];
}

export function parseRunProjectInput(value: unknown): RunProjectInput {
  if (!value || typeof value !== "object") throw new Error("Run request must be an object.");
  const input = value as { projectRoot?: unknown; packageName?: unknown };
  if (typeof input.projectRoot !== "string" || !input.projectRoot.trim()) throw new Error("projectRoot is required.");
  if (typeof input.packageName !== "string" || !PACKAGE_NAME.test(input.packageName)) throw new Error("packageName must be a valid Python package name.");
  return { projectRoot: input.projectRoot, packageName: input.packageName };
}

export async function resolveRunProject(
  input: RunProjectInput,
  approvedRoots: ReadonlySet<string>,
): Promise<ResolvedRunProject> {
  const parsed = parseRunProjectInput(input);
  const projectRoot = await realpath(path.resolve(parsed.projectRoot));
  await assertApprovedProjectRoot(projectRoot, approvedRoots);
  const entrypoint = path.join(projectRoot, "src", ...parsed.packageName.split("."), "__main__.py");
  const entrypointStats = await stat(entrypoint).catch(() => null);
  if (!entrypointStats?.isFile()) throw new Error("The approved bot project has no Python entry point.");
  return { projectRoot, packageName: parsed.packageName };
}

export function buildLocalRunCommand(target: ResolvedRunProject): LocalRunCommand {
  const virtualEnvironmentPython = process.platform === "win32"
    ? path.join(target.projectRoot, ".venv", "Scripts", "python.exe")
    : path.join(target.projectRoot, ".venv", "bin", "python");
  if (existsSync(virtualEnvironmentPython)) {
    return { executable: virtualEnvironmentPython, args: ["-m", target.packageName] };
  }
  return process.platform === "win32"
    ? { executable: "py", args: ["-3.12", "-m", target.packageName] }
    : { executable: "python3", args: ["-m", target.packageName] };
}
