import { useEffect, useRef } from "react";

import type { ProjectProcessEvent } from "../../../electron/contracts";

export function StudioTerminal({
  entries,
  running,
  pid,
  onClose,
}: {
  entries: readonly ProjectProcessEvent[];
  running: boolean;
  pid: number | null;
  onClose(): void;
}) {
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const output = outputRef.current;
    if (output) output.scrollTop = output.scrollHeight;
  }, [entries]);

  return (
    <section className="studio-terminal" aria-label="Bot terminal">
      <header className="studio-terminal__header">
        <div className="studio-terminal__title-group">
          <span className="studio-terminal__title">Terminal</span>
          {running && <span className="studio-terminal__state studio-terminal__state--running">
            <span aria-hidden="true" />
            {`Running${pid ? ` · PID ${pid}` : ""}`}
          </span>}
        </div>
        <button type="button" className="studio-terminal__close" aria-label="Close terminal" title="Close terminal" onClick={onClose}>
          <CloseIcon />
        </button>
      </header>
      <div ref={outputRef} className="studio-terminal__output" role="log" aria-live="polite" aria-relevant="additions text">
        {entries.length === 0
          ? <span className="studio-terminal__empty">Run the bot to see its output here.</span>
          : entries.map((entry) => (
            <span key={entry.sequence} className={`studio-terminal__chunk studio-terminal__chunk--${entry.stream}`}>{entry.text}</span>
          ))}
      </div>
    </section>
  );
}

function CloseIcon() {
  return <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="m4.5 4.5 7 7m0-7-7 7" /></svg>;
}
