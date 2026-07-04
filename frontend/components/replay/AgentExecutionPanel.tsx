"use client";

import { useMemo } from "react";
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

function agentColor(agent: string): string {
  const key = agent.toLowerCase().replace(/_agent$/, "").replace(/^agent_/, "");
  for (const [k, v] of Object.entries(AGENT_COLORS)) {
    if (key.includes(k)) return v;
  }
  return "var(--text-muted)";
}

function formatOffset(ms: number | null): string {
  if (ms === null) return "--:--";
  const totalSec = ms / 1000;
  const m = Math.floor(totalSec / 60);
  const s = (totalSec % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}s`;
}

const AGENT_EVENT_TYPES = new Set([
  "agent_started", "agent_completed", "agent_failed",
  "mission_started", "mission_completed", "mission_failed",
  "response_generated",
]);

export function AgentExecutionPanel() {
  const events     = useReplayStore((s) => s.events);
  const currentSeq = useReplayStore((s) => s.currentSequence);
  const seekTo     = useReplayStore((s) => s.seekTo);

  // Slice events up to current sequence, filter to agent-level events
  const visibleEvents = useMemo(() => {
    return events
      .slice(0, currentSeq + 1)
      .filter((e) => AGENT_EVENT_TYPES.has(e.event_type))
      .reverse(); // newest first
  }, [events, currentSeq]);

  const currentEvent = events[currentSeq];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {/* Current event highlight */}
      {currentEvent && (
        <div
          style={{
            padding: "10px 12px",
            borderRadius: "var(--radius-md)",
            background: "rgba(130,192,164,0.05)",
            border: "1px solid rgba(130,192,164,0.15)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent)" }} />
            <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--accent)" }}>
              Current Event
            </span>
            <span
              className="label-mono"
              style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginLeft: "auto" }}
            >
              {formatOffset(currentEvent.offset_ms)}
            </span>
          </div>
          <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--text-primary)", fontWeight: 500 }}>
            {currentEvent.message}
          </p>
          <p style={{ margin: "4px 0 0", fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
            {currentEvent.event_type} · {currentEvent.agent}
          </p>
        </div>
      )}

      {/* Agent execution history */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 260, overflowY: "auto" }} className="cortex-scroll">
        {visibleEvents.length === 0 ? (
          <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", textAlign: "center", padding: "16px 0" }}>
            No agent events yet
          </p>
        ) : (
          visibleEvents.map((ev: ReplayEvent, i: number) => {
            const color = agentColor(ev.agent);
            const isLast = i === 0;
            const evIdx  = events.indexOf(ev);
            return (
              <button
                key={`${ev.sequence}-${i}`}
                onClick={() => { if (evIdx >= 0) seekTo(evIdx); }}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 8,
                  padding: "7px 10px",
                  borderRadius: "var(--radius-md)",
                  border: `1px solid ${isLast ? "var(--border-default)" : "transparent"}`,
                  background: isLast ? "#ffffff" : "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  width: "100%",
                  boxShadow: isLast ? "var(--shadow-xs)" : "none",
                }}
              >
                <div
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: color,
                    marginTop: 5,
                    flexShrink: 0,
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 2 }}>
                    <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color }}>
                      {ev.agent}
                    </span>
                    <span
                      style={{
                        fontSize: "var(--font-size-xs)",
                        color: "var(--text-muted)",
                        padding: "0 4px",
                        background: "var(--border-subtle)",
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      {ev.event_type.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {ev.message}
                  </p>
                </div>
                <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", flexShrink: 0 }}>
                  {formatOffset(ev.offset_ms)}
                </span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
