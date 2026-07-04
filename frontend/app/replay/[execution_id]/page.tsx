"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import CortexShell from "@/components/layout/CortexShell";
import { MissionReplayGraph } from "@/components/replay/MissionReplayGraph";
import { MissionTimeline } from "@/components/replay/MissionTimeline";
import { PlaybackControls } from "@/components/replay/PlaybackControls";
import { AgentExecutionPanel } from "@/components/replay/AgentExecutionPanel";
import { ToolExecutionPanel } from "@/components/replay/ToolExecutionPanel";
import { MemoryRetrievalPanel } from "@/components/replay/MemoryRetrievalPanel";
import { useReplayStore } from "@/store/replayStore";

// ── Tab definition ────────────────────────────────────────────────────────

type PanelTab = "agents" | "tools" | "memory";

const TABS: { id: PanelTab; label: string }[] = [
  { id: "agents", label: "Agents" },
  { id: "tools",  label: "Tools"  },
  { id: "memory", label: "Memory" },
];

// ── Main page ─────────────────────────────────────────────────────────────

export default function ReplayPage() {
  const params      = useParams<{ execution_id: string }>();
  const router      = useRouter();
  const executionId = params.execution_id;

  const loadReplay  = useReplayStore((s) => s.loadReplay);
  const summary     = useReplayStore((s) => s.summary);
  const isLoading   = useReplayStore((s) => s.isLoading);
  const error       = useReplayStore((s) => s.error);
  const reset       = useReplayStore((s) => s.reset);

  const [activeTab, setActiveTab] = useState<PanelTab>("agents");

  // Load replay on mount
  useEffect(() => {
    if (executionId) {
      loadReplay(executionId);
    }
    return () => { reset(); };
  }, [executionId, loadReplay, reset]);

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <CortexShell title="Mission Replay">
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          height: "100%",
          gap: 12,
          padding: "0 0 16px",
        }}
      >
        {/* ── Header bar ─────────────────────────────────────────────── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "4px 0",
          }}
        >
          <button
            onClick={() => router.back()}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              padding: "4px 10px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-default)",
              background: "transparent",
              color: "var(--text-secondary)",
              fontSize: "var(--font-size-sm)",
              cursor: "pointer",
            }}
          >
            ← Back
          </button>

          <div style={{ flex: 1, minWidth: 0 }}>
            <h1
              style={{
                margin: 0,
                fontSize: "var(--font-size-lg)",
                fontWeight: 700,
                color: "var(--text-primary)",
                letterSpacing: "-0.02em",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              Mission Replay
            </h1>
            <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-muted)", fontFamily: "var(--font-geist-mono)", marginTop: 1 }}>
              {executionId}
            </p>
          </div>

          {/* Summary badges */}
          {summary && (
            <div style={{ display: "flex", gap: 8 }}>
              {summary.total_events != null && (
                <StatBadge label="Events" value={String(summary.total_events)} />
              )}
              {summary.duration_ms != null && (
                <StatBadge label="Duration" value={`${(summary.duration_ms / 1000).toFixed(1)}s`} />
              )}
              {summary.avg_latency_ms != null && (
                <StatBadge label="Avg Latency" value={`${summary.avg_latency_ms.toFixed(0)}ms`} />
              )}
              {summary.is_complete != null && (
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "3px 10px",
                    borderRadius: "var(--radius-pill)",
                    fontSize: "var(--font-size-xs)",
                    fontWeight: 600,
                    background: summary.is_complete ? "rgba(5,150,105,0.08)" : "rgba(217,119,6,0.08)",
                    color: summary.is_complete ? "var(--color-success)" : "var(--color-warning)",
                    border: `1px solid ${summary.is_complete ? "rgba(5,150,105,0.2)" : "rgba(217,119,6,0.2)"}`,
                  }}
                >
                  <div
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      background: "currentColor",
                    }}
                  />
                  {summary.is_complete ? "Complete" : "In Progress"}
                </span>
              )}
            </div>
          )}
        </div>

        {/* ── Loading / Error states ─────────────────────────────────── */}
        <AnimatePresence>
          {isLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "48px 0",
                color: "var(--text-muted)",
                fontSize: "var(--font-size-sm)",
                gap: 10,
              }}
            >
              <LoadingSpinner />
              Loading replay data…
            </motion.div>
          )}
          {error && !isLoading && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              style={{
                padding: "12px 16px",
                borderRadius: "var(--radius-md)",
                background: "rgba(220,38,38,0.06)",
                border: "1px solid rgba(220,38,38,0.2)",
                color: "var(--color-error)",
                fontSize: "var(--font-size-sm)",
              }}
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Main layout (only when data is loaded) ────────────────── */}
        {!isLoading && !error && summary?.found && (
          <>
            {/* Playback controls bar */}
            <PlaybackControls />

            {/* 2-column layout: graph (left) + side panels (right) */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 340px",
                gap: 12,
                flex: 1,
                minHeight: 0,
              }}
            >
              {/* Left: Agent graph */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                {/* Graph */}
                <div className="surface-panel" style={{ padding: 0, overflow: "hidden", borderRadius: "var(--radius-xl)" }}>
                  <div
                    style={{
                      padding: "12px 16px",
                      borderBottom: "1px solid var(--border-subtle)",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <span style={{ fontSize: "var(--font-size-sm)", fontWeight: 600, color: "var(--text-primary)" }}>
                      Agent Graph
                    </span>
                    <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                      Replay mode — animated by recorded timestamps
                    </span>
                  </div>
                  <MissionReplayGraph />
                </div>

                {/* Timeline */}
                <div className="surface-panel" style={{ flex: 1, minHeight: 0 }}>
                  <div
                    style={{
                      marginBottom: 12,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span style={{ fontSize: "var(--font-size-sm)", fontWeight: 600, color: "var(--text-primary)" }}>
                      Mission Timeline
                    </span>
                    {summary?.agents && (
                      <div style={{ display: "flex", gap: 4 }}>
                        {summary.agents.slice(0, 4).map((a) => (
                          <span
                            key={a}
                            style={{
                              fontSize: "var(--font-size-xs)",
                              padding: "1px 6px",
                              borderRadius: "var(--radius-pill)",
                              background: "var(--border-subtle)",
                              color: "var(--text-muted)",
                            }}
                          >
                            {a}
                          </span>
                        ))}
                        {(summary.agents.length ?? 0) > 4 && (
                          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                            +{summary.agents.length - 4}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <MissionTimeline />
                </div>
              </div>

              {/* Right: Side panels */}
              <div className="surface-panel" style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
                {/* Tabs */}
                <div
                  style={{
                    display: "flex",
                    gap: 2,
                    marginBottom: 14,
                    padding: "3px",
                    background: "var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  {TABS.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      style={{
                        flex: 1,
                        padding: "5px 0",
                        borderRadius: "var(--radius-sm)",
                        border: "none",
                        background: activeTab === tab.id ? "#ffffff" : "transparent",
                        color: activeTab === tab.id ? "var(--text-primary)" : "var(--text-muted)",
                        fontSize: "var(--font-size-xs)",
                        fontWeight: activeTab === tab.id ? 600 : 500,
                        cursor: "pointer",
                        boxShadow: activeTab === tab.id ? "var(--shadow-xs)" : "none",
                        transition: "all 0.12s",
                      }}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Panel content */}
                <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }} className="cortex-scroll">
                  <AnimatePresence mode="wait">
                    {activeTab === "agents" && (
                      <motion.div key="agents" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <AgentExecutionPanel />
                      </motion.div>
                    )}
                    {activeTab === "tools" && (
                      <motion.div key="tools" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <ToolExecutionPanel />
                      </motion.div>
                    )}
                    {activeTab === "memory" && (
                      <motion.div key="memory" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <MemoryRetrievalPanel />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Not found state */}
        {!isLoading && !error && summary && !summary.found && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              padding: "64px 0",
              color: "var(--text-muted)",
            }}
          >
            <span style={{ fontSize: 32 }}>⌀</span>
            <p style={{ margin: 0, fontSize: "var(--font-size-sm)", fontWeight: 500, color: "var(--text-secondary)" }}>
              No replay data found for this execution
            </p>
            <p style={{ margin: 0, fontSize: "var(--font-size-xs)" }}>
              {executionId}
            </p>
          </div>
        )}
      </div>
    </CortexShell>
  );
}

// ── Helper components ─────────────────────────────────────────────────────

function StatBadge({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "3px 10px",
        borderRadius: "var(--radius-md)",
        background: "var(--border-subtle)",
        border: "1px solid var(--border-default)",
      }}
    >
      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>{label}</span>
      <span className="label-mono" style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--text-primary)" }}>
        {value}
      </span>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
      style={{
        width: 16,
        height: 16,
        border: "2px solid var(--border-default)",
        borderTopColor: "var(--accent)",
        borderRadius: "50%",
      }}
    />
  );
}
