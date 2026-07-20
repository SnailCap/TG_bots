// @vitest-environment node

import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { assertApprovedProjectRoot, buildIdeCommand, ideConfiguration, parseOpenCodeInput, resolveCodeTarget } from "./open-code";

const temporaryDirectories: string[] = [];

afterEach(async () => {
  await Promise.all(temporaryDirectories.splice(0).map((directory) => rm(directory, { recursive: true, force: true })));
});

describe("open-code security", () => {
  it("resolves a Python source with spaces inside the project", async () => {
    const root = await temporaryProject();
    const folder = path.join(root, "src", "demo", "handlers with spaces");
    await mkdir(folder, { recursive: true });
    const source = path.join(folder, "submit order.py");
    await writeFile(source, "async def handle(ctx):\n    pass\n", "utf8");
    const resolved = await resolveCodeTarget({ projectRoot: root, filePath: path.relative(root, source), line: 7, column: 3 });
    expect(resolved.filePath).toBe(source);
    expect(resolved).toMatchObject({ line: 7, column: 3 });
  });

  it("rejects a sibling path that only shares the project prefix", async () => {
    const root = await temporaryProject();
    const outside = `${root}-outside`;
    temporaryDirectories.push(outside);
    await mkdir(outside);
    const source = path.join(outside, "handler.py");
    await writeFile(source, "pass\n", "utf8");
    await expect(resolveCodeTarget({ projectRoot: root, filePath: source })).rejects.toThrow("inside the open project root");
  });

  it("rejects non-Python files and malformed coordinates", async () => {
    const root = await temporaryProject();
    const source = path.join(root, "notes.txt");
    await writeFile(source, "notes", "utf8");
    await expect(resolveCodeTarget({ projectRoot: root, filePath: source })).rejects.toThrow("Only Python source files");
    expect(() => parseOpenCodeInput({ projectRoot: root, filePath: "handler.py", line: 0 })).toThrow("positive integer");
  });

  it("requires a project root approved by the native picker", async () => {
    const parent = await mkdtemp(path.join(tmpdir(), "tg-studio-approved-"));
    temporaryDirectories.push(parent);
    const project = path.join(parent, "demo");
    await mkdir(path.join(project, "resources"), { recursive: true });
    await writeFile(path.join(project, "resources", "bot.json"), "{}", "utf8");

    await expect(assertApprovedProjectRoot(project, new Set([parent]))).resolves.toBeUndefined();
    await expect(assertApprovedProjectRoot(project, new Set())).rejects.toThrow("not approved");

    const notProject = path.join(parent, "not-project");
    await mkdir(notProject);
    await expect(assertApprovedProjectRoot(notProject, new Set([parent]))).rejects.toThrow("not a schema v3 bot project");
  });
});

describe("IDE adapters", () => {
  const target = { projectRoot: "C:\\demo", filePath: "C:\\demo project\\handler.py", line: 12, column: 4 };

  it("builds VS Code goto arguments without a shell command string", () => {
    expect(buildIdeCommand(target, { adapter: "vscode", executable: "C:\\Program Files\\Microsoft VS Code\\Code.exe" })).toEqual({
      executable: "C:\\Program Files\\Microsoft VS Code\\Code.exe",
      args: ["--goto", "C:\\demo project\\handler.py:12:4"],
    });
  });

  it("builds JetBrains and fixed custom executable arguments", () => {
    expect(buildIdeCommand(target, { adapter: "jetbrains", executable: "pycharm64.exe" }).args).toEqual(["--line", "12", target.filePath]);
    expect(buildIdeCommand(target, { adapter: "custom", executable: "editor.exe" }).args).toEqual([target.filePath]);
  });

  it("loads only known adapters from controlled environment settings", () => {
    expect(ideConfiguration({ BOT_STUDIO_IDE: "jetbrains", BOT_STUDIO_IDE_EXECUTABLE: "pycharm64.exe" })).toEqual({ adapter: "jetbrains", executable: "pycharm64.exe" });
    expect(ideConfiguration({ BOT_STUDIO_IDE: "anything; rm -rf" })).toEqual({ adapter: "vscode", executable: undefined });
  });
});

async function temporaryProject(): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), "tg-studio-open-code-"));
  temporaryDirectories.push(root);
  return root;
}
