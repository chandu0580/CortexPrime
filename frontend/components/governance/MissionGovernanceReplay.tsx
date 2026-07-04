"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useGovernanceCenterStore } from "@/store/governanceCenterStore";
import type { ReplayGovernanceEvent } from "@/services/governanceCenterService";

// ── Stage config ──────────────────────────────────────────────────────────

const STAGE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  input_validation:    { label: "Input Validation",   icon: "⊕", color: "#38bdf8" },
  tool_approval:       { label: "Tool Approval",       icon: "⊙", color: "#fbbf24" },
  memory_approval:     { label: "Memory Approval",     icon: "⊞", color: "#818cf8" },
  execution_approval:  { label: "Execution Approval",  icon: "⊗", color: "#82c0a4" },
  output_validation:   { label: "Output Validation",   icon: "⊛", color: "#34d399" },
};

const DECISION_COLORS: Record<string, string> = {
  approved: "#34d399",
  blocked:  "#f87171",
  warned:   "#fbbf24",
};

function stageColor(stage: string) {
  return STAGE_CONFIG[stage]?.color ?? "var(--text-muted)";
}

function decisionColor(d: string) {
  return DECISION_COLORS[d] ?? "#a3a3a3";
}

function formatOffset(ms: number): string {
  if (ms < 1000) return `+${ms}ms`;
  if (ms < 60000) return `+${(ms / 1000).toFixed(1)}s`;
  return `+${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

// ── Timeline dot ──────────────────────────────────────────────────────────

function TimelineDot({
  event,
  isActive,
  isPast,
  onClick,
}: {
  event: ReplayGovernanceEvent;
  isActive: boolean;
  isPast: boolean;
  onClick: () => void;
}) {
  const sc    = STAGE_CONFIG[event.stage] ?? { icon: "◎", color: "#737373" };
  const color = decisionColor(event.decision);

  return (
    <motion.button
      onClick={onClick}
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: isPast || isActive ? 1 : 0.35 }}
      whileHover={{ scale: 1.15 }}
      style={{
        width:        32,
        height:       32,
        borderRadius: "50%",
        border:       `2px solid ${isActive ? color : (isPast ? color + "80" : "var(--border-default)")}`,
        background:   isActive ? `${color}22` : isPast ? `${color}10` : "rgba(255,255,255,0.02)",
        display:      "flex",
        alignItems:   "center",
        justifyContent: "center",
        cursor:       "pointer",
        flexShrink:   0,
        color:        isActive ? color : isPast ? color + "aa" : "var(--text-muted)",
        fontSize:     13,
        boxShadow:    isActive ? `0 0 12px ${color}55` : "none",
        transition:   "all 0.2s",
        position:     "relative",
      }}
    >
      {sc.icon}
      {isActive && (
        <motion.div
          animate={{ scale: [1, 1.8], opacity: [0.6, 0] }}
          transition={{ repeat: Infinity, duration: 1 }}
          style={{ position: "absolute", inset: -2, borderRadius: "50%", border: `2px solid ${color}` }}
        />
      )}
    </motion.button>
  );
}

// ── Detail panel ──────────────────────────────────────────────────────────

function DetailPanel({ event }: { event: ReplayGovernanceEvent }) {
  const sc    = STAGE_CONFIG[event.stage] ?? { label: event.stage, icon: "◎", color: "#737373" };
  const color = decisionColor(event.decision);

  return (
    <motion.div
      key={event.sequence}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
      style={{
        padding:      "12px 14px",
        borderRadius: "var(--radius-lg)",
        border:       `1px solid ${color}33`,
        background:   `${color}06`,
        position:     "relative",
        overflow:     "hidden",
      }}
    >
      {/* Left accent */}
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: color, borderRadius: "3px 0 0 3px" }} />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 15, color: sc.color }}>{sc.icon}</span>
        <span style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--text-primary)" }}>{sc.label}</span>
        <span style={{ marginLeft: "auto", fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>seq {event.sequence}</span>
        <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>{formatOffset(event.offset_ms)}</span>
      </div>

      {/* Decision + risk */}
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        <span style={{
          fontSize:     "var(--font-size-xs)", fontWeight: 700, color, padding: "2px 9px",
          borderRadius: "var(--radius-pill)", background: `${color}18`, border: `1px solid ${color}33`,
        }}>
          {event.decision.toUpperCase()}
        </span>
        <span style={{
          fontSize:     "var(--font-size-xs)", fontWeight: 600, color: stageColor(event.stage),
          padding: "2px 9px", borderRadius: "var(--radius-pill)", background: `${stageColor(event.stage)}12`,
          border: `1px solid ${stageColor(event.stage)}22`,
        }}>
          {event.risk_level.toUpperCase()} RISK
        </span>
      </div>

      {/* Action */}
      <p style={{ margin: "0 0 4px", fontSize: "var(--font-size-xs)", color: "var(--text-primary)", lineHeight: 1.5 }}>
        <strong style={{ color: "var(--text-muted)" }}>Agent: </strong>{event.agent}
        <br />
        <strong style={{ color: "var(--text-muted)" }}>Action: </strong>{event.action}
      </p>

      {event.reason && (
        <p style={{ margin: "4px 0 0", fontSize: "var(--font-size-xs)", color: "var(--text-muted)", lineHeight: 1.4 }}>
          {event.reason}
        </p>
      )}
    </motion.div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function MissionGovernanceReplay() {
  const replayData     = useGovernanceCenterStore((s) => s.replayData);
  const replayExecId   = useGovernanceCenterStore((s) => s.replayExecId);
  const replaySeq      = useGovernanceCenterStore((s) => s.replaySequence);
  const replayPlaying  = useGovernanceCenterStore((s) => s.replayPlaying);
  const isLoading      = useGovernanceCenterStore((s) => s.isReplayLoading);
  const setExecId      = useGovernanceCenterStore((s) => s.setReplayExecId);
  const setSeq         = useGovernanceCenterStore((s) => s.setReplaySequence);
  const setPlaying     = useGovernanceCenterStore((s) => s.setReplayPlaying);
  const loadReplay     = useGovernanceCenterStore((s) => s.loadReplay);

  const [inputId, setInputId] = useState(replayExecId);
  const playRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const seqRef  = useRef(replaySeq);
  useEffect(() => { seqRef.current = replaySeq; }, [replaySeq]);

  const events = replayData?.events ?? [];
  const total  = events.length;

  // Auto-advance
  useEffect(() => {
    if (!replayPlaying) { if (playRef.current) clearInterval(playRef.current); return; }
    playRef.current = setInterval(() => {
      const next = seqRef.current + 1;
      if (next >= total) { setPlaying(false); }
      else { setSeq(next); }
    }, 600);
    return () => { if (playRef.current) clearInterval(playRef.current); };
  }, [replayPlaying, total, setSeq, setPlaying]);

  const activeEvent = events[replaySeq] ?? null;

  // Stage summary for the header
  const summary = replayData?.summary as Record<string, unknown> | null;
  const summaryByStage = (summary?.by_stage ?? {}) as Record<string, number>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

      {/* Execution ID input */}
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="premium-input"
          placeholder="Execution ID (e.g. mission-abc-123)"
          value={inputId}
          onChange={(e) => setInputId(e.target.value)}
          style={{ flex: 1, fontSize: "var(--font-size-xs)" }}
          onKeyDown={(e) => { if (e.key === "Enter" && inputId.trim()) { setExecId(inputId.trim()); loadReplay(inputId.trim()); } }}
        />
        <motion.button
          className="btn-primary"
          onClick={() => { if (inputId.trim()) { setExecId(inputId.trim()); loadReplay(inputId.trim()); } }}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          style={{ fontSize: "var(--font-size-xs)", padding: "0 14px", whiteSpace: "nowrap" }}
        >
          {isLoading ? "Loading…" : "Load Replay"}
        </motion.button>
      </div>

      {isLoading && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "var(--font-size-sm)" }}>
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
            style={{ width: 12, height: 12, border: "2px solid var(--border-default)", borderTopColor: "var(--accent)", borderRadius: "50%" }}
          />
          Loading governance replay…
        </div>
      )}

      {!replayData && !isLoading && (
        <div style={{ textAlign: "center", padding: "20px 0", color: "var(--text-muted)" }}>
          <div style={{ fontSize: 22, opacity: 0.25, marginBottom: 6 }}>◈</div>
          <p style={{ margin: 0, fontSize: "var(--font-size-sm)" }}>Enter an execution ID to replay its governance timeline</p>
        </div>
      )}

      {replayData && !isLoading && (
        <>
          {/* Summary header */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
            <MiniStat label="Total Events" value={replayData.total_events} color="var(--accent)" />
            <MiniStat label="Approved"     value={(summary?.approved as number) ?? 0} color="#34d399" />
            <MiniStat label="Blocked"      value={(summary?.blocked as number) ?? 0}  color="#f87171" />
          </div>

          {/* Stage breakdown */}
          {Object.keys(summaryByStage).length > 0 && (
            <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
              {Object.entries(summaryByStage).map(([stage, count]) => {
                const sc = STAGE_CONFIG[stage];
                if (!sc || !count) return null;
                return (
                  <span key={stage} style={{
                    fontSize:     "10px", fontWeight: 600, color: sc.color,
                    background:   `${sc.color}12`, padding: "2px 8px",
                    borderRadius: "var(--radius-pill)", border: `1px solid ${sc.color}25`,
                  }}>
                    {sc.icon} {sc.label}: {count}
                  </span>
                );
              })}
            </div>
          )}

          {/* Playback controls */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              onClick={() => setSeq(Math.max(0, replaySeq - 1))}
              disabled={replaySeq === 0}
              style={{ padding: "4px 10px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-default)", background: "transparent", color: "var(--text-muted)", cursor: replaySeq === 0 ? "not-allowed" : "pointer", fontSize: "var(--font-size-xs)", opacity: replaySeq === 0 ? 0.4 : 1 }}
            >
              ◂
            </button>

            <motion.button
              onClick={() => setPlaying(!replayPlaying)}
              whileHover={{ scale: 1.06 }}
              style={{
                padding:      "4px 14px",
                borderRadius: "var(--radius-sm)",
                border:       `1px solid ${replayPlaying ? "#f87171" : "var(--accent)"}`,
                background:   replayPlaying ? "rgba(248,113,113,0.1)" : "rgba(130,192,164,0.1)",
                color:        replayPlaying ? "#f87171" : "var(--accent)",
                cursor:       "pointer",
                fontSize:     "var(--font-size-xs)",
                fontWeight:   600,
              }}
            >
              {replayPlaying ? "■ Pause" : "▶ Play"}
            </motion.button>

            <button
              onClick={() => setSeq(Math.min(total - 1, replaySeq + 1))}
              disabled={replaySeq >= total - 1}
              style={{ padding: "4px 10px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-default)", background: "transparent", color: "var(--text-muted)", cursor: replaySeq >= total - 1 ? "not-allowed" : "pointer", fontSize: "var(--font-size-xs)", opacity: replaySeq >= total - 1 ? 0.4 : 1 }}
            >
              ▸
            </button>

            <button
              onClick={() => { setSeq(0); setPlaying(false); }}
              style={{ padding: "4px 10px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-default)", background: "transparent", color: "var(--text-muted)", cursor: "pointer", fontSize: "var(--font-size-xs)" }}
            >
              ↺
            </button>

            <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", marginLeft: "auto" }}>
              {replaySeq + 1} / {total}
            </span>
          </div>

          {/* Progress bar */}
          <div style={{ height: 3, borderRadius: 999, background: "var(--border-subtle)", overflow: "hidden" }}>
            <motion.div
              animate={{ width: total > 1 ? `${(replaySeq / (total - 1)) * 100}%` : "0%" }}
              transition={{ duration: 0.2 }}
              style={{ height: "100%", background: "var(--accent)", borderRadius: 999, boxShadow: "0 0 8px var(--accent)" }}
            />
          </div>

          {/* Timeline dots */}
          <div
            style={{
              display:    "flex",
              gap:        4,
              overflowX:  "auto",
              padding:    "6px 0",
              alignItems: "center",
            }}
            className="cortex-scroll"
          >
            {events.map((ev, i) => (
              <TimelineDot
                key={ev.sequence}
                event={ev}
                isActive={i === replaySeq}
                isPast={i < replaySeq}
                onClick={() => { setSeq(i); setPlaying(false); }}
              />
            ))}
          </div>

          {/* Active event detail */}
          <AnimatePresence mode="wait">
            {activeEvent && <DetailPanel key={activeEvent.sequence} event={activeEvent} />}
          </AnimatePresence>
        </>
      )}
    </div>
  );
}

function MiniStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ padding: "7px 10px", borderRadius: "var(--radius-md)", border: `1px solid ${color}20`, background: `${color}06` }}>
      <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>{label}</p>
      <span className="label-mono" style={{ fontSize: "var(--font-size-lg)", fontWeight: 700, color }}>{value}</span>
    </div>
  );
}
