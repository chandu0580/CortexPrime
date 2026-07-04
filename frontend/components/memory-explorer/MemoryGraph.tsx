"use client";

import { useEffect, useRef, useMemo, useCallback } from "react";
import { motion } from "framer-motion";
import { useMemoryExplorerStore } from "@/store/memoryExplorerStore";
import { GraphNode, GraphEdge } from "@/services/memoryExplorerService";

// ── Layout helpers ────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  episodic:   "#4a8c70",
  semantic:   "#4a8c70",
  reflection: "#f9a825",
  voice:      "#96cead",
  browser:    "#737373",
  workspace:  "#82c0a4",
};

function typeColor(mt: string) {
  return TYPE_COLORS[mt] ?? "#a3a3a3";
}

interface LayoutNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
}

function buildLayout(nodes: GraphNode[], edges: GraphEdge[], w: number, h: number): LayoutNode[] {
  if (!nodes.length) return [];
  const cx = w / 2;
  const cy = h / 2;
  const angleStep = (2 * Math.PI) / nodes.length;

  return nodes.map((n, i) => {
    // Type-specific ring radius
    const ringR =
      n.memory_type === "semantic"   ? h * 0.28 :
      n.memory_type === "episodic"   ? h * 0.40 :
      n.memory_type === "reflection" ? h * 0.34 :
      h * 0.42;

    const angle  = angleStep * i;
    const jitter = (Math.random() - 0.5) * 30;
    const r      = Math.min(4 + n.weight * 3, 14);

    return {
      ...n,
      x:      cx + Math.cos(angle) * (ringR + jitter),
      y:      cy + Math.sin(angle) * (ringR + jitter),
      vx:     0,
      vy:     0,
      radius: r,
    };
  });
}

// ── Canvas renderer ───────────────────────────────────────────────────────

function drawGraph(
  ctx:        CanvasRenderingContext2D,
  nodes:      LayoutNode[],
  edges:      GraphEdge[],
  hoveredId:  string | null,
  selectedId: string | null,
  dpr:        number,
) {
  const { width: w, height: h } = ctx.canvas;
  ctx.clearRect(0, 0, w, h);

  // Map id → node
  const map = new Map<string, LayoutNode>(nodes.map((n) => [n.id, n]));

  // Draw edges
  ctx.lineWidth = 1;
  for (const e of edges) {
    const s = map.get(e.source);
    const t = map.get(e.target);
    if (!s || !t) continue;
    const isActive = hoveredId === s.id || hoveredId === t.id;
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.strokeStyle = isActive ? "rgba(130,192,164,0.4)" : "rgba(148,163,184,0.18)";
    ctx.lineWidth   = isActive ? 1.5 : 1;
    ctx.stroke();
  }

  // Draw nodes
  for (const n of nodes) {
    const color    = typeColor(n.memory_type);
    const isHover  = n.id === hoveredId;
    const isSel    = n.id === selectedId;
    const r        = n.radius + (isHover ? 3 : 0) + (isSel ? 2 : 0);

    // Glow
    if (isHover || isSel) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 5, 0, 2 * Math.PI);
      const grad = ctx.createRadialGradient(n.x, n.y, r, n.x, n.y, r + 6);
      grad.addColorStop(0, color + "55");
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.fill();
    }

    // Node circle
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
    ctx.fillStyle   = isHover || isSel ? color : color + "cc";
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth   = isSel ? 2 : 1;
    ctx.fill();
    ctx.stroke();

    // Label for hovered/selected
    if ((isHover || isSel) && n.label) {
      ctx.font      = `${11 * dpr}px -apple-system, BlinkMacSystemFont, sans-serif`;
      ctx.fillStyle = "#1a1a1a";
      ctx.textAlign = "center";
      ctx.fillText(n.label.slice(0, 24), n.x, n.y - r - 5);
    }
  }
}

// ── Main component ────────────────────────────────────────────────────────

