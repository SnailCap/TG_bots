import { useStudio } from "../../../app/providers/StudioProvider";
import { ConsolePanel } from "../../console/ui/ConsolePanel";
import { Inspector } from "../../inspector/ui/Inspector";
import { MessagePreview } from "../../preview/ui/MessagePreview";
import { ProjectExplorer } from "../../project-explorer/ui/ProjectExplorer";
import { TopBar } from "../../top-bar/ui/TopBar";
import { Workspace } from "../../workspace/ui/Workspace";
import styles from "./StudioShell.module.css";

export function StudioShell() {
  const studio = useStudio();
  return (
    <div className={styles.shell}>
      <TopBar />
      <div className={styles.main}>
        <ProjectExplorer />
        <Workspace />
        <div className={styles.rightRail}>
          <Inspector />
          <MessagePreview />
        </div>
      </div>
      <ConsolePanel />
      {studio.appError && (
        <div className={styles.errorToast} role="alert">
          <span>{studio.appError}</span>
          <button onClick={studio.clearAppError}>×</button>
        </div>
      )}
    </div>
  );
}
