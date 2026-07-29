import { useEffect, useRef, type Dispatch, type SetStateAction } from "react";

interface StudioKeyboardShortcutsOptions {
  activeTabKey: string | null;
  closeTab(tabKey: string): void;
  performUndo(): void | Promise<void>;
  save(): void;
  setTerminalOpen: Dispatch<SetStateAction<boolean>>;
}

export function useStudioKeyboardShortcuts({
  activeTabKey,
  closeTab,
  performUndo,
  save,
  setTerminalOpen,
}: StudioKeyboardShortcutsOptions): void {
  const saveRef = useRef(save);
  saveRef.current = save;

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && matchesPhysicalKey(event, "KeyS", "s")) {
        event.preventDefault();
        saveRef.current();
        return;
      }
      if (event.ctrlKey && (event.key === "`" || event.code === "Backquote")) {
        event.preventDefault();
        setTerminalOpen((open) => !open);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && matchesPhysicalKey(event, "KeyW", "w") && activeTabKey) {
        event.preventDefault();
        closeTab(activeTabKey);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && !event.shiftKey && matchesPhysicalKey(event, "KeyZ", "z")) {
        const target = event.target as HTMLElement | null;
        if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target?.isContentEditable) return;
        event.preventDefault();
        void performUndo();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeTabKey, closeTab, performUndo, setTerminalOpen]);
}

function matchesPhysicalKey(event: KeyboardEvent, code: string, fallbackKey: string): boolean {
  return event.code === code || (!event.code && event.key.toLowerCase() === fallbackKey);
}
