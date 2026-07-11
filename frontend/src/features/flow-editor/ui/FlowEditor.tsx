import {
  addEdge,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  type Connection,
  type EdgeChange,
  type NodeChange,
  type OnSelectionChangeParams,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStudio } from "../../../app/providers/StudioProvider";
import type {
  FlowDocument,
  FlowNodeKind,
  StudioEdge,
  StudioNode,
  StudioNodeData,
  TransitionKind,
} from "../../../entities/flow/model/types";
import { toApiError } from "../../../shared/api/client";
import { studioApi } from "../../../shared/api/studioApi";
import { FlowNodeCard } from "./FlowNodeCard";
import styles from "./FlowEditor.module.css";

const nodeTypes = { studioNode: FlowNodeCard };

const nodeDefaults: Record<FlowNodeKind, StudioNodeData> = {
  start: { kind: "start", title: "Start" },
  send_message: { kind: "send_message", title: "Send Message", text: "New message" },
  ask_input: {
    kind: "ask_input",
    title: "Ask Input",
    text: "What would you like to ask?",
    variableName: "user.answer",
    valueType: "string",
    required: true,
    validationRegex: "",
    errorMessage: "Please enter a valid value.",
    maxAttempts: 3,
  },
  choice: {
    kind: "choice",
    title: "Choice",
    text: "Choose an option",
    keyboard: "inline",
    choices: [
      { id: "option-1", label: "Option 1", value: "option_1" },
      { id: "option-2", label: "Option 2", value: "option_2" },
    ],
  },
  action: {
    kind: "action",
    title: "Action",
    actionName: "",
    actionTimeoutSeconds: 30,
    actionInputParameters: {},
    actionOutputMapping: {},
  },
  condition: {
    kind: "condition",
    title: "Condition",
    conditionVariable: "",
    conditionOperator: "truthy",
  },
  end: { kind: "end", title: "End" },
};

function nextId(kind: FlowNodeKind): string {
  return `${kind}-${globalThis.crypto?.randomUUID?.() ?? Date.now().toString(36)}`;
}

function transitionFromHandle(handle: string | null | undefined, sourceKind?: FlowNodeKind): TransitionKind {
  if (sourceKind === "choice") return "button";
  if (handle === "success") return "success";
  if (handle === "error") return "error";
  if (handle === "true" || handle === "false") return "condition";
  if (handle?.startsWith("option-")) return "button";
  return "automatic";
}

