import type { ReactNode } from "react";
import { HashRouter, MemoryRouter } from "react-router-dom";

export function StudioRouter({ children }: { children: ReactNode }) {
  if (import.meta.env.MODE === "test") {
    return <MemoryRouter initialEntries={["/resources"]}>{children}</MemoryRouter>;
  }
  return <HashRouter>{children}</HashRouter>;
}
