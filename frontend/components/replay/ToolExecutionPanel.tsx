"use client";

import { useMemo } from "react";
import { useReplayStore } from "@/store/replayStore";
import { ReplayEvent } from "@/services/replayService";

const TOOL_TYPES = new Set(["tool_called", "tool_completed", "tool_failed"]);

function statusIcon(et: string): string {
  if (et === "tool_called")    return "⏳";
  if (et === "tool_completed") return "✓";
  if (et === "tool_failed")    return "✗";
  return "·";
}

function statusColor(et: string): string {
  if (et === "tool_called")    return "var(--accent)";
  if (et === "tool_completed") return "var(--color-success)";
  if (et === "tool_failed")    return "var(--color-error)";
  return "var(--text-muted)";
}

function formatOffset(ms: number | null): string {
  if (ms === null) return "--:--";
  const totalSec = ms / 1000;
  const m = Math.floor(totalSec / 60);
  const s = (totalSec % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}s`;
}

function formatPayloadValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v.length > 80 ? v.slice(0, 80) + "…" : v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try { return JSON.stringify(v).slice(0, 80); } catch { return "…"; }
}

export function ToolExecutionPanel() {
  const events     = useReplayStore((s) => s.events);
  const currentSeq = useReplayStore((s) => s.currentSequence);
  const seekTo     = useReplayStore((s) => s.seekTo);

  const toolEvents = useMemo(() => {
    return events.slice(0, currentSeq + 1).filter((e) => TOOL_TYPES.has(e.event_type)).reverse();
  }, [events, currentSeq]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 280, overflowY: "auto" }} className="cortex-scroll">
      {toolEvents.length === 0 ? (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", textAlign: "center", padding: "16px 0" }}>
          No tool calls yet
        </p>
      ) : (
        toolEvents.map((ev: ReplayEvent, i: number) => {
          const color = statusColor(ev.event_type);
          const icon  = statusIcon(ev.event_type);
          const evIdx = events.indexOf(ev);
          const toolName = (ev.payload?.tool_name as string) ?? ev.message.split(" ")[0] ?? "tool";
          const args     = ev.payload?.args as Record<string, unknown> | undefined;
          const result   = ev.payload?.result as unknown;

          return (
            <button
              key={`${ev.sequence}-${i}`}
              onClick={() => { if (evIdx >= 0) seekTo(evIdx); }}
              style={{
                display: "flex",
                gap: 10,
                padding: "8px 10px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-default)",
                background: "#ffffff",
                cursor: "pointer",
                textAlign: "left",
                width: "100%",
                boxShadow: "var(--shadow-xs)",
              }}
            >
              {/* Status icon */}
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: "var(--radius-sm)",
                  background: `${color}15`,
                  border: `1px solid ${color}30`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12,
                  flexShrink: 0,
                  color,
                }}
              >
                {icon}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                  <span style={{ fontSize: "var(--font-size-sm)", fontWeight: 600, color: "var(--text-primary)" }}>
                    {toolName}
                  </span>
                  <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                    {ev.agent}
                  </span>
                  <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginLeft: "auto" }}>
                    {formatOffset(ev.offset_ms)}
                  </span>
                </div>

                {/* Args */}
                {args && Object.keys(args).length > 0 && (
                  <div style={{ marginBottom: 4 }}>
                    {Object.entries(args).slice(0, 2).map(([k, v]) => (
                      <div key={k} style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                        <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{k}:</span>{" "}
                        {formatPayloadValue(v)}
                      </div>
                    ))}
                  </div>
                )}

                {/* Result (for completed) */}
                {ev.event_type === "tool_completed" && result !== undefined && (
                  <div
                    style={{
                      fontSize: "var(--font-size-xs)",
                      color: "var(--color-success)",
                      background: "rgba(74,140,112,0.06)",
                      padding: "3px 6px",
                      borderRadius: "var(--radius-sm)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    ↳ {formatPayloadValue(result)}
                  </div>
                )}

                {ev.event_type === "tool_failed" && (
                  <div
                    style={{
                      fontSize: "var(--font-size-xs)",
                      color: "var(--color-error)",
                      background: "rgba(220,38,38,0.06)",
                      padding: "3px 6px",
                      borderRadius: "var(--radius-sm)",
                    }}
                  >
                    ✗ {ev.message}
                  </div>
                )}

                {/* Latency */}
                {ev.latency_ms != null && (
                  <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                    {ev.latency_ms.toFixed(0)}ms
                  </span>
                )}
              </div>
            </button>
          );
        })
      )}
    </div>
  );
}
