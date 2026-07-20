/// <reference types="vite/client" />

import type { StudioDesktop } from "../electron/contracts";

declare global {
  interface Window {
    studioDesktop?: StudioDesktop;
  }
}

export {};
