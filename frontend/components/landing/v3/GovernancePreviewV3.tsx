"use client";

import { motion } from "framer-motion";

// ── Safety pipeline stages ─────────────────────────────────────────────────

const STAGES = [
  { id: "input",      label: "User Request",    color: "#737373", icon: "→",  status: "pass",   detail: "PII scan + intent classification" },
  { id: "policy",     label: "Policy Filter",   color: "#4a8c70", icon: "⊕",  status: "pass",   detail: "Content policy validation" },
  { id: "guardrail",  label: "Guardrail Engine", color: "#f59e0b", icon: "⊗", status: "warn",   detail: "Risk scoring: 2/100 flagged" },
  { id: "approval",   label: "Approval Queue",  color: "#f9a825", icon: "◈",  status: "pass",   detail: "Human-in-the-loop checkpoint" },
  { id: "audit",      label: "Audit Log",       color: "#4a8c70", icon: "◉",  status: "pass",   detail: "Immutable event trail created" },
  { id: "response",   label: "Release",         color: "#34d399", icon: "✓",  status: "pass",   detail: "Response authorized & released" },
];

const STATUS_COLORS: Record<string, string> = { pass: "#34d399", warn: "#fbbf24", block: "#f87171" };

// ── Risk gauge ─────────────────────────────────────────────────────────────

