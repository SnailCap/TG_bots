import { useCallback, useEffect, useRef, useState } from "react";

export function useStudioLayout(previewOpen: boolean) {
  const [explorerWidth, setExplorerWidth] = useState(262);
  const [terminalHeight, setTerminalHeight] = useState(280);
  const explorerWidthRef = useRef(explorerWidth);
  const terminalHeightRef = useRef(terminalHeight);
  const workspaceRef = useRef<HTMLDivElement>(null);

  const maximumExplorerWidth = useCallback((workspaceWidth: number) => {
    const previewWidth = previewOpen ? Math.min(340, Math.max(220, workspaceWidth * 0.27)) : 0;
    return Math.max(180, workspaceWidth - previewWidth - 321);
  }, [previewOpen]);

  const maximumTerminalHeight = useCallback((workspaceHeight: number) => Math.max(120, workspaceHeight - 165), []);

  useEffect(() => {
    const clampDimensions = () => {
      const workspaceElement = workspaceRef.current;
      if (!workspaceElement) return;
      const width = Math.min(maximumExplorerWidth(workspaceElement.clientWidth), explorerWidthRef.current);
      const height = Math.min(maximumTerminalHeight(workspaceElement.clientHeight), terminalHeightRef.current);
      if (width !== explorerWidthRef.current) {
        explorerWidthRef.current = width;
        setExplorerWidth(width);
      }
      if (height !== terminalHeightRef.current) {
        terminalHeightRef.current = height;
        setTerminalHeight(height);
      }
    };
    clampDimensions();
    window.addEventListener("resize", clampDimensions);
    return () => window.removeEventListener("resize", clampDimensions);
  }, [maximumExplorerWidth, maximumTerminalHeight]);

  const resizeExplorer = useCallback((width: number) => {
    explorerWidthRef.current = width;
    workspaceRef.current?.style.setProperty("--explorer-width", `${width}px`);
  }, []);

  const commitExplorerSize = useCallback(() => setExplorerWidth(explorerWidthRef.current), []);

  const resizeTerminal = useCallback((height: number) => {
    terminalHeightRef.current = height;
    workspaceRef.current?.style.setProperty("--terminal-height", `${height}px`);
  }, []);

  const commitTerminalSize = useCallback(() => setTerminalHeight(terminalHeightRef.current), []);

  return {
    explorerWidth,
    terminalHeight,
    workspaceRef,
    maximumExplorerWidth,
    maximumTerminalHeight,
    resizeExplorer,
    commitExplorerSize,
    resizeTerminal,
    commitTerminalSize,
  };
}
