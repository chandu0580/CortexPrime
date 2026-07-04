"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import CortexShell from "@/components/layout/CortexShell";
import { MemorySearchPanel }   from "@/components/memory-explorer/MemorySearchPanel";
import { MemoryTimeline }      from "@/components/memory-explorer/MemoryTimeline";
import { MemoryGraph }         from "@/components/memory-explorer/MemoryGraph";
import { MemoryHeatmap }       from "@/components/memory-explorer/MemoryHeatmap";
import { MemoryMetadataPanel } from "@/components/memory-explorer/MemoryMetadataPanel";
import { useMemoryExplorerStore } from "@/store/memoryExplorerStore";

// ── Tab definition ────────────────────────────────────────────────────────

type View = "search" | "timeline" | "graph" | "heatmap";

const VIEWS: { id: View; label: string; description: string; icon: string }[] = [
  { id: "search",   label: "Search",   description: "Vector + text search across all memory stores", icon: "⌕"  },
  { id: "timeline", label: "Timeline", description: "Memories grouped chronologically by date",      icon: "↕"  },
  { id: "graph",    label: "Graph",    description: "Memory concept relationship graph",              icon: "◎"  },
  { id: "heatmap",  label: "Heatmap",  description: "Most frequently retrieved memories",            icon: "▦"  },
];

// ── Main page ─────────────────────────────────────────────────────────────

export default function MemoryExplorerPage() {
  const activeView   = useMemoryExplorerStore((s) => s.activeView);
  const setView      = useMemoryExplorerStore((s) => s.setActiveView);
  const stats        = useMemoryExplorerStore((s) => s.stats);
  const loadTimeline = useMemoryExplorerStore((s) => s.loadTimeline);
  const loadGraph    = useMemoryExplorerStore((s) => s.loadGraph);
  const loadStats    = useMemoryExplorerStore((s) => s.loadStats);

  // Load data on first render
  useEffect(() => {
    loadStats();
    loadTimeline();
  }, [loadStats, loadTimeline]);

  // Lazy-load graph when user switches to it
  function handleViewChange(v: View) {
    setView(v);
    if (v === "graph") loadGraph();
    if (v === "heatmap") loadStats();
    if (v === "timeline") loadTimeline();
  }

  const totalMemories = stats?.total ?? null;

  return (
    <CortexShell title="Memory Explorer">
      <div
        style={{
          display:       "flex",
          flexDirection: "column",
          height:        "100%",
          gap:           14,
        }}
      >
        {/* ── Page header ─────────────────────────────────────────── */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1
              style={{
                margin:         0,
                fontSize:       "var(--font-size-2xl)",
                fontWeight:     800,
                color:          "var(--text-primary)",
                letterSpacing:  "-0.03em",
                lineHeight:     1.1,
              }}
            >
              Memory Explorer
            </h1>
            <p style={{ margin: "4px 0 0", fontSize: "var(--font-size-sm)", color: "var(--text-muted)" }}>
              Search, visualise, and inspect memories across all cognitive stores
            </p>
          </div>

          {/* Total count badge */}
          {totalMemories !== null && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{
                display:      "flex",
                flexDirection: "column",
                alignItems:   "flex-end",
                gap:          1,
                padding:      "6px 14px",
                borderRadius: "var(--radius-lg)",
                background:   "rgba(130,192,164,0.06)",
                border:       "1px solid rgba(130,192,164,0.15)",
              }}
            >
              <span
                className="label-mono"
                style={{ fontSize: "var(--font-size-2xl)", fontWeight: 800, color: "var(--accent)", lineHeight: 1 }}
              >
                {totalMemories.toLocaleString()}
              </span>
              <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                total memories
              </span>
            </motion.div>
          )}
        </div>

        {/* ── View tabs ───────────────────────────────────────────── */}
        <div
          style={{
            display:      "flex",
            gap:          4,
            padding:      "4px",
            background:   "var(--border-subtle)",
            borderRadius: "var(--radius-lg)",
            width:        "fit-content",
          }}
        >
          {VIEWS.map((v) => (
            <motion.button
              key={v.id}
              onClick={() => handleViewChange(v.id)}
              title={v.description}
              style={{
                display:      "flex",
                alignItems:   "center",
                gap:          6,
                padding:      "6px 14px",
                borderRadius: "var(--radius-md)",
                border:       "none",
                background:   activeView === v.id ? "var(--surface)" : "transparent",
                color:        activeView === v.id ? "var(--text-primary)" : "var(--text-muted)",
                fontSize:     "var(--font-size-sm)",
                fontWeight:   activeView === v.id ? 600 : 500,
                cursor:       "pointer",
                boxShadow:    activeView === v.id ? "var(--shadow-sm)" : "none",
                transition:   "all 0.12s",
                whiteSpace:   "nowrap",
              }}
              whileHover={activeView !== v.id ? { color: "var(--text-secondary)" } : {}}
            >
              <span style={{ fontSize: 12 }}>{v.icon}</span>
              {v.label}
            </motion.button>
          ))}
        </div>

        {/* ── Main layout: content + metadata sidebar ──────────────── */}
        <div
          style={{
            display:             "grid",
            gridTemplateColumns: "1fr 280px",
            gap:                 14,
            flex:                1,
            minHeight:           0,
          }}
        >
          {/* Left: active view */}
          <div
            className="surface-panel"
            style={{ display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}
          >
            <AnimatePresence mode="wait">
              <motion.div
                key={activeView}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.18 }}
                style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}
              >
                {activeView === "search"   && <MemorySearchPanel />}
                {activeView === "timeline" && <MemoryTimeline />}
                {activeView === "graph"    && <MemoryGraph />}
                {activeView === "heatmap"  && <MemoryHeatmap />}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Right: metadata panel */}
          <div className="surface-panel" style={{ overflow: "hidden" }}>
            <p style={{ margin: "0 0 10px", fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Memory Details
            </p>
            <div style={{ flex: 1, overflowY: "auto" }} className="cortex-scroll">
              <MemoryMetadataPanel />
            </div>
          </div>
        </div>

        {/* ── Quick stats strip ────────────────────────────────────── */}
        {stats && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              display:      "flex",
              alignItems:   "center",
              gap:          16,
              padding:      "8px 14px",
              borderRadius: "var(--radius-md)",
              background:   "var(--border-subtle)",
              flexWrap:     "wrap",
            }}
          >
            {Object.entries(stats.by_type)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <div key={type} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <div
                    style={{
                      width:        6,
                      height:       6,
                      borderRadius: "50%",
                      background:   TYPE_COLORS[type] ?? "var(--text-muted)",
                    }}
                  />
                  <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                    {type}
                  </span>
                  <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", fontWeight: 600 }}>
                    {count.toLocaleString()}
                  </span>
                </div>
              ))}

            {Object.keys(stats.by_agent).length > 0 && (
              <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginLeft: "auto" }}>
                {Object.keys(stats.by_agent).length} active agents
              </span>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  );
}

// ── Type colors (also used in the stats strip) ───────────────────────────

const TYPE_COLORS: Record<string, string> = {
  episodic:   "var(--agent-planner)",
  semantic:   "var(--agent-research)",
  reflection: "var(--agent-critic)",
  voice:      "var(--agent-optimizer)",
  browser:    "var(--agent-memory)",
  workspace:  "var(--agent-orchestrator)",
};