function RiskGauge({ score, label }: { score: number; label: string }) {
  const r    = 32;
  const circ = Math.PI * r;  // half circle
  const fill = (score / 100) * circ;
  const color = score < 30 ? "#34d399" : score < 70 ? "#fbbf24" : "#f87171";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={80} height={44} viewBox="0 0 80 44">
        <path d={`M 8,40 A 32,32 0 0,1 72,40`} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={6} strokeLinecap="round" />
        <motion.path
          d={`M 8,40 A 32,32 0 0,1 72,40`}
          fill="none"
          stroke={color}
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          whileInView={{ strokeDashoffset: circ - fill }}
          viewport={{ once: true }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
        <text x={40} y={35} textAnchor="middle" style={{ fontSize: 14, fontWeight: 900, fill: color, fontFamily: "monospace" }}>{score}</text>
      </svg>
      <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.35)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export default function GovernancePreviewV3() {
  return (
    <section id="governance" style={{ padding: "100px 24px", background: "var(--background)", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.025) 1px, transparent 1px)", backgroundSize: "28px 28px", pointerEvents: "none" }} />

      <div style={{ maxWidth: 1000, margin: "0 auto", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 3, height: 14, borderRadius: 2, background: "#f87171" }} />
          <span style={{ fontSize: "10px", fontWeight: 800, color: "#f87171", letterSpacing: "0.12em", textTransform: "uppercase" }}>Governance & Safety</span>
        </div>
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ margin: "0 0 8px", fontSize: "clamp(28px,4vw,44px)", fontWeight: 900, color: "#fff", letterSpacing: "-0.03em" }}
        >
          Safety Without Compromise
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          style={{ margin: "0 0 44px", fontSize: "var(--font-size-md)", color: "rgba(255,255,255,0.38)" }}
        >
          Every AI action flows through a six-stage safety pipeline before release.
        </motion.p>

        <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          {/* Safety pipeline */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            style={{ flex: "1 1 420px", padding: "20px", borderRadius: "var(--radius-xl)", border: "1px solid rgba(248,113,113,0.15)", background: "rgba(248,113,113,0.04)" }}
          >
            <p style={{ margin: "0 0 16px", fontSize: "var(--font-size-xs)", fontWeight: 700, color: "rgba(255,255,255,0.5)", letterSpacing: "0.07em", textTransform: "uppercase" }}>Live Safety Pipeline</p>

            {/* Top + bottom labels */}
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
              <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.25)", letterSpacing: "0.06em" }}>USER REQUEST</span>
              <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.25)", letterSpacing: "0.06em" }}>RESPONSE RELEASED</span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
              {STAGES.map((stage, i) => (
                <div key={stage.id}>
                  <motion.div
                    initial={{ opacity: 0, x: -12 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.08 }}
                    style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: "var(--radius-md)", border: `1px solid ${stage.color}20`, background: `${stage.color}06` }}
                  >
                    <span style={{ fontSize: 13, color: stage.color, width: 16, textAlign: "center", flexShrink: 0 }}>{stage.icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ margin: 0, fontSize: "var(--font-size-xs)", fontWeight: 700, color: "#fff" }}>{stage.label}</p>
                      <p style={{ margin: 0, fontSize: "9px", color: "rgba(255,255,255,0.35)" }}>{stage.detail}</p>
                    </div>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: STATUS_COLORS[stage.status], boxShadow: `0 0 8px ${STATUS_COLORS[stage.status]}`, flexShrink: 0 }} />
                  </motion.div>
                  {i < STAGES.length - 1 && (
                    <div style={{ marginLeft: 26, width: 1, height: 6, background: "rgba(255,255,255,0.06)" }} />
                  )}
                </div>
              ))}
            </div>
          </motion.div>

          {/* Risk + compliance */}
          <div style={{ flex: "0 0 260px", display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Risk scores */}
            <motion.div
              initial={{ opacity: 0, x: 16 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              style={{ padding: "18px", borderRadius: "var(--radius-xl)", border: "1px solid rgba(255,255,255,0.07)", background: "rgba(255,255,255,0.02)" }}
            >
              <p style={{ margin: "0 0 14px", fontSize: "var(--font-size-xs)", fontWeight: 700, color: "rgba(255,255,255,0.5)", letterSpacing: "0.07em", textTransform: "uppercase" }}>Risk Scoring</p>
              <div style={{ display: "flex", justifyContent: "space-around" }}>
                <RiskGauge score={8}  label="Today" />
                <RiskGauge score={22} label="7-day" />
                <RiskGauge score={15} label="30-day" />
              </div>
            </motion.div>

            {/* Compliance */}
            <motion.div
              initial={{ opacity: 0, x: 16 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              style={{ padding: "18px", borderRadius: "var(--radius-xl)", border: "1px solid rgba(255,255,255,0.07)", background: "rgba(255,255,255,0.02)", flex: 1 }}
            >
              <p style={{ margin: "0 0 14px", fontSize: "var(--font-size-xs)", fontWeight: 700, color: "rgba(255,255,255,0.5)", letterSpacing: "0.07em", textTransform: "uppercase" }}>Compliance</p>
              {[
                { label: "Safety Score",   score: 98, color: "#34d399" },
                { label: "Policy Score",   score: 96, color: "#82c0a4" },
                { label: "Governance",     score: 99, color: "#818cf8" },
              ].map((item) => (
                <div key={item.label} style={{ marginBottom: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.5)" }}>{item.label}</span>
                    <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: item.color, fontFamily: "monospace" }}>{item.score}%</span>
                  </div>
                  <div style={{ height: 4, borderRadius: 999, background: "rgba(255,255,255,0.06)" }}>
                    <motion.div
                      initial={{ width: 0 }}
                      whileInView={{ width: `${item.score}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 1.2, ease: "easeOut" }}
                      style={{ height: "100%", background: `linear-gradient(to right, ${item.color}60, ${item.color})`, borderRadius: 999, boxShadow: `0 0 8px ${item.color}40` }}
                    />
                  </div>
                </div>
              ))}
            </motion.div>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          style={{ textAlign: "center", marginTop: 32 }}
        >
          <a href="/governance-center" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 28px", borderRadius: "var(--radius-pill)", background: "rgba(248,113,113,0.12)", border: "1.5px solid rgba(248,113,113,0.3)", color: "#f87171", fontSize: "var(--font-size-sm)", fontWeight: 800, textDecoration: "none" }}>
            Open Governance Center →
          </a>
        </motion.div>
      </div>
    </section>
  );
}