export function MemoryGraph() {
  const nodes      = useMemoryExplorerStore((s) => s.graphNodes);
  const edges      = useMemoryExplorerStore((s) => s.graphEdges);
  const isLoading  = useMemoryExplorerStore((s) => s.isGraphLoading);
  const setSelected = useMemoryExplorerStore((s) => s.setSelectedRecord);
  const selectedRecord = useMemoryExplorerStore((s) => s.selectedRecord);

  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const layoutRef    = useRef<LayoutNode[]>([]);
  const hoveredRef   = useRef<string | null>(null);
  const rafRef       = useRef<number>(0);

  // Build layout once when nodes arrive
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !nodes.length) return;
    const { width: w, height: h } = el.getBoundingClientRect();
    layoutRef.current = buildLayout(nodes, edges, w, h);
  }, [nodes, edges]);

  // Canvas render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;

    function resize() {
      const el = containerRef.current;
      if (!el || !canvas) return;
      const { width: w, height: h } = el.getBoundingClientRect();
      canvas.width  = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width  = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx!.scale(dpr, dpr);
    }

    function render() {
      resize();
      drawGraph(ctx!, layoutRef.current, edges, hoveredRef.current, selectedRecord?.id ?? null, dpr);
      rafRef.current = requestAnimationFrame(render);
    }

    rafRef.current = requestAnimationFrame(render);
    return () => cancelAnimationFrame(rafRef.current);
  }, [edges, selectedRecord]);

  // Mouse hit-test
  const hitTest = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    for (const n of layoutRef.current) {
      const dx = mx - n.x;
      const dy = my - n.y;
      if (dx * dx + dy * dy <= (n.radius + 4) ** 2) return n;
    }
    return null;
  }, []);

  function onMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const hit = hitTest(e);
    hoveredRef.current = hit?.id ?? null;
    if (canvasRef.current) {
      canvasRef.current.style.cursor = hit ? "pointer" : "default";
    }
  }

  function onClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const hit = hitTest(e);
    if (!hit) { setSelected(null); return; }
    // Find full MemoryRecord-compatible object from store search results
    // For the graph we just show the node label in the metadata panel
    setSelected({
      id:               hit.id,
      memory_type:      hit.memory_type as never,
      content:          hit.label,
      agent:            hit.agent,
      concept:          hit.memory_type === "semantic" ? hit.label : null,
      event_type:       null,
      session_id:       null,
      mission_id:       null,
      source:           null,
      similarity_score: null,
      confidence:       hit.weight,
      retrieval_count:  0,
      created_at:       hit.created_at,
      last_retrieved:   null,
      metadata:         {},
    });
  }

  // Legend
  const legend = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of nodes) counts[n.memory_type] = (counts[n.memory_type] ?? 0) + 1;
    return counts;
  }, [nodes]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, height: "100%" }}>
      {/* Legend */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {Object.entries(legend).map(([t, n]) => (
          <div key={t} style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: typeColor(t) }} />
            <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
              {t} ({n})
            </span>
          </div>
        ))}
        {nodes.length > 0 && (
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginLeft: "auto" }}>
            {nodes.length} nodes · {edges.length} edges
          </span>
        )}
      </div>

      {/* Canvas */}
      <div
        ref={containerRef}
        style={{
          flex:         1,
          borderRadius: "var(--radius-lg)",
          background:   "#fafbfc",
          border:       "1px solid var(--border-subtle)",
          position:     "relative",
          overflow:     "hidden",
          minHeight:    300,
        }}
      >
        {isLoading && (
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, color: "var(--text-muted)", fontSize: "var(--font-size-sm)" }}>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
              style={{ width: 14, height: 14, border: "2px solid var(--border-default)", borderTopColor: "var(--accent)", borderRadius: "50%" }}
            />
            Building graph…
          </div>
        )}

        {!isLoading && nodes.length === 0 && (
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8, color: "var(--text-muted)" }}>
            <span style={{ fontSize: 28 }}>◎</span>
            <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>No memory graph data</p>
          </div>
        )}

        <canvas
          ref={canvasRef}
          onMouseMove={onMouseMove}
          onClick={onClick}
          style={{ display: nodes.length > 0 ? "block" : "none", width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
}
