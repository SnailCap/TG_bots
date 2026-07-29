import { CalendarDays, FileText, House, SquareTerminal, Terminal, Workflow, Zap } from "lucide-react";

import type { Selection } from "../../domain/project";

export function ResourceIcon({ selection, title }: { selection: Selection; title: string }) {
  const isHome = selection.kind === "view" && /^(home|index|start)$/i.test(title);
  const icons = {
    view: isHome ? House : FileText,
    flow: Workflow,
    handler: Zap,
    command: SquareTerminal,
    commands: Terminal,
    schedule: CalendarDays,
  };
  const Icon = icons[selection.kind];
  return <span className={`explorer__resource-icon explorer__resource-icon--${selection.kind}`} aria-hidden="true"><Icon /></span>;
}
