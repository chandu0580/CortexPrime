"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

// ── Animated counter hook ──────────────────────────────────────────────────

function useCountUp(target: number, duration = 2000, started: boolean) {
  const [val, setVal] = useState(0);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    if (!started) return;
    const start = performance.now();
    function tick(now: number) {
      const t = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3); // cubic ease-out
      setVal(Math.round(ease * target));
      if (t < 1) raf.current = requestAnimationFrame(tick);
    }
    raf.current = requestAnimationFrame(tick);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [target, duration, started]);

  return val;
}

// ── Single metric ──────────────────────────────────────────────────────────

const METRICS = [
  { label: "Specialized Agents",  value: 5,    suffix: "",    color: "#82c0a4", icon: "⊙", detail: "Orchestrator, Planner, Research, Critic, Optimizer" },
  { label: "Memory Records",      value: 1247, suffix: "+",   color: "#4a8c70", icon: "◈", detail: "Episodic, semantic, short-term, and reflection stores" },
  { label: "Platform Pages",      value: 21,   suffix: "",    color: "#4a8c70", icon: "⊞", detail: "Full-stack autonomous AI operating system" },
  { label: "Safety Pipeline Stages", value: 6, suffix: "",   color: "#f87171", icon: "⊕", detail: "Input → Policy → Guardrail → Approval → Audit → Release" },
  { label: "LLM Providers",       value: 4,    suffix: "",    color: "#818cf8", icon: "◉", detail: "GPT-4o · Claude 3.5 · Gemini 1.5 · Ollama (local)" },
  { label: "Autonomy Score",      value: 92,   suffix: ".8",  color: "#34d399", icon: "◎", detail: "A+ grade across Reasoning, Execution, Memory, Safety" },
];

function MetricCard({ m, index }: { m: typeof METRICS[0]; index: number }) {
  const [started, setStarted] = useState(false);
  const count = useCountUp(m.value, 1800, started);

  return (
    <motion.div
      initial={{ opacity: 0, y: 24, scale: 0.95 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ delay: index * 0.08, duration: 0.5 }}
      onViewportEnter={() => setStarted(true)}
      style={{
        display:        "flex",
        flexDirection:  "column",
        gap:            10,
        padding:        "24px 20px",
        borderRadius:   "var(--radius-xl)",
        border:         `1px solid ${m.color}20`,
        background:     `${m.color}06`,
        position:       "relative",
        overflow:       "hidden",
      }}
    >
      {/* Background gradient */}
      <div style={{ position: "absolute", inset: 0, background: `radial-gradient(ellipse at 80% 20%, ${m.color}08, transparent 60%)`, pointerEvents: "none" }} />

      {/* Icon */}
      <span style={{ fontSize: 18, color: m.color }}>{m.icon}</span>

      {/* Counter */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 1 }}>
        <span style={{ fontSize: "clamp(32px, 5vw, 52px)", fontWeight: 900, color: m.color, letterSpacing: "-0.04em", fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>
          {count.toLocaleString()}
        </span>
        {m.suffix && (
          <span style={{ fontSize: "clamp(18px, 2.5vw, 28px)", fontWeight: 900, color: m.color, opacity: 0.7 }}>
            {m.suffix}
          </span>
        )}
      </div>

      {/* Label */}
      <p style={{ margin: 0, fontSize: "var(--font-size-sm)", fontWeight: 700, color: "#fff", lineHeight: 1.2 }}>
        {m.label}
      </p>

      {/* Detail */}
      <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.35)", lineHeight: 1.4 }}>
        {m.detail}
      </p>

      {/* Bottom bar */}
      <motion.div
        initial={{ width: 0 }}
        whileInView={{ width: "60%" }}
        viewport={{ once: true }}
        transition={{ delay: index * 0.08 + 0.3, duration: 0.8, ease: "easeOut" }}
        style={{ position: "absolute", bottom: 0, left: 0, height: 2, background: `linear-gradient(to right, ${m.color}, transparent)`, borderRadius: "0 2px 0 0" }}
      />
    </motion.div>
  );
}

export default function MetricsV3() {
  return (
    <section style={{ padding: "100px 24px", background: "var(--background)", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse at 50% 50%, rgba(130,192,164,0.04) 0%, transparent 60%)", pointerEvents: "none" }} />
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.025) 1px, transparent 1px)", backgroundSize: "28px 28px", pointerEvents: "none" }} />

      <div style={{ maxWidth: 1100, margin: "0 auto", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 3, height: 14, borderRadius: 2, background: "#82c0a4" }} />
          <span style={{ fontSize: "10px", fontWeight: 800, color: "#82c0a4", letterSpacing: "0.12em", textTransform: "uppercase" }}>System Metrics</span>
        </div>
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ margin: "0 0 8px", fontSize: "clamp(28px,4vw,44px)", fontWeight: 900, color: "#fff", letterSpacing: "-0.03em" }}
        >
          Numbers That Matter
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          style={{ margin: "0 0 52px", fontSize: "var(--font-size-md)", color: "rgba(255,255,255,0.38)" }}
        >
          The scale of a fully autonomous AI operating system.
        </motion.p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 14 }}>
          {METRICS.map((m, i) => (
            <MetricCard key={m.label} m={m} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
