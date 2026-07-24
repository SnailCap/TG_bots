// @vitest-environment node

import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  compatiblePythonCandidates,
  migrateLegacyCorePin,
  projectEnvironmentPython,
} from "./project-environment";

describe("managed project Python environment", () => {
  it("prefers supported Windows Python versions instead of pinning one minor", () => {
    expect(compatiblePythonCandidates("win32", {})).toEqual([
      { executable: "py", args: ["-3.13"] },
      { executable: "py", args: ["-3.12"] },
    ]);
  });

  it("honors an explicitly configured interpreter before automatic discovery", () => {
    expect(compatiblePythonCandidates("win32", { BOT_STUDIO_PYTHON: "C:\\Python\\python.exe" })[0])
      .toEqual({ executable: "C:\\Python\\python.exe", args: [] });
  });

  it("always points local runs at the managed project environment", () => {
    expect(projectEnvironmentPython("C:\\bots\\demo", "win32"))
      .toBe(path.join("C:\\bots\\demo", ".venv", "Scripts", "python.exe"));
    expect(projectEnvironmentPython("/bots/demo", "linux"))
      .toBe(path.join("/bots/demo", ".venv", "bin", "python"));
  });

  it("migrates known outdated starter dependency pins", () => {
    const legacyPins = [
      "dependencies = [",
      '  "tg-bot-core @ git+https://github.com/SnailCap/TG_bots.git@core-v3.0.0#subdirectory=packages/tg-bot-core",',
      '  "tg-bot-core @ git+https://github.com/SnailCap/TG_bots.git@b183a173a3f46f2b096a0b6ec877ad5cba41566a#subdirectory=packages/tg-bot-core",',
      '  "custom-package>=1",',
      "]",
    ].join("\n");
    const migrated = migrateLegacyCorePin(legacyPins);

    expect(migrated).not.toContain("@core-v3.0.0#subdirectory");
    expect(migrated).not.toContain("@b183a173a3f46f2b096a0b6ec877ad5cba41566a#subdirectory");
    expect(migrated).toContain("@119f2200566021ebf4d5bafa44c08805dcf236ed#subdirectory");
    expect(migrated).toContain('"custom-package>=1"');
    expect(migrateLegacyCorePin(migrated)).toBe(migrated);
  });
});
