"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useExecutiveStore } from "@/store/executiveStore";

// ── Animated counter hook ─────────────────────────────────────────────────

function useAnimatedCount(target: number, duration = 1200): number {
  const [current, setCurrent] = useState(target);
  const prev = useRef(target);

  useEffect(() => {
    if (prev.current === target) return;
    const start     = prev.current;
    const diff      = target - start;
    const startTime = performance.now();

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const t       = Math.min(elapsed / duration, 1);
      const ease    = 1 - Math.pow(1 - t, 3); // cubic ease-out
      setCurrent(Math.round(start + diff * ease));
      if (t < 1) requestAnimationFrame(tick);
      else { prev.current = target; setCurrent(target); }
    };
    requestAnimationFrame(tick);
  }, [target, duration]);

  return current;
}

// ── Status dot ────────────────────────────────────────────────────────────

function StatusDot({ status }: { status: string }) {
  const color =
    status === "online"   ? "#34d399" :
    status === "degraded" ? "#fbbf24" : "#f87171";

  return (
    <div style={{ position: "relative", width: 8, height: 8, flexShrink: 0 }}>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
      {status === "online" && (
        <motion.div
          animate={{ scale: [1, 2.2], opacity: [0.7, 0] }}
          transition={{ repeat: Infinity, duration: 1.6 }}
          style={{ position: "absolute", inset: 0, borderRadius: "50%", background: color }}
        />
      )}
    </div>
  );
}

// ── Chip ──────────────────────────────────────────────────────────────────

interface ChipProps {
  label:   string;
  value:   number | string;
  unit?:   string;
  color:   string;
  alert?:  boolean;
  animate?: boolean;
  icon?:   string;
}

function Chip({ label, value, unit = "", color, alert = false, animate = true, icon }: ChipProps) {
  const numValue   = typeof value === "number" ? value : NaN;
  const animated   = animate && !isNaN(numValue) ? numValue : null;
  const display    = useAnimatedCount(animated ?? 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        display:       "flex",
        flexDirection: "column",
        gap:           3,
        padding:       "10px 16px",
        borderRadius:  "var(--radius-lg)",
        border:        `1px solid ${alert ? color + "55" : color + "20"}`,
        background:    alert ? `${color}0c` : `${color}07`,
        position:      "relative",
        overflow:      "hidden",
        flex:          "1 1 0",
        minWidth:      0,
      }}
    >
      {/* Subtle top highlight */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: `linear-gradient(to right, transparent, ${color}40, transparent)` }} />

      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", fontWeight: 500, whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 4 }}>
        {icon && <span>{icon}</span>}
        {label}
      </span>

      <div style={{ display: "flex", alignItems: "baseline", gap: 3 }}>
        <span
          className="label-mono"
          style={{
            fontSize:   typeof value === "string" ? "var(--font-size-sm)" : "var(--font-size-xl)",
            fontWeight: 800,
            color,
            lineHeight: 1,
          }}
        >
          {animated !== null ? display.toLocaleString() : String(value)}
        </span>
        {unit && <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>{unit}</span>}
      </div>
    </motion.div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function StatusCommandBar() {
  const snapshot   = useExecutiveStore((s) => s.snapshot);
  const isLoading  = useExecutiveStore((s) => s.isLoading);
  const lastRefresh= useExecutiveStore((s) => s.lastRefresh);

  const systemStatus = snapshot?.system_status ?? "online";
  const statusColor  =
    systemStatus === "online"   ? "#34d399" :
    systemStatus === "degraded" ? "#fbbf24" : "#f87171";
  const statusLabel  =
    systemStatus === "online"   ? "All Systems Operational" :
    systemStatus === "degraded" ? "Degraded Mode" : "Emergency Stop Active";

  return (
    <div
      style={{
        display:         "flex",
        alignItems:      "center",
        gap:             8,
        padding:         "8px 12px",
        borderRadius:    "var(--radius-xl)",
        border:          `1px solid ${statusColor}22`,
        background:      `linear-gradient(to right, ${statusColor}06, transparent 40%)`,
        position:        "relative",
        overflow:        "hidden",
      }}
    >
      {/* Background grid shimmer */}
      <div style={{
        position: "absolute", inset: 0, opacity: 0.03,
        backgroundImage: "linear-gradient(rgba(255,255,255,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.4) 1px, transparent 1px)",
        backgroundSize: "24px 24px",
        pointerEvents: "none",
      }} />

      {/* System status badge */}
      <div
        style={{
          display:      "flex",
          alignItems:   "center",
          gap:          7,
          padding:      "6px 14px",
          borderRadius: "var(--radius-pill)",
          border:       `1px solid ${statusColor}33`,
          background:   `${statusColor}10`,
          flexShrink:   0,
        }}
      >
        <StatusDot status={systemStatus} />
        <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: statusColor, letterSpacing: "0.04em", whiteSpace: "nowrap" }}>
          {statusLabel}
        </span>
      </div>

      {/* Divider */}
      <div style={{ width: 1, height: 32, background: "var(--border-default)", flexShrink: 0 }} />

      {/* Chips row */}
      <div style={{ display: "flex", gap: 6, flex: 1, minWidth: 0 }}>
        <Chip label="Active Missions" value={snapshot?.active_missions ?? 0} color="#38bdf8"  icon="⊗" />
        <Chip label="Voice Sessions"  value={snapshot?.active_voice    ?? 0} color="#818cf8"  icon="◉" />
        <Chip label="Active Agents"   value={snapshot?.active_agents   ?? 0} color="#34d399"  icon="⊙" />
        <Chip label="Total Memories"  value={snapshot?.total_memories  ?? 0} color="#82c0a4"  icon="◎" />
        <Chip label="Safety Score"    value={snapshot ? `${snapshot.safety_score.toFixed(0)}%` : "—"} color="#fbbf24" icon="⊕" animate={false} />
        <Chip label="LLM Provider"    value={snapshot?.llm_provider ?? "—"} color="#a78bfa" icon="◈" animate={false} />
      </div>

      {/* Uptime + refresh */}
      <div style={{ flexShrink: 0, textAlign: "right", display: "flex", flexDirection: "column", gap: 1 }}>
        {snapshot && (
          <span className="label-mono" style={{ fontSize: "10px", color: "var(--text-muted)" }}>
            ↑ {snapshot.uptime_hours.toFixed(1)}h uptime
          </span>
        )}
        <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>
          {lastRefresh ? new Date(lastRefresh).toLocaleTimeString() : "—"}
          {isLoading && <span style={{ marginLeft: 4, opacity: 0.5 }}>↻</span>}
        </span>
      </div>
    </div>
  );
}
