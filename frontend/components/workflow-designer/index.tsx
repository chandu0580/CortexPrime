'use client';

import { useCallback, useRef, useState } from 'react';
import type { DragEvent, ReactNode } from 'react';

export type NodeType = 'start' | 'end' | 'task' | 'condition' | 'parallel' | 'approval' | 'sub_workflow' | 'wait' | 'tool';

export interface WorkflowNode {
  id: string;
  type: NodeType;
  label: string;
  config?: Record<string, unknown>;
  position: { x: number; y: number };
}

export interface WorkflowEdge {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  label?: string;
  condition?: string;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  tags?: string[];
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

interface WorkflowDesignerProps {
  workflow: Workflow;
  onWorkflowChange: (workflow: Workflow) => void;
}

const NODE_COLORS: Record<NodeType, string> = {
  start: '#22c55e',
  end: '#ef4444',
  task: '#3b82f6',
  condition: '#f59e0b',
  parallel: '#8b5cf6',
  approval: '#ec4899',
  sub_workflow: '#06b6d4',
  wait: '#f97316',
  tool: '#6366f1',
};

const NODE_LABELS: Record<NodeType, string> = {
  start: 'Start',
  end: 'End',
  task: 'Task',
  condition: 'Condition',
  parallel: 'Parallel',
  approval: 'Approval',
  sub_workflow: 'Sub-workflow',
  wait: 'Wait',
  tool: 'Tool',
};

const SIDEBAR_NODES: NodeType[] = ['task', 'condition', 'parallel', 'approval', 'sub_workflow', 'wait', 'tool'];

export function WorkflowDesigner({ workflow, onWorkflowChange }: WorkflowDesignerProps) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const handleCanvasDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const nodeType = e.dataTransfer.getData('nodeType') as NodeType;
      if (!nodeType || !canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const newNode: WorkflowNode = {
        id: crypto.randomUUID(),
        type: nodeType,
        label: NODE_LABELS[nodeType],
        position: { x: e.clientX - rect.left - 60, y: e.clientY - rect.top - 20 },
      };
      onWorkflowChange({
        ...workflow,
        nodes: [...workflow.nodes, newNode],
      });
    },
    [workflow, onWorkflowChange],
  );

  const handleNodeDragStart = (e: DragEvent<HTMLDivElement>, nodeId: string) => {
    setDragging(nodeId);
    const node = workflow.nodes.find((n) => n.id === nodeId);
    if (node) {
      setDragOffset({ x: e.clientX - node.position.x, y: e.clientY - node.position.y });
    }
  };

  const handleNodeDragEnd = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      if (!dragging || !canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const updatedNodes = workflow.nodes.map((n) =>
        n.id === dragging
          ? { ...n, position: { x: e.clientX - dragOffset.x - rect.left, y: e.clientY - dragOffset.y - rect.top } }
          : n,
      );
      onWorkflowChange({ ...workflow, nodes: updatedNodes });
      setDragging(null);
    },
    [dragging, dragOffset, workflow, onWorkflowChange],
  );

  const handleSidebarDragStart = (e: DragEvent<HTMLDivElement>, nodeType: NodeType) => {
    e.dataTransfer.setData('nodeType', nodeType);
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleDeleteNode = (nodeId: string) => {
    onWorkflowChange({
      ...workflow,
      nodes: workflow.nodes.filter((n) => n.id !== nodeId),
      edges: workflow.edges.filter((e) => e.sourceNodeId !== nodeId && e.targetNodeId !== nodeId),
    });
  };

  return (
    <div style={{ display: 'flex', height: '100%', fontFamily: 'system-ui, sans-serif' }}>
      <div
        style={{
          width: 200,
          borderRight: '1px solid var(--color-border, #e5e7eb)',
          padding: 16,
          background: 'var(--color-surface, #f9fafb)',
        }}
      >
        <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 600, color: 'var(--color-text, #111827)' }}>
          Node Palette
        </h3>
        {SIDEBAR_NODES.map((nodeType) => (
          <div
            key={nodeType}
            draggable
            onDragStart={(e) => handleSidebarDragStart(e, nodeType)}
            style={{
              padding: '8px 12px',
              marginBottom: 8,
              borderRadius: 6,
              cursor: 'grab',
              fontSize: 13,
              color: '#fff',
              background: NODE_COLORS[nodeType],
              userSelect: 'none',
            }}
          >
            {NODE_LABELS[nodeType]}
          </div>
        ))}
      </div>

      <div
        ref={canvasRef}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleCanvasDrop}
        style={{
          flex: 1,
          position: 'relative',
          background: 'var(--color-canvas, #f3f4f6)',
          overflow: 'hidden',
        }}
      >
        <svg
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        >
          {workflow.edges.map((edge) => {
            const source = workflow.nodes.find((n) => n.id === edge.sourceNodeId);
            const target = workflow.nodes.find((n) => n.id === edge.targetNodeId);
            if (!source || !target) return null;
            return (
              <line
                key={edge.id}
                x1={source.position.x + 60}
                y1={source.position.y + 20}
                x2={target.position.x + 60}
                y2={target.position.y + 20}
                stroke="#9ca3af"
                strokeWidth={2}
                strokeDasharray={edge.condition ? '4 4' : undefined}
              />
            );
          })}
        </svg>

        {workflow.nodes.map((node) => (
          <div
            key={node.id}
            draggable
            onDragStart={(e) => handleNodeDragStart(e, node.id)}
            onDragEnd={handleNodeDragEnd}
            style={{
              position: 'absolute',
              left: node.position.x,
              top: node.position.y,
              width: 120,
              padding: '10px 12px',
              borderRadius: 8,
              background: NODE_COLORS[node.type],
              color: '#fff',
              fontSize: 12,
              fontWeight: 500,
              cursor: 'grab',
              textAlign: 'center',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              zIndex: dragging === node.id ? 100 : 1,
              opacity: dragging === node.id ? 0.7 : 1,
            }}
          >
            <div style={{ fontSize: 10, opacity: 0.8, marginBottom: 2 }}>{node.type}</div>
            <div>{node.label}</div>
            <button
              onClick={() => handleDeleteNode(node.id)}
              style={{
                position: 'absolute',
                top: -6,
                right: -6,
                width: 18,
                height: 18,
                borderRadius: '50%',
                border: 'none',
                background: 'rgba(0,0,0,0.5)',
                color: '#fff',
                fontSize: 10,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              ×
            </button>
          </div>
        ))}

        {workflow.nodes.length === 0 && (
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              color: '#9ca3af',
              fontSize: 14,
              textAlign: 'center',
            }}
          >
            Drag nodes from the palette to start building your workflow
          </div>
        )}
      </div>
    </div>
  );
}
