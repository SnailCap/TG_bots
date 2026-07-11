import { useMemo, useState } from "react";
import { useStudio } from "../../../app/providers/StudioProvider";
import type { ProjectTreeKind, ProjectTreeNode } from "../../../entities/project/model/types";
import styles from "./ProjectExplorer.module.css";

const icons: Record<ProjectTreeKind, string> = {
  project: "◆",
  directory: "▾",
  flow: "◇",
  script: "#",
  asset: "▧",
  settings: "⚙",
};

function filterTree(nodes: ProjectTreeNode[], query: string): ProjectTreeNode[] {
  if (!query) return nodes;
  return nodes.flatMap((node) => {
    const children = filterTree(node.children, query);
    return node.name.toLowerCase().includes(query) || children.length ? [{ ...node, children }] : [];
  });
}

function TreeRow({
  node,
  depth,
  selected,
  onSelect,
  onOpen,
}: {
  node: ProjectTreeNode;
  depth: number;
  selected: string | null;
  onSelect(node: ProjectTreeNode): void;
  onOpen(node: ProjectTreeNode): void;
}) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children.length > 0;
  return (
    <>
      <button
        className={`${styles.row} ${selected === node.id ? styles.selected : ""}`}
        style={{ paddingLeft: 8 + depth * 14 }}
        onClick={() => onSelect(node)}
        onDoubleClick={() => {
          if (hasChildren) setExpanded((value) => !value);
          else onOpen(node);
        }}
        title={node.path}
      >
        <span className={styles.disclosure}>{hasChildren ? (expanded ? "▾" : "▸") : ""}</span>
        <span className={styles.icon}>{icons[node.kind]}</span>
        <span className={styles.name}>{node.name}</span>
        {node.hasError && <span className={styles.errorBadge}>{node.errorCount ?? "!"}</span>}
      </button>
      {expanded &&
        node.children.map((child) => (
          <TreeRow
            key={`${child.kind}:${child.id}:${child.path}`}
            node={child}
            depth={depth + 1}
            selected={selected}
            onSelect={onSelect}
            onOpen={onOpen}
          />
        ))}
    </>
  );
}

export function ProjectExplorer() {
  const studio = useStudio();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<ProjectTreeNode | null>(null);
  const visibleTree = useMemo(() => filterTree(studio.tree, query.trim().toLowerCase()), [query, studio.tree]);

  async function create(kind: ProjectTreeKind) {
    const defaultName = kind === "flow" ? "New Flow" : kind === "script" ? "action.py" : "asset.txt";
    const name = window.prompt(`Name for the new ${kind}`, defaultName)?.trim();
    if (name) await studio.createExplorerResource(kind, name);
  }

  async function rename() {
    if (!selected) return;
    const nextPath = window.prompt("New resource path/name", selected.path || selected.name)?.trim();
    if (nextPath && nextPath !== selected.path) await studio.renameResource(selected, nextPath);
  }

  async function remove() {
    if (!selected || !window.confirm(`Delete ${selected.name}? This cannot be undone.`)) return;
    await studio.deleteResource(selected);
    setSelected(null);
  }

  return (
    <aside className={styles.panel} aria-label="Project Explorer">
      <div className={styles.heading}>
        <strong>Project</strong>
        <button onClick={() => void studio.refreshProjectResources()} title="Refresh project tree">
          ↻
        </button>
      </div>
      <div className={styles.toolbar}>
        <button disabled={!studio.currentProject} onClick={() => void create("flow")} title="New flow">
          + Flow
        </button>
        <button disabled={!studio.currentProject} onClick={() => void create("script")} title="New Python script">
          + Script
        </button>
        <button disabled={!studio.currentProject} onClick={() => void create("asset")} title="New asset reference">
          + Asset
        </button>
      </div>
      <input
        className={styles.search}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search project…"
        aria-label="Search project"
      />
      <div className={styles.tree}>
        {!studio.currentProject ? (
          <p className={styles.empty}>Create or open a bot project to start.</p>
        ) : visibleTree.length ? (
          visibleTree.map((node) => (
            <TreeRow
              key={`${node.kind}:${node.id}:${node.path}`}
              node={node}
              depth={0}
              selected={selected?.id ?? null}
              onSelect={setSelected}
              onOpen={studio.openTreeNode}
            />
          ))
        ) : (
          <p className={styles.empty}>No matching project items.</p>
        )}
      </div>
      <div className={styles.actions}>
        <button disabled={!selected || selected.kind === "settings"} onClick={() => void rename()}>
          Rename
        </button>
        <button disabled={!selected || selected.kind === "settings"} onClick={() => void remove()}>
          Delete
        </button>
        <button disabled={!selected} onClick={() => selected && studio.openTreeNode(selected)}>
          Open
        </button>
      </div>
    </aside>
  );
}
