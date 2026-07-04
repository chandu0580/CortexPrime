"use client";

import { motion } from "framer-motion";

const CAPABILITIES = [
  {
    icon:   "🎙️",
    title:  "Voice Intelligence",
    color:  "#f59e0b",
    href:   "/voice",
    bullets: ["Wake-word detection", "Whisper STT (97%+ accuracy)", "Natural TTS synthesis", "Real-time conversation"],
    badge:  "Live",
  },
  {
    icon:   "🧠",
    title:  "Multi-Agent Reasoning",
    color:  "#82c0a4",
    href:   "/command",
    bullets: ["5 specialized agents", "Parallel task execution", "Critic validation layer", "Optimizer synthesis"],
    badge:  "Core",
  },
  {
    icon:   "🗄️",
    title:  "Memory System",
    color:  "#4a8c70",
    href:   "/memory-explorer",
    bullets: ["Episodic + semantic memory", "ChromaDB vector search", "Reflection & consolidation", "Cross-session recall"],
    badge:  "Persistent",
  },
  {
    icon:   "🖥️",
    title:  "Computer Control",
    color:  "#a78bfa",
    href:   "/operator",
    bullets: ["Desktop automation", "Screenshot + OCR vision", "GUI interaction", "pyautogui integration"],
    badge:  "Autonomous",
  },
  {
    icon:   "🌐",
    title:  "Browser Automation",
    color:  "#38bdf8",
    href:   "/operator",
    bullets: ["Full Playwright control", "Web research at scale", "Form filling & extraction", "Multi-tab orchestration"],
    badge:  "Autonomous",
  },
  {
    icon:   "🛡️",
    title:  "Governance & Safety",
    color:  "#f87171",
    href:   "/governance-center",
    bullets: ["Real-time guardrails", "Human approval queue", "Compliance scoring", "Full audit trail"],
    badge:  "Always On",
  },
  {
    icon:   "▶",
    title:  "Mission Replay",
    color:  "#818cf8",
    href:   "/replay",
    bullets: ["Step-by-step playback", "Agent state reconstruction", "Timeline visualization", "Governance review"],
    badge:  "Complete",
  },
  {
    icon:   "⚡",
    title:  "Executive Command",
    color:  "#4a8c70",
    href:   "/executive",
    bullets: ["Real-time system view", "Autonomy intelligence score", "Analytics dashboard", "Live agent graph"],
    badge:  "Flagship",
  },
];

function CapabilityCard({ cap, index }: { cap: typeof CAPABILITIES[0]; index: number }) {
  return (
    <motion.a
      href={cap.href}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ delay: index * 0.06, duration: 0.5 }}
      whileHover={{ y: -4, scale: 1.02 }}
      style={{
        display:        "flex",
        flexDirection:  "column",
        gap:            12,
        padding:        "20px",
        borderRadius:   "var(--radius-xl)",
        border:         `1px solid ${cap.color}20`,
        background:     `${cap.color}06`,
        textDecoration: "none",
        position:       "relative",
        overflow:       "hidden",
        cursor:         "pointer",
        transition:     "border-color 0.2s",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = `${cap.color}45`; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = `${cap.color}20`; }}
    >
      {/* Corner glow */}
      <div style={{ position: "absolute", top: -20, right: -20, width: 80, height: 80, borderRadius: "50%", background: `${cap.color}10`, filter: "blur(20px)", pointerEvents: "none" }} />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 22 }}>{cap.icon}</span>
        <span style={{ fontSize: "9px", fontWeight: 800, color: cap.color, background: `${cap.color}15`, border: `1px solid ${cap.color}25`, padding: "2px 7px", borderRadius: "var(--radius-pill)", letterSpacing: "0.05em" }}>
          {cap.badge}
        </span>
      </div>

      {/* Title */}
      <p style={{ margin: 0, fontSize: "var(--font-size-md)", fontWeight: 800, color: "#fff", letterSpacing: "-0.01em" }}>
        {cap.title}
      </p>

      {/* Bullets */}
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {cap.bullets.map((b) => (
          <div key={b} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 3, height: 3, borderRadius: "50%", background: cap.color, flexShrink: 0 }} />
            <span style={{ fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.45)", lineHeight: 1.3 }}>{b}</span>
          </div>
        ))}
      </div>

      {/* Link */}
      <div style={{ marginTop: "auto", paddingTop: 8, display: "flex", alignItems: "center", gap: 4 }}>
        <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: cap.color }}>Explore</span>
        <span style={{ fontSize: "var(--font-size-xs)", color: cap.color }}>→</span>
      </div>
    </motion.a>
  );
}

export default function CapabilitiesV3() {
  return (
    <section id="capabilities" style={{ padding: "100px 24px", background: "var(--background)", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.025) 1px, transparent 1px)", backgroundSize: "28px 28px", pointerEvents: "none" }} />

      <div style={{ maxWidth: 1100, margin: "0 auto", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 3, height: 14, borderRadius: 2, background: "#82c0a4" }} />
          <span style={{ fontSize: "10px", fontWeight: 800, color: "#82c0a4", letterSpacing: "0.12em", textTransform: "uppercase" }}>AI Capabilities</span>
        </div>

        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ margin: "0 0 8px", fontSize: "clamp(28px,4vw,44px)", fontWeight: 900, color: "#fff", letterSpacing: "-0.03em" }}
        >
          The Full Intelligence Stack
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          style={{ margin: "0 0 52px", fontSize: "var(--font-size-md)", color: "rgba(255,255,255,0.38)" }}
        >
          Every capability working together as one unified autonomous system.
        </motion.p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 14 }}>
          {CAPABILITIES.map((cap, i) => (
            <CapabilityCard key={cap.title} cap={cap} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
