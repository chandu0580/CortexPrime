"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useMemoryExplorerStore } from "@/store/memoryExplorerStore";
import { MemoryRecord, TimelineDay } from "@/services/memoryExplorerService";

// ── Types helpers ─────────────────────────────────────────────────────────

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

function relativeTime(iso: string): string {
  const t = new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return t;
}

function formatDay(yyyymmdd: string): string {
  const d = new Date(yyyymmdd + "T00:00:00");
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

// ── Day column ────────────────────────────────────────────────────────────

function DayBucket({
  day,
  isExpanded,
  onToggle,
  onSelect,
  selectedId,
}: {
  day: TimelineDay;
  isExpanded: boolean;
  onToggle: () => void;
  onSelect: (r: MemoryRecord) => void;
  selectedId: string | null;
}) {
  // Count by type
  const typeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of day.records) c[r.memory_type] = (c[r.memory_type] ?? 0) + 1;
    return c;
  }, [day.records]);

  return (
    <div>
      {/* Day header */}
      <button
        onClick={onToggle}
        style={{
          display:        "flex",
          alignItems:     "center",
          gap:            10,
          padding:        "8px 0",
          width:          "100%",
          cursor:         "pointer",
          background:     "transparent",
          border:         "none",
          textAlign:      "left",
        }}
      >
        {/* Expand icon */}
        <motion.span
          animate={{ rotate: isExpanded ? 90 : 0 }}
          transition={{ duration: 0.15 }}
          style={{ fontSize: 10, color: "var(--text-muted)", flexShrink: 0 }}
        >
          ▶
        </motion.span>

        {/* Date */}
        <span style={{ fontSize: "var(--font-size-sm)", fontWeight: 600, color: "var(--text-primary)" }}>
          {formatDay(day.date)}
        </span>

        {/* Count badge */}
        <span
          style={{
            fontSize:     "var(--font-size-xs)",
            fontWeight:   600,
            padding:      "1px 7px",
            borderRadius: "var(--radius-pill)",
            background:   "var(--border-subtle)",
            color:        "var(--text-muted)",
          }}
        >
          {day.count}
        </span>

        {/* Type distribution dots */}
        <div style={{ display: "flex", gap: 3, marginLeft: "auto" }}>
          {Object.entries(typeCounts).map(([t, n]) => (
            <span
              key={t}
              title={`${n} ${t}`}
              style={{
                display:      "inline-block",
                width:        Math.min(6 + n * 2, 18),
                height:       6,
                borderRadius: 999,
                background:   typeColor(t),
                opacity:      0.7,
              }}
            />
          ))}
        </div>
      </button>

      {/* Events */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: "hidden", paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}
          >
            {day.records.map((rec) => {
              const color    = typeColor(rec.memory_type);
              const isSel    = rec.id === selectedId;

              return (
                <motion.button
                  key={rec.id}
                  onClick={() => onSelect(rec)}
                  style={{
                    display:     "flex",
                    alignItems:  "flex-start",
                    gap:         8,
                    padding:     "6px 10px",
                    borderRadius: "var(--radius-md)",
                    border:      `1px solid ${isSel ? color + "44" : "transparent"}`,
                    background:  isSel ? `${color}08` : "transparent",
                    cursor:      "pointer",
                    textAlign:   "left",
                    width:       "100%",
                  }}
                  whileHover={{ background: `${color}06`, borderColor: `${color}22` }}
                >
                  {/* Type dot */}
                  <div
                    style={{
                      width:        7,
                      height:       7,
                      borderRadius: "50%",
                      background:   color,
                      marginTop:    5,
                      flexShrink:   0,
                    }}
                  />

                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Content preview */}
                    <p
                      style={{
                        margin:         0,
                        fontSize:       "var(--font-size-xs)",
                        color:          "var(--text-secondary)",
                        lineHeight:     1.4,
                        overflow:       "hidden",
                        textOverflow:   "ellipsis",
                        whiteSpace:     "nowrap",
                      }}
                    >
                      {rec.concept ? (
                        <><strong style={{ color: "var(--text-primary)" }}>{rec.concept}:</strong>{" "}</>
                      ) : null}
                      {rec.content}
                    </p>
                    <div style={{ display: "flex", gap: 6, marginTop: 2 }}>
                      <span style={{ fontSize: "var(--font-size-xs)", color }}>
                        {rec.memory_type}
                      </span>
                      {rec.agent && (
                        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                          {rec.agent}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Time */}
                  <span
                    className="label-mono"
                    style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", flexShrink: 0, paddingTop: 2 }}
                  >
                    {relativeTime(rec.created_at)}
                  </span>
                </motion.button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Separator line */}
      <div style={{ height: 1, background: "var(--border-subtle)", margin: "4px 0" }} />
    </div>
  );
}

// ── Day range selector ────────────────────────────────────────────────────

const DAY_OPTIONS = [7, 14, 30, 60, 90];

// ── Main component ────────────────────────────────────────────────────────

export function MemoryTimeline() {
  const timeline      = useMemoryExplorerStore((s) => s.timeline);
  const total         = useMemoryExplorerStore((s) => s.timelineTotal);
  const isLoading     = useMemoryExplorerStore((s) => s.isTimelineLoading);
  const days          = useMemoryExplorerStore((s) => s.timelineDays);
  const setDays       = useMemoryExplorerStore((s) => s.setTimelineDays);
  const loadTimeline  = useMemoryExplorerStore((s) => s.loadTimeline);
  const setSelected   = useMemoryExplorerStore((s) => s.setSelectedRecord);
  const selectedId    = useMemoryExplorerStore((s) => s.selectedRecord?.id ?? null);

  const [expandedDays, setExpandedDays] = useState<Set<string>>(
    () => new Set(timeline.slice(0, 3).map((d) => d.date))
  );

  function toggleDay(date: string) {
    setExpandedDays((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  }

  function handleDayChange(d: number) {
    setDays(d);
    loadTimeline();
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, height: "100%" }}>
      {/* Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>Show last</span>
        {DAY_OPTIONS.map((d) => (
          <button
            key={d}
            onClick={() => handleDayChange(d)}
            style={{
              padding:      "3px 8px",
              borderRadius: "var(--radius-sm)",
              border:       `1px solid ${days === d ? "var(--accent)" : "var(--border-default)"}`,
              background:   days === d ? "rgba(130,192,164,0.08)" : "transparent",
              color:        days === d ? "var(--accent)" : "var(--text-muted)",
              fontSize:     "var(--font-size-xs)",
              fontWeight:   days === d ? 700 : 500,
              cursor:       "pointer",
            }}
          >
            {d}d
          </button>
        ))}

        <span
          style={{ marginLeft: "auto", fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}
        >
          {total.toLocaleString()} total memories
        </span>
      </div>

      {/* Loading */}
      {isLoading && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "var(--font-size-sm)", padding: "16px 0" }}>
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
            style={{ width: 14, height: 14, border: "2px solid var(--border-default)", borderTopColor: "var(--accent)", borderRadius: "50%" }}
          />
          Loading timeline…
        </div>
      )}

      {/* Empty */}
      {!isLoading && timeline.length === 0 && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 0", color: "var(--text-muted)", gap: 8 }}>
          <span style={{ fontSize: 28 }}>◎</span>
          <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--text-secondary)" }}>No memories in this period</p>
        </div>
      )}

      {/* Timeline list */}
      {!isLoading && timeline.length > 0 && (
        <div style={{ flex: 1, overflowY: "auto" }} className="cortex-scroll">
          {timeline.map((day) => (
            <DayBucket
              key={day.date}
              day={day}
              isExpanded={expandedDays.has(day.date)}
              onToggle={() => toggleDay(day.date)}
              onSelect={setSelected}
              selectedId={selectedId}
            />
          ))}
        </div>
      )}
    </div>
  );
}
