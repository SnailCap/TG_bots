import type { ReactNode } from "react";

import type { Selection } from "../../domain/project";

export function ResourceIcon({ selection, title }: { selection: Selection; title: string }) {
  const isHome = selection.kind === "view" && /^(home|index|start)$/i.test(title);
  const paths: Record<Selection["kind"], ReactNode> = {
    view: isHome ? <path d="M3 7.1 8 3l5 4.1v5.15c0 .4-.32.75-.75.75H9.5V9.5h-3v3.5H3.75a.75.75 0 0 1-.75-.75V7.1Z" /> : <><rect x="2.75" y="3.25" width="10.5" height="9.5" rx="1.25" /><path d="M5.25 6.25h5.5M5.25 8.5h5.5M5.25 10.75h3" /></>,
    template: <><path d="m5.75 4-3 4 3 4M10.25 4l3 4-3 4" /><path d="m9.25 3-2.5 10" /></>,
    flow: <><circle cx="4" cy="4" r="1.35" /><circle cx="12" cy="4" r="1.35" /><circle cx="12" cy="12" r="1.35" /><path d="M5.35 4h1.8A2.85 2.85 0 0 1 10 6.85v3.8" /></>,
    handler: <path d="m9.2 2.5-4.4 6h3l-.75 5 4.4-6h-3l.75-5Z" />,
    command: <><path d="M3.25 4.25h9.5v7.5h-9.5z" /><path d="m5.25 6.5 1.5 1.5-1.5 1.5M8.5 9.5h2.25" /></>,
    commands: <><path d="m3.5 5 2.5 3-2.5 3M8 11h4.5" /></>,
    schedule: <><rect x="3" y="4" width="10" height="9" rx="1.25" /><path d="M5.5 2.75v2.5M10.5 2.75v2.5M3 7h10M5.5 9.5h.01M8 9.5h.01M10.5 9.5h.01" /></>,
  };
  return <span className={`explorer__resource-icon explorer__resource-icon--${selection.kind}`} aria-hidden="true"><svg viewBox="0 0 16 16" focusable="false">{paths[selection.kind]}</svg></span>;
}
