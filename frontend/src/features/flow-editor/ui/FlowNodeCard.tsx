import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { StudioNode } from "../../../entities/flow/model/types";
import styles from "./FlowNodeCard.module.css";

const kindLabels: Record<StudioNode["data"]["kind"], string> = {
  start: "Start",
  send_message: "Send Message",
  ask_input: "Ask Input",
  choice: "Choice",
  action: "Action",
  condition: "Condition",
  end: "End",
};

function outputs(node: StudioNode): { id: string; label?: string }[] {
  if (node.data.kind === "action") return [{ id: "success", label: "success" }, { id: "error", label: "error" }];
  if (node.data.kind === "ask_input") return [{ id: "success", label: "valid" }, { id: "error", label: "error" }];
  if (node.data.kind === "condition") return [{ id: "true", label: "true" }, { id: "false", label: "false" }];
  if (node.data.kind === "choice" && node.data.choices?.length) {
    return node.data.choices.map((choice) => ({ id: choice.id, label: choice.label }));
  }
  return node.data.kind === "end" ? [] : [{ id: "next" }];
}

function summary(node: StudioNode): string {
  if (node.data.kind === "ask_input") return node.data.variableName || "Select a variable";
  if (node.data.kind === "action") return node.data.actionName || "Select an action";
  if (node.data.kind === "condition") {
    return node.data.conditionVariable
      ? `${node.data.conditionVariable} ${node.data.conditionOperator ?? "truthy"}`
      : "Set a condition";
  }
  return node.data.text || node.data.title || kindLabels[node.data.kind];
}

export function FlowNodeCard(props: NodeProps<StudioNode>) {
  const node = props as unknown as StudioNode;
  const nodeOutputs = outputs(node);
  return (
    <div
      className={`${styles.node} ${styles[node.data.kind]} ${props.selected ? styles.selected : ""}`}
      data-node-kind={node.data.kind}
    >
      {node.data.kind !== "start" && <Handle type="target" position={Position.Left} />}
      <div className={styles.header}>
        <span className={styles.kindIcon}>{kindLabels[node.data.kind].slice(0, 1)}</span>
        <strong>{node.data.title || kindLabels[node.data.kind]}</strong>
      </div>
      <div className={styles.summary}>{summary(node)}</div>
      {nodeOutputs.map((output, index) => (
        <div className={styles.output} key={output.id} style={{ top: `${42 + index * 22}px` }}>
          {output.label && <span>{output.label}</span>}
          <Handle id={output.id} type="source" position={Position.Right} />
        </div>
      ))}
    </div>
  );
}
