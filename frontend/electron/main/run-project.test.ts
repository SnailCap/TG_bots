// @vitest-environment node

import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { buildLocalRunCommand, parseRunProjectInput, resolveRunProject } from "./run-project";

const temporaryDirectories: string[] = [];

afterEach(async () => {
  await Promise.all(temporaryDirectories.splice(0).map((directory) => rm(directory, { recursive: true, force: true })));
});

describe("local project run", () => {
  it("only resolves an approved project with its generated package entry point", async () => {
    const root = await temporaryProject();
    const target = await resolveRunProject({ projectRoot: root, packageName: "demo_bot" }, new Set([root]));

    expect(target).toEqual({ projectRoot: root, packageName: "demo_bot" });
    expect(buildLocalRunCommand(target)).toEqual({
      executable: process.platform === "win32"
        ? path.join(root, ".venv", "Scripts", "python.exe")
        : path.join(root, ".venv", "bin", "python"),
      args: ["-m", "demo_bot"],
    });
  });

  it("rejects malformed package names before any process can be launched", () => {
    expect(() => parseRunProjectInput({ projectRoot: "C:/demo", packageName: "demo; whoami" })).toThrow("valid Python package name");
  });
});

async function temporaryProject(): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), "tg-studio-run-project-"));
  temporaryDirectories.push(root);
  await mkdir(path.join(root, "resources"), { recursive: true });
  await mkdir(path.join(root, "src", "demo_bot"), { recursive: true });
  await writeFile(path.join(root, "resources", "bot.json"), "{}", "utf8");
  await writeFile(path.join(root, "src", "demo_bot", "__main__.py"), "", "utf8");
  return root;
}
