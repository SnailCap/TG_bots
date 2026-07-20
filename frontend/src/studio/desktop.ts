import type { IdeAdapter, OpenCodeInput } from "../../electron/contracts";
import type { OpenCodeTarget } from "../domain/project";

export async function openCode(target: OpenCodeTarget, adapter?: IdeAdapter): Promise<void> {
  if (!window.studioDesktop) throw new Error("Open code is available in the desktop Studio application.");
  const input: OpenCodeInput = { ...target, adapter };
  await window.studioDesktop.openCode(input);
}
