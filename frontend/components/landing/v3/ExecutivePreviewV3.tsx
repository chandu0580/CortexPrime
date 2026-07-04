"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

// ── Simulated live telemetry ───────────────────────────────────────────────

function useLiveTick(interval = 1400) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), interval);
    return () => clearInterval(id);
  }, [interval]);
  return tick;
}

function rnd(min: number, max: number) {
  return Math.round(Math.random() * (max - min) + min);
}

// ── Mini bar chart ─────────────────────────────────────────────────────────

function SparkBars({ color }: { color: string }) {
  const tick = useLiveTick(800);
  const bars = Array.from({ length: 12 }, (_, i) => 20 + Math.sin((tick + i) * 0.7) * 15 + Math.random() * 10);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 28 }}>
      {bars.map((h, i) => (
        <div key={i} style={{ flex: 1, height: `${h}px`, borderRadius: "1px 1px 0 0", background: `${color}${i === bars.length - 1 ? "cc" : "55"}`, transition: "height 0.4s" }} />
      ))}
    </div>
  );
}

// ── Metric chip ────────────────────────────────────────────────────────────

function MetricChip({ label, value, color, unit = "" }: { label: string; value: number; color: string; unit?: string }) {
  const tick = useLiveTick(1800);
  const live = value + (tick % 3 === 0 ? rnd(-2, 4) : 0);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3, padding: "10px 14px", borderRadius: "var(--radius-md)", border: `1px solid ${color}22`, background: `${color}08` }}>
      <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.35)", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" }}>{label}</span>
      <span style={{ fontSize: "var(--font-size-xl)", fontWeight: 900, color, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>{live}{unit}</span>
    </div>
  );
}

// ── Agent row ──────────────────────────────────────────────────────────────

const AGENTS = [
  { id: "orchestrator", color: "#82c0a4", action: "Coordinating 5-agent pipeline" },
  { id: "planner",      color: "#4a8c70", action: "Planning research strategy" },
  { id: "research",     color: "#4a8c70", action: "Querying 3 data sources" },
  { id: "critic",       color: "#f9a825", action: "Validating confidence scores" },
  { id: "memory",       color: "#737373", action: "Consolidating 8 findings" },
];

