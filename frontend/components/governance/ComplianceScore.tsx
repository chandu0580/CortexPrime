"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { useGovernanceCenterStore } from "@/store/governanceCenterStore";
import type { ComplianceCategory } from "@/services/governanceCenterService";

// ── Grade ring ────────────────────────────────────────────────────────────

function GradeRing({ score, grade }: { score: number; grade: string }) {
  const r   = 52;
  const cx  = 66;
  const cy  = 66;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color =
    score >= 85 ? "#34d399" :
    score >= 70 ? "#fbbf24" :
    "#f87171";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg width={132} height={132} style={{ overflow: "visible" }}>
        {/* Track */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={7} />
        {/* Fill */}
        <motion.circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={7}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - fill }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ filter: `drop-shadow(0 0 8px ${color})` }}
        />
        {/* Grade */}
        <text x={cx} y={cy - 4} textAnchor="middle" style={{ fontSize: 28, fontWeight: 800, fill: color, fontFamily: "monospace" }}>
          {grade}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" style={{ fontSize: 11, fill: "#737373", fontFamily: "monospace" }}>
          {score.toFixed(1)}
        </text>
        <text x={cx} y={cy + 28} textAnchor="middle" style={{ fontSize: 9, fill: "#737373", letterSpacing: 1 }}>
          GOVERNANCE
        </text>
      </svg>
    </div>
  );
}

// ── Score bar ─────────────────────────────────────────────────────────────

function ScoreBar({ score, color }: { score: number; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 999, background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ duration: 1.0, ease: "easeOut" }}
          style={{
            height:       "100%",
            background:   `linear-gradient(to right, ${color}80, ${color})`,
            borderRadius: 999,
            boxShadow:    `0 0 8px ${color}50`,
          }}
        />
      </div>
      <span className="label-mono" style={{ fontSize: "var(--font-size-xs)", color, fontWeight: 700, minWidth: 40, textAlign: "right" }}>
        {score.toFixed(1)}
      </span>
    </div>
  );
}

// ── Category card ─────────────────────────────────────────────────────────

function CategoryCard({ cat, index }: { cat: ComplianceCategory; index: number }) {
  const color =
    cat.score >= 85 ? "#34d399" :
    cat.score >= 70 ? "#fbbf24" :
    "#f87171";

  const trend = cat.trend;
  const trendColor = trend > 0 ? "#34d399" : trend < 0 ? "#f87171" : "var(--text-muted)";
  const trendArrow = trend > 0 ? "↑" : trend < 0 ? "↓" : "→";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      style={{
        padding:       "12px 14px",
        borderRadius:  "var(--radius-lg)",
        border:        `1px solid ${color}22`,
        background:    `${color}05`,
        display:       "flex",
        flexDirection: "column",
        gap:           8,
        position:      "relative",
        overflow:      "hidden",
      }}
    >
      {/* Background glow */}
      <div style={{
        position: "absolute", top: -20, right: -20, width: 80, height: 80,
        borderRadius: "50%", background: `radial-gradient(circle, ${color}12, transparent)`,
        pointerEvents: "none",
      }} />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--text-primary)", flex: 1 }}>
          {cat.label}
        </span>
        <span style={{ fontSize: "var(--font-size-xs)", color: trendColor, fontWeight: 600 }}>
          {trendArrow} {Math.abs(trend).toFixed(1)}%
        </span>
      </div>

      {/* Score bar */}
      <ScoreBar score={cat.score} color={color} />

      {/* Details */}
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {cat.details.map((d, i) => (
          <p key={i} style={{ margin: 0, fontSize: "10px", color: "var(--text-muted)", lineHeight: 1.5 }}>
            · {d}
          </p>
        ))}
      </div>
    </motion.div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function ComplianceScore() {
  const compliance = useGovernanceCenterStore((s) => s.compliance);
  const isLoading  = useGovernanceCenterStore((s) => s.isComplianceLoading);
  const loadData   = useGovernanceCenterStore((s) => s.loadCompliance);

  useEffect(() => { loadData(); }, [loadData]);

  if (isLoading && !compliance) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-muted)", fontSize: "var(--font-size-sm)", padding: "20px 0" }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
          style={{ width: 14, height: 14, border: "2px solid var(--border-default)", borderTopColor: "var(--accent)", borderRadius: "50%" }}
        />
        Calculating compliance…
      </div>
    );
  }

  if (!compliance) {
    return (
      <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-muted)" }}>
        <div style={{ fontSize: 22, opacity: 0.25, marginBottom: 6 }}>◎</div>
        <p style={{ margin: 0, fontSize: "var(--font-size-sm)" }}>No compliance data available</p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Overall ring + timestamp */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
        <GradeRing score={compliance.overall} grade={compliance.grade} />
        <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
          Updated {new Date(compliance.updated_at).toLocaleTimeString()}
        </p>
      </div>

      {/* Overall health bar */}
      <div>
        <p style={{ margin: "0 0 6px", fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Overall Governance Health
        </p>
        <ScoreBar
          score={compliance.overall}
          color={compliance.overall >= 85 ? "#34d399" : compliance.overall >= 70 ? "#fbbf24" : "#f87171"}
        />
      </div>

      {/* Category cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {compliance.categories.map((cat, i) => (
          <CategoryCard key={cat.label} cat={cat} index={i} />
        ))}
      </div>
    </div>
  );
}
