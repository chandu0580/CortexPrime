"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { useMemoryExplorerStore } from "@/store/memoryExplorerStore";
import { HeatmapCell } from "@/services/memoryExplorerService";

// ── Constants ─────────────────────────────────────────────────────────────

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

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days < 1) return "today";
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

// ── Heatmap cell ──────────────────────────────────────────────────────────

function Cell({
  cell,
  maxCount,
  isSelected,
  onSelect,
}: {
  cell: HeatmapCell;
  maxCount: number;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const color     = typeColor(cell.memory_type);
  const intensity = maxCount > 0 ? cell.retrieval_count / maxCount : 0;
  const bgAlpha   = Math.max(0.06, intensity * 0.6);
  const borderAlpha = Math.max(0.12, intensity * 0.5);

  return (
    <motion.button
      onClick={onSelect}
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={{ scale: 1.03, zIndex: 10 }}
      style={{
        display:      "flex",
        flexDirection: "column",
        gap:          4,
        padding:      "10px 12px",
        borderRadius: "var(--radius-md)",
        border:       `1px solid ${isSelected ? color + "55" : color + Math.round(borderAlpha * 255).toString(16).padStart(2, "0")}`,
        background:   isSelected ? `${color}18` : `${color}${Math.round(bgAlpha * 255).toString(16).padStart(2, "0")}`,
        cursor:       "pointer",
        textAlign:    "left",
        position:     "relative",
        overflow:     "hidden",
        transition:   "border-color 0.12s",
      }}
    >
      {/* Heat intensity bar (bottom fill) */}
      <div
        style={{
          position:     "absolute",
          left:         0,
          bottom:       0,
          width:        `${intensity * 100}%`,
          height:       2,
          background:   color,
          borderRadius: "0 0 var(--radius-md) var(--radius-md)",
        }}
      />

      {/* Type chip */}
      <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0 }} />
        <span style={{ fontSize: "var(--font-size-xs)", color, fontWeight: 600 }}>
          {cell.memory_type}
        </span>
        {cell.agent && (
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
            {cell.agent}
          </span>
        )}
      </div>

      {/* Label */}
      <p style={{
        margin:         0,
        fontSize:       "var(--font-size-xs)",
        fontWeight:     500,
        color:          "var(--text-primary)",
        lineHeight:     1.3,
        display:        "-webkit-box",
        WebkitLineClamp: 2,
        WebkitBoxOrient: "vertical" as const,
        overflow:       "hidden",
      }}>
        {cell.label}
      </p>

      {/* Count + age */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span
          style={{
            fontSize:     "var(--font-size-xs)",
            fontWeight:   700,
            color,
            background:   `${color}18`,
            padding:      "1px 6px",
            borderRadius: "var(--radius-pill)",
          }}
        >
          {cell.retrieval_count > 0 ? `${cell.retrieval_count}×` : "new"}
        </span>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          {relativeTime(cell.created_at)}
        </span>
      </div>
    </motion.button>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export function MemoryHeatmap() {
  const stats       = useMemoryExplorerStore((s) => s.stats);
  const isLoading   = useMemoryExplorerStore((s) => s.isStatsLoading);
  const setSelected = useMemoryExplorerStore((s) => s.setSelectedRecord);
  const selectedId  = useMemoryExplorerStore((s) => s.selectedRecord?.id ?? null);

  const heatmap = stats?.heatmap ?? [];

  // Max retrieval count for normalisation
  const maxCount = useMemo(
    () => heatmap.reduce((m, c) => Math.max(m, c.retrieval_count), 1),
    [heatmap]
  );

  // Date distribution bar chart data
  const dateDist = useMemo(() => {
    const dist = stats?.date_distribution ?? {};
    const entries = Object.entries(dist).sort(([a], [b]) => a.localeCompare(b));
    const max     = Math.max(...entries.map(([, v]) => v), 1);
    return entries.map(([d, v]) => ({ date: d, count: v, pct: v / max }));
  }, [stats]);

  if (isLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "var(--font-size-sm)", padding: "24px 0" }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
          style={{ width: 14, height: 14, border: "2px solid var(--border-default)", borderTopColor: "var(--accent)", borderRadius: "50%" }}
        />
        Loading heatmap…
      </div>
    );
  }

  if (!stats) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "32px 0", color: "var(--text-muted)", gap: 8 }}>
        <span style={{ fontSize: 28 }}>◎</span>
        <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>No stats available</p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* ── Stats overview ─────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
        <StatCard label="Total Memories" value={stats.total.toLocaleString()} color="var(--accent)" />
        <StatCard
          label="Memory Types"
          value={Object.keys(stats.by_type).length}
          color="var(--agent-planner)"
        />
        <StatCard
          label="Active Agents"
          value={Object.keys(stats.by_agent).length}
          color="var(--agent-research)"
        />
      </div>

      {/* ── Type breakdown ─────────────────────────────────────────── */}
      <div>
        <p style={{ margin: "0 0 8px", fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          By Type
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {Object.entries(stats.by_type)
            .sort(([, a], [, b]) => b - a)
            .map(([type, count]) => {
              const total = stats.total || 1;
              const pct   = Math.round((count / total) * 100);
              const color = typeColor(type);
              return (
                <div key={type} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: "var(--font-size-xs)", color, fontWeight: 500, minWidth: 72 }}>
                    {type}
                  </span>
                  <div style={{ flex: 1, height: 5, borderRadius: 999, background: "var(--border-subtle)", overflow: "hidden" }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.5, ease: "easeOut" }}
                      style={{ height: "100%", background: color, borderRadius: 999 }}
                    />
                  </div>
                  <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", minWidth: 36, textAlign: "right" }}>
                    {count.toLocaleString()}
                  </span>
                </div>
              );
            })}
        </div>
      </div>

      {/* ── Activity chart (last 30 days) ──────────────────────────── */}
      {dateDist.length > 0 && (
        <div>
          <p style={{ margin: "0 0 8px", fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Activity (last {dateDist.length} days)
          </p>
          <div
            style={{
              display:       "flex",
              alignItems:    "flex-end",
              gap:           2,
              height:        48,
              paddingBottom: 2,
            }}
          >
            {dateDist.map(({ date, count, pct }) => (
              <motion.div
                key={date}
                title={`${date}: ${count}`}
                initial={{ height: 0 }}
                animate={{ height: `${Math.max(pct * 100, 4)}%` }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                style={{
                  flex:         1,
                  minWidth:     2,
                  borderRadius: "2px 2px 0 0",
                  background:   `rgba(130,192,164,${0.2 + pct * 0.8})`,
                  cursor:       "default",
                }}
              />
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
            <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>{dateDist[0]?.date}</span>
            <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>{dateDist[dateDist.length - 1]?.date}</span>
          </div>
        </div>
      )}

      {/* ── Heatmap grid ───────────────────────────────────────────── */}
      {heatmap.length > 0 && (
        <div>
          <p style={{ margin: "0 0 10px", fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Most Retrieved Memories
          </p>
          <div
            style={{
              display:             "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
              gap:                 8,
              maxHeight:           400,
              overflowY:           "auto",
            }}
            className="cortex-scroll"
          >
            {heatmap.map((cell) => (
              <Cell
                key={cell.id}
                cell={cell}
                maxCount={maxCount}
                isSelected={selectedId === cell.id}
                onSelect={() => {
                  setSelected({
                    id:               cell.id,
                    memory_type:      cell.memory_type as never,
                    content:          cell.label,
                    agent:            cell.agent,
                    concept:          cell.memory_type === "semantic" ? cell.label : null,
                    event_type:       null,
                    session_id:       null,
                    mission_id:       null,
                    source:           null,
                    similarity_score: null,
                    confidence:       null,
                    retrieval_count:  cell.retrieval_count,
                    created_at:       cell.created_at,
                    last_retrieved:   null,
                    metadata:         {},
                  });
                }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────

function StatCard({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div
      style={{
        display:      "flex",
        flexDirection: "column",
        gap:          2,
        padding:      "10px 12px",
        borderRadius: "var(--radius-md)",
        background:   `${color}08`,
        border:       `1px solid ${color}22`,
      }}
    >
      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>{label}</span>
      <span
        className="label-mono"
        style={{ fontSize: "var(--font-size-lg)", fontWeight: 700, color }}
      >
        {typeof value === "number" ? value.toLocaleString() : value}
      </span>
    </div>
  );
}
