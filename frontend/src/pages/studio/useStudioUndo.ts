import { useCallback, useRef, useState, type Dispatch, type SetStateAction } from "react";

type UndoEntry = { undo: () => Promise<void> };

type StudioUndoOptions = {
  busy: boolean;
  setBusy: Dispatch<SetStateAction<boolean>>;
  clearError(): void;
  report(caught: unknown): void;
};

export function useStudioUndo({ busy, setBusy, clearError, report }: StudioUndoOptions) {
  const undoStackRef = useRef<UndoEntry[]>([]);
  const [undoAvailable, setUndoAvailable] = useState(false);

  const pushUndo = useCallback((entry: UndoEntry) => {
    undoStackRef.current.push(entry);
    setUndoAvailable(true);
  }, []);

  const performUndo = useCallback(async () => {
    if (busy) return;
    const entry = undoStackRef.current.pop();
    setUndoAvailable(undoStackRef.current.length > 0);
    if (!entry) return;
    setBusy(true);
    try {
      await entry.undo();
      clearError();
    } catch (caught) {
      report(caught);
    } finally {
      setBusy(false);
    }
  }, [busy, clearError, report, setBusy]);

  return { undoAvailable, pushUndo, performUndo };
}
