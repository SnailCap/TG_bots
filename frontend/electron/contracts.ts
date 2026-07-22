export type IdeAdapter = "system" | "vscode" | "jetbrains" | "custom";

export interface OpenCodeInput {
  projectRoot: string;
  filePath: string;
  line?: number;
  column?: number;
  adapter?: IdeAdapter;
}

export interface RunProjectInput {
  projectRoot: string;
  packageName: string;
}

export interface LocalRunResult {
  pid: number;
  alreadyRunning: boolean;
}

export interface LocalRunStatus {
  running: boolean;
  pid: number | null;
}

export type ProjectOutputStream = "stdout" | "stderr" | "lifecycle";

export interface ProjectProcessEvent {
  sequence: number;
  projectRoot: string;
  stream: ProjectOutputStream;
  text: string;
  timestamp: string;
  running?: boolean;
  pid?: number | null;
}

export interface StudioDesktop {
  backendInfo(): Promise<{ baseUrl: string }>;
  selectDirectory(): Promise<string | null>;
  openCode(input: OpenCodeInput): Promise<void>;
  approveProjectRoot?(projectRoot: string): Promise<void>;
  runProject?(input: RunProjectInput): Promise<LocalRunResult>;
  stopProject?(projectRoot: string): Promise<void>;
  projectRunStatus?(projectRoot: string): Promise<LocalRunStatus>;
  onProjectOutput?(listener: (event: ProjectProcessEvent) => void): () => void;
}
