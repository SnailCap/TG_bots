import { StudioProvider } from "./providers/StudioProvider";
import { StudioShell } from "../widgets/studio-shell/ui/StudioShell";

export function App() {
  return (
    <StudioProvider>
      <StudioShell />
    </StudioProvider>
  );
}
