"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useGovernanceCenterStore } from "@/store/governanceCenterStore";
import type { PipelineStage, PipelineStatus } from "@/services/governanceCenterService";

// ── Constants ─────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<PipelineStatus, { color: string; glow: string; label: string; dot: string }> = {
  idle:     { color: "var(--text-muted)",   glow: "transparent",           label: "Idle",     dot: "#737373" },
  active:   { color: "#38bdf8",             glow: "rgba(56,189,248,0.35)", label: "Active",   dot: "#38bdf8" },
  approved: { color: "#34d399",             glow: "rgba(52,211,153,0.35)", label: "Approved", dot: "#34d399" },
  warned:   { color: "#fbbf24",             glow: "rgba(251,191,36,0.40)", label: "Warning",  dot: "#fbbf24" },
  blocked:  { color: "#f87171",             glow: "rgba(248,113,113,0.40)", label: "Blocked", dot: "#f87171" },
};

const STAGE_ICONS: Record<string, string> = {
  input_validation:    "⊕",
  policy_engine:       "⊞",
  tool_approval:       "⊙",
  execution_approval:  "⊗",
  output_validation:   "⊛",
  response_release:    "⊚",
};

function relTime(iso: string | null): string {
  if (!iso) return "—";
  const d = Date.now() - new Date(iso).getTime();
  if (d < 5000)  return "just now";
  if (d < 60000) return `${Math.floor(d / 1000)}s ago`;
  if (d < 3600000) return `${Math.floor(d / 60000)}m ago`;
  return `${Math.floor(d / 3600000)}h ago`;
}

// ── Animated connector ────────────────────────────────────────────────────

function Connector({ from, to }: { from: PipelineStatus; to: PipelineStatus }) {
  const active = from === "approved" || from === "active";
  const color  = active ? STATUS_CONFIG[from].color : "var(--border-default)";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0, margin: "0 auto" }}>
      {/* Arrow stem */}
      <motion.div
        style={{
          width:      2,
          height:     32,
          background: `linear-gradient(to bottom, ${color}, ${STATUS_CONFIG[to].color})`,
          opacity:    active ? 1 : 0.2,
          position:   "relative",
          overflow:   "hidden",
        }}
      >
        {/* Traveling pulse */}
        {active && (
          <motion.div
            animate={{ y: [-32, 32] }}
            transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
            style={{
              position:     "absolute",
              width:        2,
              height:       12,
              background:   `linear-gradient(to bottom, transparent, ${color}, transparent)`,
              filter:       `drop-shadow(0 0 4px ${color})`,
              left:         0,
            }}
          />
        )}
      </motion.div>

      {/* Arrowhead */}
      <div
        style={{
          width:     0,
          height:    0,
          borderLeft:  "4px solid transparent",
          borderRight: "4px solid transparent",
          borderTop:   `6px solid ${active ? STATUS_CONFIG[to].color : "var(--border-default)"}`,
          opacity:     active ? 1 : 0.2,
        }}
      />
    </div>
  );
}

// ── Stage card ────────────────────────────────────────────────────────────

function StageCard({ stage, index }: { stage: PipelineStage; index: number }) {
  const cfg = STATUS_CONFIG[stage.status as PipelineStatus] ?? STATUS_CONFIG.idle;

  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3 }}
      style={{
        display:      "flex",
        alignItems:   "center",
        gap:          12,
        padding:      "12px 16px",
        borderRadius: "var(--radius-lg)",
        border:       `1px solid ${stage.status === "idle" ? "var(--border-subtle)" : cfg.color + "33"}`,
        background:   stage.status === "idle"
          ? "rgba(255,255,255,0.01)"
          : `radial-gradient(ellipse at left, ${cfg.color}08, transparent 60%)`,
        position:     "relative",
        overflow:     "hidden",
        transition:   "all 0.3s",
      }}
    >
      {/* Left accent bar */}
      <div
        style={{
          position:     "absolute",
          left:         0,
          top:          0,
          bottom:       0,
          width:        2,
          background:   cfg.color,
          opacity:      stage.status === "idle" ? 0.15 : 0.8,
          borderRadius: "2px 0 0 2px",
          boxShadow:    stage.status !== "idle" ? `0 0 8px ${cfg.glow}` : "none",
        }}
      />

      {/* Icon */}
      <div
        style={{
          width:        38,
          height:       38,
          borderRadius: "var(--radius-md)",
          border:       `1px solid ${cfg.color}33`,
          background:   `${cfg.color}10`,
          display:      "flex",
          alignItems:   "center",
          justifyContent: "center",
          fontSize:     18,
          color:        cfg.color,
          flexShrink:   0,
          boxShadow:    stage.status !== "idle" ? `0 0 12px ${cfg.glow}` : "none",
          transition:   "box-shadow 0.3s",
        }}
      >
        {STAGE_ICONS[stage.id] || "◎"}
      </div>

      {/* Text */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ margin: 0, fontSize: "var(--font-size-sm)", fontWeight: 600, color: "var(--text-primary)" }}>
          {stage.label}
        </p>
        <p style={{ margin: "1px 0 0", fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          {stage.count > 0 ? `${stage.count.toLocaleString()} events` : "No events yet"}
          {stage.last_at && <span style={{ marginLeft: 6 }}>· {relTime(stage.last_at)}</span>}
        </p>
      </div>

      {/* Status pill */}
      <motion.div
        key={stage.status}
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        style={{
          display:      "flex",
          alignItems:   "center",
          gap:          5,
          padding:      "3px 10px",
          borderRadius: "var(--radius-pill)",
          background:   `${cfg.color}18`,
          border:       `1px solid ${cfg.color}33`,
          flexShrink:   0,
        }}
      >
        {/* Pulsing dot */}
        <div style={{ position: "relative", width: 6, height: 6 }}>
          <div
            style={{
              width:        6,
              height:       6,
              borderRadius: "50%",
              background:   cfg.dot,
            }}
          />
          {(stage.status === "active" || stage.status === "warned" || stage.status === "blocked") && (
            <motion.div
              animate={{ scale: [1, 2.4], opacity: [0.6, 0] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
              style={{
                position:     "absolute",
                inset:        0,
                borderRadius: "50%",
                background:   cfg.dot,
              }}
            />
          )}
        </div>
        <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: cfg.color, whiteSpace: "nowrap" }}>
          {cfg.label}
        </span>
      </motion.div>
    </motion.div>
  );
}