export function FlowEditor({ flowId, tabId }: { flowId: string; tabId: string }) {
  const studio = useStudio();
  const [flow, setFlow] = useState<FlowDocument | null>(null);
  const [nodes, setNodes, baseOnNodesChange] = useNodesState<StudioNode>([]);
  const [edges, setEdges, baseOnEdgesChange] = useEdgesState<StudioEdge>([]);
  const [instance, setInstance] = useState<ReactFlowInstance<StudioNode, StudioEdge> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedIds = useRef({ nodes: [] as string[], edges: [] as string[] });
  const projectId = studio.currentProject?.id;

  useEffect(() => {
    if (!projectId) return;
    let active = true;
    setLoading(true);
    setError(null);
    void studioApi
      .getFlow(projectId, flowId)
      .then((loaded) => {
        if (!active) return;
        setFlow(loaded);
        setNodes(loaded.nodes);
        setEdges(loaded.edges);
        studio.markTabDirty(tabId, false);
        window.setTimeout(() => instance?.fitView({ padding: 0.2 }), 0);
      })
      .catch((reason) => active && setError(toApiError(reason).message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [flowId, instance, projectId, setEdges, setNodes, studio.markTabDirty, tabId]);

  const markDirty = useCallback(() => studio.markTabDirty(tabId, true), [studio.markTabDirty, tabId]);

  const onNodesChange = useCallback(
    (changes: NodeChange<StudioNode>[]) => {
      baseOnNodesChange(changes);
      if (changes.some((change) => ["add", "remove", "position", "replace"].includes(change.type))) markDirty();
    },
    [baseOnNodesChange, markDirty],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange<StudioEdge>[]) => {
      baseOnEdgesChange(changes);
      if (changes.some((change) => ["add", "remove", "replace"].includes(change.type))) markDirty();
    },
    [baseOnEdgesChange, markDirty],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      const sourceKind = nodes.find((node) => node.id === connection.source)?.data.kind;
      const transitionKind = transitionFromHandle(connection.sourceHandle, sourceKind);
      setEdges((items) =>
        addEdge<StudioEdge>(
          {
            ...connection,
            id: `edge-${globalThis.crypto?.randomUUID?.() ?? Date.now().toString(36)}`,
            label: connection.sourceHandle && connection.sourceHandle !== "next" ? connection.sourceHandle : undefined,
            data: { transitionKind, outcome: connection.sourceHandle ?? undefined },
          },
          items,
        ),
      );
      markDirty();
    },
    [markDirty, nodes, setEdges],
  );

  const onSelectionChange = useCallback(
    ({ nodes: selectedNodes, edges: selectedEdges }: OnSelectionChangeParams<StudioNode, StudioEdge>) => {
      selectedIds.current = {
        nodes: selectedNodes.map((node) => node.id),
        edges: selectedEdges.map((edge) => edge.id),
      };
      if (selectedNodes[0]) studio.selectGraphElement({ kind: "node", flowId, node: selectedNodes[0] });
      else if (selectedEdges[0]) studio.selectGraphElement({ kind: "edge", flowId, edge: selectedEdges[0] });
      else studio.selectGraphElement(null);
    },
    [flowId, studio.selectGraphElement],
  );

  useEffect(() => {
    const patch = studio.nodePatch;
    if (!patch || patch.flowId !== flowId) return;
    setNodes((items) =>
      items.map((node) =>
        node.id === patch.nodeId ? { ...node, data: { ...node.data, ...patch.patch } } : node,
      ),
    );
    markDirty();
  }, [flowId, markDirty, setNodes, studio.nodePatch]);

  useEffect(() => {
    const target = studio.graphNavigation;
    if (!target || target.flowId !== flowId) return;
    const node = nodes.find((item) => item.id === target.nodeId);
    if (!node) return;
    setNodes((items) => items.map((item) => ({ ...item, selected: item.id === target.nodeId })));
    studio.selectGraphElement({ kind: "node", flowId, node });
    void instance?.fitView({ nodes: [{ id: target.nodeId }], padding: 0.7, duration: 350 });
  }, [flowId, instance, nodes, setNodes, studio.graphNavigation, studio.selectGraphElement]);

  const save = useCallback(async () => {
    if (!projectId || !flow) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await studioApi.saveFlow(projectId, { ...flow, nodes, edges });
      setFlow(saved);
      setNodes(saved.nodes);
      setEdges(saved.edges);
      studio.markTabDirty(tabId, false);
      await studio.refreshProjectResources();
    } catch (reason) {
      setError(toApiError(reason).message);
    } finally {
      setSaving(false);
    }
  }, [edges, flow, nodes, projectId, setEdges, setNodes, studio.markTabDirty, studio.refreshProjectResources, tabId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void save();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [save]);

  function addNode(kind: FlowNodeKind) {
    const position = instance?.screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 }) ?? {
      x: 160 + nodes.length * 30,
      y: 100 + nodes.length * 24,
    };
    setNodes((items) => [
      ...items,
      { id: nextId(kind), type: "studioNode", position, data: { ...nodeDefaults[kind] } },
    ]);
    markDirty();
  }

  function deleteSelection() {
    const nodeIds = new Set(selectedIds.current.nodes);
    const edgeIds = new Set(selectedIds.current.edges);
    if (!nodeIds.size && !edgeIds.size) return;
    setNodes((items) => items.filter((node) => !nodeIds.has(node.id)));
    setEdges((items) =>
      items.filter(
        (edge) => !edgeIds.has(edge.id) && !nodeIds.has(edge.source) && !nodeIds.has(edge.target),
      ),
    );
    studio.selectGraphElement(null);
    markDirty();
  }

  const invalidNodeIds = useMemo(
    () => new Set(studio.issues.flatMap((issue) => (issue.entity?.flowId === flowId && issue.entity.nodeId ? [issue.entity.nodeId] : []))),
    [flowId, studio.issues],
  );
  const decoratedNodes = useMemo(
    () => nodes.map((node) => ({ ...node, className: invalidNodeIds.has(node.id) ? styles.invalidNode : node.className })),
    [invalidNodeIds, nodes],
  );

  if (loading) return <div className={styles.message}>Loading flow…</div>;
  if (!flow) return <div className={styles.message}>Unable to open flow: {error ?? "Unknown error"}</div>;

  return (
    <section className={styles.editor} aria-label={`Flow editor: ${flow.name}`}>
      <div className={styles.toolbar}>
        <div className={styles.nodeButtons}>
          {(Object.keys(nodeDefaults) as FlowNodeKind[]).map((kind) => (
            <button key={kind} onClick={() => addNode(kind)}>
              + {nodeDefaults[kind].title}
            </button>
          ))}
        </div>
        <span className={styles.spacer} />
        {error && <span className={styles.error}>{error}</span>}
        <button onClick={deleteSelection}>Delete</button>
        <button className={styles.save} onClick={() => void save()} disabled={saving}>
          {saving ? "Saving…" : "Save flow"}
        </button>
      </div>
      <div className={styles.canvas}>
        <ReactFlow<StudioNode, StudioEdge>
          nodes={decoratedNodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onSelectionChange={onSelectionChange}
          onInit={setInstance}
          fitView
          minZoom={0.2}
          maxZoom={2.5}
          deleteKeyCode={["Backspace", "Delete"]}
          multiSelectionKeyCode="Shift"
          selectionOnDrag
          panOnDrag={[1, 2]}
          defaultEdgeOptions={{ animated: false, style: { stroke: "#6a7c96", strokeWidth: 1.5 } }}
        >
          <Background color="#303949" gap={22} size={1} variant={BackgroundVariant.Dots} />
          <MiniMap pannable zoomable className={styles.minimap} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </section>
  );
}
