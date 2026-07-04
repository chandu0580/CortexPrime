"use client";

import { useMemo } from "react";
import { useReplayStore } from "@/store/replayStore";
import { ReplayEvent } from "@/services/replayService";

const MEMORY_TYPES = new Set(["memory_retrieved", "memory_stored"]);

function formatOffset(ms: number | null): string {
  if (ms === null) return "--:--";
  const totalSec = ms / 1000;
  const m = Math.floor(totalSec / 60);
  const s = (totalSec % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}s`;
}

function preview(text: unknown, maxLen = 100): string {
  if (!text) return "";
  const s = typeof text === "string" ? text : JSON.stringify(text);
  return s.length > maxLen ? s.slice(0, maxLen) + "…" : s;
}

export function MemoryRetrievalPanel() {
  const events     = useReplayStore((s) => s.events);
  const currentSeq = useReplayStore((s) => s.currentSequence);
  const seekTo     = useReplayStore((s) => s.seekTo);

  const memEvents = useMemo(() => {
    return events.slice(0, currentSeq + 1).filter((e) => MEMORY_TYPES.has(e.event_type)).reverse();
  }, [events, currentSeq]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 280, overflowY: "auto" }} className="cortex-scroll">
      {memEvents.length === 0 ? (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", textAlign: "center", padding: "16px 0" }}>
          No memory events yet
        </p>
      ) : (
        memEvents.map((ev: ReplayEvent, i: number) => {
          const evIdx   = events.indexOf(ev);
          const isStore = ev.event_type === "memory_stored";
          const chunkCount = (ev.payload?.chunk_count as number) ?? (ev.payload?.chunks as unknown[])?.length ?? null;
          const queryText  = (ev.payload?.query as string) ?? null;
          const content    = (ev.payload?.content as string) ?? null;

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
              {/* Icon */}
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: "var(--radius-sm)",
                  background: isStore ? "rgba(71,85,105,0.08)" : "rgba(74,140,112,0.08)",
                  border: isStore ? "1px solid rgba(71,85,105,0.2)" : "1px solid rgba(74,140,112,0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                  flexShrink: 0,
                  color: isStore ? "var(--agent-memory)" : "var(--agent-planner)",
                }}
              >
                {isStore ? "▼" : "▲"}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-primary)" }}>
                    {isStore ? "Memory Store" : "Memory Retrieve"}
                  </span>
                  <span style={{ fontSize: "var(--font-size-xs)", color: "var(--agent-memory)" }}>
                    {ev.agent}
                  </span>
                  {chunkCount !== null && (
                    <span
                      style={{
                        fontSize: "var(--font-size-xs)",
                        padding: "0 5px",
                        borderRadius: "var(--radius-pill)",
                        background: "rgba(74,140,112,0.08)",
                        color: "var(--agent-planner)",
                        fontWeight: 600,
                      }}
                    >
                      {chunkCount} chunks
                    </span>
                  )}
                  <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginLeft: "auto" }}>
                    {formatOffset(ev.offset_ms)}
                  </span>
                </div>

                {queryText && (
                  <p style={{ margin: "0 0 4px", fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", fontStyle: "italic" }}>
                    Query: {preview(queryText, 80)}
                  </p>
                )}

                {content && (
                  <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {preview(content)}
                  </p>
                )}

                {!queryText && !content && (
                  <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
                    {preview(ev.message)}
                  </p>
                )}
              </div>
            </button>
          );
        })
      )}
    </div>
  );
}