// ── Emergency stop banner ─────────────────────────────────────────────────

function EmergencyBanner() {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        display:      "flex",
        alignItems:   "center",
        gap:          10,
        padding:      "10px 16px",
        borderRadius: "var(--radius-md)",
        background:   "rgba(248,113,113,0.08)",
        border:       "1px solid rgba(248,113,113,0.4)",
        marginBottom: 12,
      }}
    >
      <motion.span
        animate={{ opacity: [1, 0.3, 1] }}
        transition={{ repeat: Infinity, duration: 0.7 }}
        style={{ fontSize: 16 }}
      >
        🛑
      </motion.span>
      <div>
        <p style={{ margin: 0, fontWeight: 700, fontSize: "var(--font-size-sm)", color: "#f87171" }}>
          EMERGENCY STOP ACTIVE
        </p>
        <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          All agent execution is halted. Deactivate from Governance settings.
        </p>
      </div>
    </motion.div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function SafetyPipeline() {
  const overview   = useGovernanceCenterStore((s) => s.overview);
  const isLoading  = useGovernanceCenterStore((s) => s.isOverviewLoading);
  const loadData   = useGovernanceCenterStore((s) => s.loadOverview);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-refresh every 8 seconds
  useEffect(() => {
    loadData();
    intervalRef.current = setInterval(loadData, 8000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [loadData]);

  const pipeline = overview?.pipeline ?? [];

  if (isLoading && !overview) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "var(--font-size-sm)", padding: "20px 0" }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
          style={{ width: 14, height: 14, border: "2px solid var(--border-default)", borderTopColor: "var(--accent)", borderRadius: "50%" }}
        />
        Connecting to safety pipeline…
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* Emergency stop banner */}
      {overview?.emergency_stop && <EmergencyBanner />}

      {/* Header stats */}
      {overview && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 16 }}>
          <StatChip label="Active Missions" value={overview.active_missions} color="#38bdf8" />
          <StatChip label="Approved Today"  value={overview.approved_today}  color="#34d399" />
          <StatChip label="Blocked Today"   value={overview.blocked_today}   color="#f87171" alert={overview.blocked_today > 5} />
          <StatChip label="Guardrail Hits"  value={overview.guardrail_hits}  color="#fbbf24" alert={overview.guardrail_hits > 10} />
        </div>
      )}

      {/* User Request (input top) */}
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>
        <div style={{
          padding:      "8px 20px",
          borderRadius: "var(--radius-pill)",
          border:       "1px solid rgba(56,189,248,0.3)",
          background:   "rgba(56,189,248,0.06)",
          fontSize:     "var(--font-size-xs)",
          fontWeight:   600,
          color:        "#38bdf8",
          letterSpacing: "0.04em",
        }}>
          USER REQUEST
        </div>
      </div>

      {/* Pipeline stages with connectors */}
      <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
        {pipeline.map((stage, i) => (
          <div key={stage.id}>
            <StageCard stage={stage} index={i} />
            {i < pipeline.length - 1 && (
              <div style={{ display: "flex", justifyContent: "center", padding: "2px 0" }}>
                <Connector
                  from={stage.status as PipelineStatus}
                  to={(pipeline[i + 1]?.status ?? "idle") as PipelineStatus}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Response Release at bottom */}
      <div style={{ display: "flex", justifyContent: "center", marginTop: 8 }}>
        <div style={{
          padding:      "8px 20px",
          borderRadius: "var(--radius-pill)",
          border:       "1px solid rgba(52,211,153,0.3)",
          background:   "rgba(52,211,153,0.06)",
          fontSize:     "var(--font-size-xs)",
          fontWeight:   600,
          color:        "#34d399",
          letterSpacing: "0.04em",
        }}>
          RESPONSE RELEASED
        </div>
      </div>

      {/* Refresh indicator */}
      <p style={{ textAlign: "center", margin: "12px 0 0", fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
        Live · refreshes every 8s
        {isLoading && <span style={{ marginLeft: 6, opacity: 0.6 }}>↻</span>}
      </p>
    </div>
  );
}

// ── Stat chip ─────────────────────────────────────────────────────────────

function StatChip({
  label, value, color, alert = false,
}: { label: string; value: number; color: string; alert?: boolean }) {
  return (
    <div style={{
      display:       "flex",
      flexDirection: "column",
      gap:           2,
      padding:       "8px 12px",
      borderRadius:  "var(--radius-md)",
      border:        `1px solid ${alert ? color + "55" : color + "20"}`,
      background:    `${color}08`,
    }}>
      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>{label}</span>
      <span className="label-mono" style={{ fontSize: "var(--font-size-xl)", fontWeight: 800, color, lineHeight: 1 }}>
        {value}
      </span>
    </div>
  );
}
