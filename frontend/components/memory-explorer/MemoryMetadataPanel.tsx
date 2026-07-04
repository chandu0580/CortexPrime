"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useMemoryExplorerStore } from "@/store/memoryExplorerStore";
import { MemoryRecord } from "@/services/memoryExplorerService";

// ── Helpers ───────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  episodic:   "var(--agent-planner)",
  semantic:   "var(--agent-research)",
  reflection: "var(--agent-critic)",
  voice:      "var(--agent-optimizer)",
  browser:    "var(--agent-memory)",
  workspace:  "var(--agent-orchestrator)",
};

function typeColor(mt: string) {
  return TYPE_COLORS[mt] ?? "var(--text-muted)";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function scoreDisplay(score: number | null): { label: string; color: string } | null {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const color =
    score > 0.8 ? "var(--color-success)" :
    score > 0.5 ? "var(--accent)" :
    "var(--color-warning)";
  return { label: `${pct}%`, color };
}

// ── Row helper ────────────────────────────────────────────────────────────

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        display:       "grid",
        gridTemplateColumns: "100px 1fr",
        gap:           8,
        padding:       "5px 0",
        borderBottom:  "1px solid var(--border-subtle)",
        alignItems:    "start",
      }}
    >
      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", fontWeight: 500, paddingTop: 1 }}>
        {label}
      </span>
      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-primary)", wordBreak: "break-word", lineHeight: 1.5 }}>
        {children}
      </span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export function MemoryMetadataPanel() {
  const record    = useMemoryExplorerStore((s) => s.selectedRecord);
  const setRecord = useMemoryExplorerStore((s) => s.setSelectedRecord);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <AnimatePresence mode="wait">
        {!record ? (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              display:         "flex",
              flexDirection:   "column",
              alignItems:      "center",
              justifyContent:  "center",
              gap:             10,
              flex:            1,
              color:           "var(--text-muted)",
              padding:         "32px 16px",
            }}
          >
            <div style={{ fontSize: 28, opacity: 0.3 }}>◉</div>
            <p style={{ margin: 0, fontSize: "var(--font-size-sm)", fontWeight: 500, color: "var(--text-secondary)", textAlign: "center" }}>
              Select a memory to inspect
            </p>
            <p style={{ margin: 0, fontSize: "var(--font-size-xs)", textAlign: "center", maxWidth: 200, lineHeight: 1.5 }}>
              Click any result, timeline entry, graph node, or heatmap cell
            </p>
          </motion.div>
        ) : (
          <motion.div
            key={record.id}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ duration: 0.18 }}
            style={{ display: "flex", flexDirection: "column", gap: 0, flex: 1 }}
          >
            {/* Header */}
            <div
              style={{
                display:       "flex",
                alignItems:    "center",
                gap:           8,
                marginBottom:  12,
              }}
            >
              {/* Type badge */}
              <span
                style={{
                  fontSize:     "var(--font-size-xs)",
                  fontWeight:   600,
                  padding:      "2px 9px",
                  borderRadius: "var(--radius-pill)",
                  background:   `${typeColor(record.memory_type)}15`,
                  color:        typeColor(record.memory_type),
                  border:       `1px solid ${typeColor(record.memory_type)}33`,
                }}
              >
                {record.memory_type}
              </span>

              {/* Dismiss */}
              <button
                onClick={() => setRecord(null)}
                style={{
                  marginLeft:   "auto",
                  width:        24,
                  height:       24,
                  borderRadius: "var(--radius-sm)",
                  border:       "1px solid var(--border-default)",
                  background:   "transparent",
                  color:        "var(--text-muted)",
                  cursor:       "pointer",
                  fontSize:     12,
                  display:      "flex",
                  alignItems:   "center",
                  justifyContent: "center",
                }}
              >
                ✕
              </button>
            </div>

            {/* Content */}
            <div
              style={{
                padding:      "10px 12px",
                borderRadius: "var(--radius-md)",
                background:   "var(--border-subtle)",
                marginBottom: 12,
              }}
            >
              <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--text-primary)", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {record.content}
              </p>
            </div>

            {/* Metadata table */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              {record.concept && (
                <MetaRow label="Concept">
                  <strong>{record.concept}</strong>
                </MetaRow>
              )}

              {record.agent && (
                <MetaRow label="Agent">
                  <span style={{ color: typeColor(record.memory_type), fontWeight: 500 }}>
                    {record.agent}
                  </span>
                </MetaRow>
              )}

              {record.event_type && (
                <MetaRow label="Event Type">
                  {record.event_type}
                </MetaRow>
              )}

              {record.source && (
                <MetaRow label="Source">
                  {record.source}
                </MetaRow>
              )}

              {record.mission_id && (
                <MetaRow label="Mission">
                  <span className="label-mono" style={{ fontSize: "var(--font-size-xs)" }}>
                    {record.mission_id}
                  </span>
                </MetaRow>
              )}

              {record.session_id && (
                <MetaRow label="Session">
                  <span className="label-mono" style={{ fontSize: "var(--font-size-xs)" }}>
                    {record.session_id}
                  </span>
                </MetaRow>
              )}

              <MetaRow label="Created">
                {formatDate(record.created_at)}
              </MetaRow>

              {record.last_retrieved && (
                <MetaRow label="Last Retrieved">
                  {formatDate(record.last_retrieved)}
                </MetaRow>
              )}

              <MetaRow label="Retrieved">
                <span style={{ fontWeight: 600, color: record.retrieval_count > 0 ? typeColor(record.memory_type) : "var(--text-muted)" }}>
                  {record.retrieval_count}×
                </span>
              </MetaRow>

              {record.similarity_score !== null && (() => {
                const s = scoreDisplay(record.similarity_score);
                return s ? (
                  <MetaRow label="Similarity">
                    <span style={{ fontWeight: 700, color: s.color }}>{s.label}</span>
                  </MetaRow>
                ) : null;
              })()}

              {record.confidence !== null && (
                <MetaRow label="Confidence">
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ width: 50, height: 3, borderRadius: 999, background: "var(--border-default)", overflow: "hidden" }}>
                      <div style={{ width: `${(record.confidence ?? 0) * 100}%`, height: "100%", background: typeColor(record.memory_type) }} />
                    </div>
                    <span>{Math.round((record.confidence ?? 0) * 100)}%</span>
                  </div>
                </MetaRow>
              )}

              <MetaRow label="ID">
                <span className="label-mono" style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                  {record.id}
                </span>
              </MetaRow>
            </div>

            {/* Extra metadata JSON */}
            {Object.keys(record.metadata).length > 0 && (
              <div style={{ marginTop: 12 }}>
                <p style={{ margin: "0 0 6px", fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                  Metadata
                </p>
                <pre
                  style={{
                    margin:       0,
                    padding:      "8px 10px",
                    borderRadius: "var(--radius-md)",
                    background:   "#f0f7f4",
                    border:       "1px solid var(--border-subtle)",
                    fontSize:     10,
                    color:        "var(--text-secondary)",
                    overflowX:    "auto",
                    lineHeight:   1.6,
                    maxHeight:    120,
                    overflowY:    "auto",
                  }}
                  className="cortex-scroll"
                >
                  {JSON.stringify(record.metadata, null, 2)}
                </pre>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