function AgentRow({ agent, delay }: { agent: typeof AGENTS[0]; delay: number }) {
  const tick = useLiveTick(2400 + delay * 300);
  const isActive = tick % 3 !== 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: isActive ? agent.color : "rgba(255,255,255,0.15)", boxShadow: isActive ? `0 0 8px ${agent.color}` : "none", flexShrink: 0, transition: "background 0.3s, box-shadow 0.3s" }} />
      <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: isActive ? agent.color : "rgba(255,255,255,0.3)", textTransform: "capitalize", minWidth: 90 }}>{agent.id}</span>
      <span style={{ fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.3)", overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" }}>{isActive ? agent.action : "Standby"}</span>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export default function ExecutivePreviewV3() {
  return (
    <section id="executive" style={{ padding: "100px 24px", background: "var(--background)", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse at 50% 50%, rgba(130,192,164,0.05) 0%, transparent 60%)", pointerEvents: "none" }} />

      <div style={{ maxWidth: 1000, margin: "0 auto", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 3, height: 14, borderRadius: 2, background: "#82c0a4" }} />
          <span style={{ fontSize: "10px", fontWeight: 800, color: "#82c0a4", letterSpacing: "0.12em", textTransform: "uppercase" }}>Executive Command Center</span>
        </div>
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ margin: "0 0 8px", fontSize: "clamp(28px,4vw,44px)", fontWeight: 900, color: "#fff", letterSpacing: "-0.03em" }}
        >
          Total System Visibility
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          style={{ margin: "0 0 44px", fontSize: "var(--font-size-md)", color: "rgba(255,255,255,0.38)" }}
        >
          Every metric, every agent, every decision — in one cinematic interface.
        </motion.p>

        {/* Dashboard mock */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{
            borderRadius:  "var(--radius-xl)",
            border:        "1px solid rgba(255,255,255,0.07)",
            background:    "rgba(10,16,28,0.8)",
            overflow:      "hidden",
            boxShadow:     "0 40px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(130,192,164,0.1)",
          }}
        >
          {/* Fake chrome bar */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "10px 16px", borderBottom: "1px solid rgba(255,255,255,0.05)", background: "rgba(5,10,18,0.6)" }}>
            {["#f87171","#fbbf24","#34d399"].map((c) => (
              <div key={c} style={{ width: 8, height: 8, borderRadius: "50%", background: c, opacity: 0.6 }} />
            ))}
            <span style={{ marginLeft: 10, fontSize: "10px", color: "rgba(255,255,255,0.25)", fontFamily: "monospace" }}>cortexprime.ai/executive</span>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 5 }}>
              <motion.div animate={{ opacity: [1, 0.3, 1] }} transition={{ repeat: Infinity, duration: 1.2 }} style={{ width: 5, height: 5, borderRadius: "50%", background: "#82c0a4" }} />
              <span style={{ fontSize: "9px", fontWeight: 700, color: "#82c0a4", letterSpacing: "0.06em" }}>LIVE</span>
            </div>
          </div>

          <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Status bar */}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <MetricChip label="Active Missions" value={1}  color="#82c0a4" />
              <MetricChip label="Active Agents"   value={3}  color="#4a8c70" />
              <MetricChip label="Safety Score"    value={98} color="#34d399" unit="%" />
              <MetricChip label="Total Memories"  value={1247} color="#4a8c70" />
              <div style={{ flex: 1, minWidth: 140, padding: "10px 14px", borderRadius: "var(--radius-md)", border: "1px solid rgba(130,192,164,0.2)", background: "rgba(130,192,164,0.05)" }}>
                <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.35)", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", display: "block", marginBottom: 5 }}>Throughput</span>
                <SparkBars color="#82c0a4" />
              </div>
            </div>

            {/* Content row */}
            <div style={{ display: "flex", gap: 12 }}>
              {/* Agent status */}
              <div style={{ flex: 1, padding: "14px", borderRadius: "var(--radius-lg)", border: "1px solid rgba(255,255,255,0.05)", background: "rgba(255,255,255,0.02)" }}>
                <p style={{ margin: "0 0 10px", fontSize: "var(--font-size-xs)", fontWeight: 700, color: "rgba(255,255,255,0.5)", letterSpacing: "0.07em", textTransform: "uppercase" }}>Agent Activity</p>
                {AGENTS.map((a, i) => <AgentRow key={a.id} agent={a} delay={i} />)}
              </div>

              {/* Intelligence score */}
              <div style={{ flex: "0 0 200px", padding: "14px", borderRadius: "var(--radius-lg)", border: "1px solid rgba(255,255,255,0.05)", background: "rgba(255,255,255,0.02)", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                <p style={{ margin: 0, fontSize: "var(--font-size-xs)", fontWeight: 700, color: "rgba(255,255,255,0.5)", letterSpacing: "0.07em", textTransform: "uppercase" }}>Intelligence Score</p>
                <svg width={100} height={100}>
                  <circle cx={50} cy={50} r={40} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={7} />
                  <motion.circle
                    cx={50} cy={50} r={40}
                    fill="none" stroke="#82c0a4" strokeWidth={7}
                    strokeLinecap="round"
                    strokeDasharray={251.2}
                    initial={{ strokeDashoffset: 251.2 }}
                    whileInView={{ strokeDashoffset: 251.2 * (1 - 0.928) }}
                    viewport={{ once: true }}
                    transition={{ duration: 1.5, ease: "easeOut" }}
                    transform="rotate(-90 50 50)"
                    style={{ filter: "drop-shadow(0 0 8px rgba(130,192,164,0.6))" }}
                  />
                  <text x={50} y={46} textAnchor="middle" style={{ fontSize: 20, fontWeight: 900, fill: "#82c0a4", fontFamily: "monospace" }}>A+</text>
                  <text x={50} y={60} textAnchor="middle" style={{ fontSize: 9, fill: "rgba(255,255,255,0.4)" }}>92.8</text>
                </svg>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, width: "100%" }}>
                  {[["Reasoning", 94, "#818cf8"], ["Execution", 91, "#82c0a4"], ["Safety", 98, "#34d399"]].map(([l, v, c]) => (
                    <div key={String(l)} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.35)", minWidth: 62 }}>{l}</span>
                      <div style={{ flex: 1, height: 3, borderRadius: 999, background: "rgba(255,255,255,0.06)" }}>
                        <motion.div
                          initial={{ width: 0 }}
                          whileInView={{ width: `${v}%` }}
                          viewport={{ once: true }}
                          transition={{ duration: 1, ease: "easeOut" }}
                          style={{ height: "100%", background: String(c), borderRadius: 999 }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          style={{ textAlign: "center", marginTop: 32 }}
        >
          <a href="/executive" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 28px", borderRadius: "var(--radius-pill)", background: "linear-gradient(135deg, #82c0a4, #4a8c70)", color: "#fff", fontSize: "var(--font-size-sm)", fontWeight: 800, textDecoration: "none", boxShadow: "0 0 24px rgba(130,192,164,0.3)" }}>
            Open Executive Center →
          </a>
        </motion.div>
      </div>
    </section>
  );
}
