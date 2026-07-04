"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useReplayStore } from "@/store/replayStore";
import { ReplayEvent } from "@/services/replayService";

const AGENT_COLORS: Record<string, string> = {
  orchestrator: "var(--agent-orchestrator)",
  planner:      "var(--agent-planner)",
  research:     "var(--agent-research)",
  critic:       "var(--agent-critic)",
  optimizer:    "var(--agent-optimizer)",
  memory:       "var(--agent-memory)",
};

const EVENT_TYPE_LABELS: Record<string, string> = {
  mission_started:     "Mission Started",
  mission_completed:   "Mission Complete",
  mission_failed:      "Mission Failed",
  agent_started:       "Agent Active",
  agent_completed:     "Agent Done",
  agent_failed:        "Agent Failed",
  tool_called:         "Tool Call",
  tool_completed:      "Tool Result",
  tool_failed:         "Tool Failed",
  memory_retrieved:    "Memory Retrieved",
  memory_stored:       "Memory Stored",
  response_generated:  "Response",
};

function agentColor(agent: string): string {
  const key = agent.toLowerCase().replace("_agent", "").replace("agent_", "");
  for (const [k, v] of Object.entries(AGENT_COLORS)) {
    if (key.includes(k)) return v;
  }
  return "var(--text-muted)";
}

function formatOffset(ms: number | null): string {
  if (ms === null) return "--:--";
  const totalSec = ms / 1000;
  const m = Math.floor(totalSec / 60);
  const s = (totalSec % 60).toFixed(2).padStart(5, "0");
  return `${m}:${s}`;
}

function statusBadge(et: string): { bg: string; text: string } {
  if (et.includes("failed") || et.includes("error"))
    return { bg: "rgba(220,38,38,0.08)", text: "var(--color-error)" };
  if (et.includes("started") || et.includes("called"))
    return { bg: "rgba(130,192,164,0.08)", text: "var(--agent-orchestrator)" };
  if (et.includes("completed") || et.includes("generated"))
    return { bg: "rgba(74,140,112,0.08)", text: "var(--color-success)" };
  if (et.includes("memory"))
    return { bg: "rgba(71,85,105,0.08)", text: "var(--agent-memory)" };
  return { bg: "rgba(100,116,139,0.08)", text: "var(--text-muted)" };
}

interface MissionTimelineProps {
  /** If provided, the timeline auto-scrolls to keep current event visible */
  autoScroll?: boolean;
}

export function MissionTimeline({ autoScroll = true }: MissionTimelineProps) {
  const events         = useReplayStore((s) => s.events);
  const currentSeq     = useReplayStore((s) => s.currentSequence);
  const seekTo         = useReplayStore((s) => s.seekTo);
  const totalSequences = useReplayStore((s) => s.totalSequences);

  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Auto-scroll active item into view
  useEffect(() => {
    if (!autoScroll) return;
    const el = itemRefs.current[currentSeq];
    if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [currentSeq, autoScroll]);

  if (!events.length) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: 120,
          color: "var(--text-muted)",
          fontSize: "var(--font-size-sm)",
        }}
      >
        No events recorded yet
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 2,
        overflowY: "auto",
        maxHeight: 340,
        paddingRight: 4,
      }}
      className="cortex-scroll"
    >
      {/* Scrubber bar */}
      <div style={{ marginBottom: 8 }}>
        <div
          style={{
            height: 4,
            borderRadius: 999,
            background: "var(--border-subtle)",
            cursor: "pointer",
            position: "relative",
          }}
          onClick={(e) => {
            const rect = (e.target as HTMLElement).getBoundingClientRect();
            const pct  = (e.clientX - rect.left) / rect.width;
            seekTo(Math.round(pct * (totalSequences - 1)));
          }}
        >
          <motion.div
            style={{
              height: "100%",
              borderRadius: 999,
              background: "var(--accent)",
              transformOrigin: "left",
            }}
            animate={{ width: `${totalSequences > 1 ? (currentSeq / (totalSequences - 1)) * 100 : 0}%` }}
            transition={{ duration: 0.1 }}
          />
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: 4,
            fontSize: "var(--font-size-xs)",
            color: "var(--text-muted)",
          }}
        >
          <span>{formatOffset(events[0]?.offset_ms ?? 0)}</span>
          <span className="label-mono">
            {currentSeq + 1} / {totalSequences}
          </span>
          <span>{formatOffset(events[events.length - 1]?.offset_ms ?? null)}</span>
        </div>
      </div>

      {/* Event list */}
      {events.map((ev: ReplayEvent, i: number) => {
        const isActive  = i === currentSeq;
        const isPast    = i < currentSeq;
        const color     = agentColor(ev.agent);
        const badge     = statusBadge(ev.event_type);
        const label     = EVENT_TYPE_LABELS[ev.event_type] ?? ev.event_type;

        return (
          <motion.button
            key={`${ev.sequence}-${i}`}
            ref={(el) => { itemRefs.current[i] = el; }}
            onClick={() => seekTo(i)}
            initial={false}
            animate={{
              background: isActive
                ? "rgba(130,192,164,0.06)"
                : "transparent",
              borderColor: isActive ? "rgba(130,192,164,0.2)" : "transparent",
            }}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
              padding: "6px 8px",
              borderRadius: "var(--radius-md)",
              border: "1px solid transparent",
              cursor: "pointer",
              textAlign: "left",
              width: "100%",
              opacity: isPast ? 0.55 : 1,
              transition: "opacity 0.15s",
            }}
          >
            {/* Timeline dot + line */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                paddingTop: 3,
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: isActive ? color : isPast ? "var(--border-strong)" : "var(--border-default)",
                  flexShrink: 0,
                  boxShadow: isActive ? `0 0 0 3px ${color}22` : "none",
                }}
              />
              {i < events.length - 1 && (
                <div
                  style={{
                    width: 1,
                    flexGrow: 1,
                    minHeight: 16,
                    background: isPast ? "var(--border-strong)" : "var(--border-subtle)",
                    marginTop: 3,
                  }}
                />
              )}
            </div>

            {/* Content */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: 2,
                }}
              >
                <span
                  style={{
                    fontSize: "var(--font-size-xs)",
                    fontWeight: 600,
                    padding: "1px 6px",
                    borderRadius: "var(--radius-sm)",
                    background: badge.bg,
                    color: badge.text,
                    whiteSpace: "nowrap",
                  }}
                >
                  {label}
                </span>
                <span
                  style={{
                    fontSize: "var(--font-size-xs)",
                    color: color,
                    fontWeight: 500,
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {ev.agent}
                </span>
              </div>
              <p
                style={{
                  margin: 0,
                  fontSize: "var(--font-size-xs)",
                  color: "var(--text-secondary)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  maxWidth: "100%",
                }}
              >
                {ev.message}
              </p>
            </div>

            {/* Timestamp */}
            <span
              className="label-mono"
              style={{
                fontSize: "var(--font-size-xs)",
                color: "var(--text-muted)",
                flexShrink: 0,
                paddingTop: 2,
              }}
            >
              {formatOffset(ev.offset_ms)}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}
