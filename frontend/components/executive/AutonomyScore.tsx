"use client";

import { motion } from "framer-motion";
import { useExecutiveStore } from "@/store/executiveStore";
import type { AutonomyDimension } from "@/services/executiveService";

const EMPTY_AUTONOMY: AutonomyDimension[] = [];

// ── Radial intelligence ring ──────────────────────────────────────────────

function IntelligenceRing({ overall }: { overall: number }) {
  const size  = 140;
  const r     = 54;
  const cx    = 70;
  const cy    = 70;
  const circ  = 2 * Math.PI * r;
  const fill  = (overall / 100) * circ;

  const color =
    overall >= 88 ? "#34d399" :
    overall >= 75 ? "#82c0a4" :
    overall >= 60 ? "#fbbf24" : "#f87171";

  const grade =
    overall >= 92 ? "A+" :
    overall >= 85 ? "A"  :
    overall >= 78 ? "B+" :
    overall >= 70 ? "B"  : "C";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg width={size} height={size} style={{ overflow: "visible" }}>
        {/* Outer glow ring */}
        <circle cx={cx} cy={cy} r={r + 4} fill="none" stroke={`${color}10`} strokeWidth={12} />
        {/* Track */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={8} />
        {/* Fill */}
        <motion.circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - fill }}
          transition={{ duration: 1.6, ease: "easeOut" }}
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ filter: `drop-shadow(0 0 10px ${color})` }}
        />
        {/* Grade */}
        <text x={cx} y={cy - 8} textAnchor="middle"
          style={{ fontSize: 30, fontWeight: 900, fill: color, fontFamily: "monospace" }}>
          {grade}
        </text>
        {/* Score */}
        <text x={cx} y={cy + 12} textAnchor="middle"
          style={{ fontSize: 13, fontWeight: 700, fill: color, fontFamily: "monospace" }}>
          {overall.toFixed(1)}
        </text>
        {/* Label */}
        <text x={cx} y={cy + 28} textAnchor="middle"
          style={{ fontSize: 8, fill: "#737373", letterSpacing: 1.5 }}>
          INTELLIGENCE SCORE
        </text>
      </svg>

      {/* Subtitle */}
      <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-muted)", textAlign: "center" }}>
        {overall >= 88 ? "Peak Autonomous Operation" :
         overall >= 75 ? "Full Operational Capacity" :
         overall >= 60 ? "Partial Capacity" : "Initializing"}
      </p>
    </div>
  );
}

// ── Dimension bar ─────────────────────────────────────────────────────────

const DIM_COLORS: Record<string, string> = {
  Reasoning:   "#818cf8",
  Execution:   "#82c0a4",
  Memory:      "#4a8c70",
  Safety:      "#34d399",
  Reliability: "#38bdf8",
};

function DimensionBar({ dim, index }: { dim: AutonomyDimension; index: number }) {
  const color = DIM_COLORS[dim.label] ?? "var(--accent)";

  return (
    <motion.div
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.08 }}
      style={{ display: "flex", flexDirection: "column", gap: 3 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: "var(--font-size-xs)", color, fontWeight: 600, minWidth: 72 }}>
          {dim.label}
        </span>
        <div style={{ flex: 1, height: 5, borderRadius: 999, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${dim.score}%` }}
            transition={{ duration: 1.0, ease: "easeOut", delay: index * 0.08 }}
            style={{
              height:     "100%",
              background: `linear-gradient(to right, ${color}70, ${color})`,
              borderRadius: 999,
              boxShadow:  `0 0 8px ${color}50`,
            }}
          />
        </div>
        <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color, minWidth: 36, textAlign: "right" }}>
          {dim.score.toFixed(0)}
        </span>
      </div>
      <p style={{ margin: 0, fontSize: "9px", color: "var(--text-muted)", paddingLeft: 78, lineHeight: 1 }}>
        {dim.detail}
      </p>
    </motion.div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function AutonomyScore() {
  const dims    = useExecutiveStore((s) => s.snapshot?.autonomy) ?? EMPTY_AUTONOMY;
  const overall = useExecutiveStore((s) => s.snapshot?.autonomy_overall ?? 0);
  const loading = useExecutiveStore((s) => s.isLoading);

  if (loading && dims.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, opacity: 0.4, padding: "20px 0" }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
          style={{ width: 24, height: 24, border: "3px solid var(--border-default)", borderTopColor: "var(--accent)", borderRadius: "50%" }}
        />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, alignItems: "center" }}>
      {/* Ring */}
      <IntelligenceRing overall={overall} />

      {/* Dimension bars */}
      <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 7 }}>
        {dims.map((d, i) => (
          <DimensionBar key={d.label} dim={d} index={i} />
        ))}
      </div>
    </div>
  );
}
