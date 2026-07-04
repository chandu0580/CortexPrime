"use client";

/**
 * MissionReplayGraph
 * Wraps the existing AgentGraph but overrides agent statuses from the
 * replay store instead of the live runtime store.
 *
 * Strategy: temporarily patch `useRuntimeStore` selectors via the override
 * prop on the GraphFrame component — we don't mutate the live store, instead
 * we build the ReactFlow nodes directly with replay data and render our own
 * ReactFlow instance.
 */

import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeProps,
  Handle,
  Position,
  BackgroundVariant,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { useReplayStore } from "@/store/replayStore";

// ── Agent identity (mirrors AgentGraph.tsx) ───────────────────────────────

const AGENT_META: Record<string, { role: string; color: string; bgMuted: string; border: string }> = {
  orchestrator: { role: "Mission Coordinator", color: "#82c0a4",  bgMuted: "rgba(130,192,164,0.07)",  border: "rgba(130,192,164,0.22)"  },
  planner:      { role: "Execution Planner",   color: "#4a8c70",  bgMuted: "rgba(74,140,112,0.07)",   border: "rgba(74,140,112,0.22)"   },
  research:     { role: "Knowledge Retrieval", color: "#4a8c70",  bgMuted: "rgba(74,140,112,0.07)",   border: "rgba(74,140,112,0.22)"   },
  critic:       { role: "Quality Assurance",   color: "#f9a825",  bgMuted: "rgba(217,119,6,0.07)",   border: "rgba(217,119,6,0.22)"   },
  optimizer:    { role: "Efficiency Engine",   color: "#96cead",  bgMuted: "rgba(124,58,237,0.07)",  border: "rgba(124,58,237,0.22)"  },
  memory:       { role: "Memory System",       color: "#737373",  bgMuted: "rgba(71,85,105,0.07)",   border: "rgba(71,85,105,0.22)"   },
};

const STATUS_COLOR: Record<string, string> = {
  active:     "#4a8c70",
  processing: "#82c0a4",
  idle:       "#d1d1d1",
  done:       "#4a8c70",
  error:      "#dc2626",
};

const STATUS_LABEL: Record<string, string> = {
  active:     "Active",
  processing: "Processing",
  idle:       "Standby",
  done:       "Done",
  error:      "Error",
};

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  orchestrator: { x: 220, y:  20 },
  planner:      { x:  40, y: 180 },
  research:     { x: 220, y: 180 },
  critic:       { x: 400, y: 180 },
  optimizer:    { x: 120, y: 340 },
  memory:       { x: 320, y: 340 },
};

// ── Custom node (same as AgentGraph) ─────────────────────────────────────

interface ReplayNodeData {
  agentId:  string;
  label:    string;
  status:   string;
  lastMessage: string;
}

function ReplayAgentNode({ data }: NodeProps<ReplayNodeData>) {
  const meta        = AGENT_META[data.agentId] ?? AGENT_META.memory;
  const statusColor = STATUS_COLOR[data.status] ?? STATUS_COLOR.idle;
  const statusLabel = STATUS_LABEL[data.status] ?? "Standby";
  const isActive    = data.status === "active" || data.status === "processing";

  return (
    <div
      style={{
        width: 200,
        background: "#ffffff",
        border: `1px solid ${isActive ? meta.border : "#dceee4"}`,
        borderRadius: 12,
        boxShadow: isActive
          ? `0 4px 16px rgba(0,0,0,0.06), 0 0 0 1px ${meta.border}`
          : "0 1px 4px rgba(0,0,0,0.05)",
        transition: "all 0.25s ease",
        overflow: "hidden",
      }}
    >
      <Handle type="target" position={Position.Top}    style={{ opacity: 0, pointerEvents: "none" }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: "none" }} />

      <div style={{ height: 3, background: isActive ? meta.color : "#dceee4", transition: "background 0.3s" }} />

      <div style={{ padding: "12px 14px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#1a1a1a", letterSpacing: "-0.01em" }}>
            {data.label}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: statusColor }} />
            <span style={{ fontSize: 10, fontWeight: 600, color: statusColor }}>
              {statusLabel}
            </span>
          </div>
        </div>

        <p style={{ fontSize: 10, color: "#a3a3a3", fontWeight: 500, marginBottom: data.lastMessage ? 8 : 0 }}>
          {meta.role}
        </p>

        {data.lastMessage && (
          <div style={{ background: isActive ? meta.bgMuted : "#f0f7f4", borderRadius: 6, padding: "5px 8px" }}>
            <p style={{ fontSize: 10, color: "#737373", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {data.lastMessage}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

const nodeTypes = { replayAgent: ReplayAgentNode };

// ── Main graph component ──────────────────────────────────────────────────

const AGENT_IDS = ["orchestrator", "planner", "research", "critic", "optimizer", "memory"];

const STATIC_EDGES: Edge[] = [
  { id: "orc-pln", source: "orchestrator", target: "planner"   },
  { id: "orc-res", source: "orchestrator", target: "research"  },
  { id: "orc-cri", source: "orchestrator", target: "critic"    },
  { id: "pln-opt", source: "planner",      target: "optimizer" },
  { id: "res-mem", source: "research",     target: "memory"    },
];

export function MissionReplayGraph() {
  const agentStates   = useReplayStore((s) => s.currentAgentStates);
  const graphSteps    = useReplayStore((s) => s.graphSteps);
  const currentSeq    = useReplayStore((s) => s.currentSequence);

  // Derive last message per agent from graphSteps up to currentSeq
  const lastMessages = useMemo<Record<string, string>>(() => {
    const msgs: Record<string, string> = {};
    for (let i = 0; i <= Math.min(currentSeq, graphSteps.length - 1); i++) {
      const step = graphSteps[i];
      if (step.agent) msgs[step.agent.toLowerCase().replace(/_agent$/, "").replace(/^agent_/, "")] = step.message;
    }
    return msgs;
  }, [graphSteps, currentSeq]);

  const nodes: Node[] = useMemo(
    () =>
      AGENT_IDS.map((id) => {
        const status = agentStates[id] ?? "idle";
        return {
          id,
          type: "replayAgent",
          position: NODE_POSITIONS[id],
          data: {
            agentId:     id,
            label:       id.charAt(0).toUpperCase() + id.slice(1),
            status,
            lastMessage: lastMessages[id] ?? "",
          } satisfies ReplayNodeData,
        };
      }),
    [agentStates, lastMessages]
  );

  const edges: Edge[] = useMemo(
    () =>
      STATIC_EDGES.map((e) => {
        const srcStatus = agentStates[e.source] ?? "idle";
        const isActive  = srcStatus === "active" || srcStatus === "processing";
        return {
          ...e,
          animated:    isActive,
          style: {
            stroke:      isActive ? "#82c0a4" : "#d1d1d1",
            strokeWidth: isActive ? 2 : 1.5,
            strokeDasharray: isActive ? undefined : "4 4",
          },
          markerEnd: {
            type:  MarkerType.ArrowClosed,
            color: isActive ? "#82c0a4" : "#d1d1d1",
          },
        };
      }),
    [agentStates]
  );

  return (
    <div
      style={{
        height: 500,
        borderRadius: 14,
        overflow: "hidden",
        border: "1px solid var(--border-default)",
        background: "#fafbfc",
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="rgba(130,192,164,0.12)" />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) => {
            const st = (n.data as ReplayNodeData).status;
            return STATUS_COLOR[st] ?? STATUS_COLOR.idle;
          }}
          style={{ background: "#f0f7f4", border: "1px solid #dceee4" }}
        />
      </ReactFlow>
    </div>
  );
}
