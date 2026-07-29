import type { CSSProperties, ReactNode } from "react";
import { ChevronDown } from "lucide-react";

type TreeDisclosure = {
  label: string;
  expanded: boolean;
  controls: string;
  onToggle(): void;
};

type ExplorerTreeRowProps = {
  depth?: number;
  disclosure?: TreeDisclosure;
  children: ReactNode;
};

type ExplorerTreeLeafProps = {
  depth: number;
  icon: ReactNode;
  children: ReactNode;
  ariaLabel?: string;
  onClick?(): void;
};

export function ExplorerTreeRow({ depth = 0, disclosure, children }: ExplorerTreeRowProps) {
  const style = { "--explorer-tree-depth": depth } as CSSProperties;
  const className = disclosure
    ? "explorer-tree__row"
    : "explorer-tree__row explorer-tree__row--without-disclosure";
  return <div className={className} data-tree-depth={depth} style={style}>
    {disclosure
      ? <button
          type="button"
          className="explorer-tree__toggle"
          aria-label={disclosure.label}
          aria-expanded={disclosure.expanded}
          aria-controls={disclosure.controls}
          onClick={(event) => {
            event.stopPropagation();
            disclosure.onToggle();
          }}
        >
          <span className={disclosure.expanded ? "explorer-tree__arrow explorer-tree__arrow--open" : "explorer-tree__arrow"} aria-hidden="true"><ChevronDown /></span>
        </button>
      : null}
    <div className="explorer-tree__main">{children}</div>
  </div>;
}

export function ExplorerTreeGroup({ id, open, children }: { id: string; open: boolean; children: ReactNode }) {
  return <div id={id} className={open ? "explorer-tree__group explorer-tree__group--open" : "explorer-tree__group"}>
    <div className="explorer-tree__group-items">{children}</div>
  </div>;
}

export function ExplorerTreeLeaf({ depth, icon, children, ariaLabel, onClick }: ExplorerTreeLeafProps) {
  const content = <><span className="explorer-tree__leaf-icon" aria-hidden="true">{icon}</span><span className="explorer-tree__leaf-label">{children}</span></>;
  return <ExplorerTreeRow depth={depth}>
    {onClick
      ? <button type="button" className="explorer-tree__leaf" aria-label={ariaLabel} onClick={onClick}>{content}</button>
      : <div className="explorer-tree__leaf">{content}</div>}
  </ExplorerTreeRow>;
}
