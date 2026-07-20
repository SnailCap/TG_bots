export type IdeAdapter = "system" | "vscode" | "jetbrains" | "custom";

export interface OpenCodeInput {
  projectRoot: string;
  filePath: string;
  line?: number;
  column?: number;
  adapter?: IdeAdapter;
}

export interface StudioDesktop {
  backendInfo(): Promise<{ baseUrl: string }>;
  selectDirectory(): Promise<string | null>;
  openCode(input: OpenCodeInput): Promise<void>;
}
