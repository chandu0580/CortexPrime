"use client";

import { motion } from "framer-motion";

const TECH_ITEMS = [
  {
    icon:    "🎙️",
    title:   "Voice Runtime",
    color:   "#f59e0b",
    stack:   ["edge-TTS synthesis", "Whisper STT", "Wake-word detection", "SpeechRecognition"],
    status:  "Production Ready",
    detail:  "Sub-200ms voice roundtrip. Multi-language support. Always-on wake-word with <0.1% false positive rate.",
  },
  {
    icon:    "🖥️",
    title:   "Computer Agent",
    color:   "#a78bfa",
    stack:   ["pyautogui automation", "mss screenshots", "Tesseract OCR", "CV2 vision"],
    status:  "Autonomous",
    detail:  "Full desktop control. Screen-level reasoning. Pixel-accurate GUI interaction with visual verification.",
  },
  {
    icon:    "🌐",
    title:   "Browser Agent",
    color:   "#38bdf8",
    stack:   ["Playwright async", "Multi-tab control", "DOM extraction", "Form automation"],
    status:  "Autonomous",
    detail:  "Headless + headed modes. JavaScript execution. Cookie/session management. Anti-detection stealth.",
  },
  {
    icon:    "⚡",
    title:   "Multi-LLM Router",
    color:   "#82c0a4",
    stack:   ["GPT-4o / GPT-4o-mini", "Claude 3.5 Sonnet", "Gemini 1.5 Pro", "Local Ollama"],
    status:  "Dynamic Routing",
    detail:  "Cost-latency optimization. Provider fallback. Streaming responses. Context-aware model selection.",
  },
  {
    icon:    "💾",
    title:   "Runtime Persistence",
    color:   "#4a8c70",
    stack:   ["ChromaDB vectors", "PostgreSQL async", "Redis cache", "Episodic replay"],
    status:  "Persistent",
    detail:  "Cross-session memory. Checkpoint recovery. Sub-10ms vector retrieval at 1M+ embedding scale.",
  },
  {
    icon:    "🔒",
    title:   "Security Layer",
    color:   "#f87171",
    stack:   ["JWT auth", "Rate limiting", "Prompt injection guard", "Audit logging"],
    status:  "OWASP Compliant",
    detail:  "OWASP Top 10 hardening. Input sanitization. Immutable audit trail. Human-in-the-loop controls.",
  },
];

function TechCard({ item, index }: { item: typeof TECH_ITEMS[0]; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ delay: index * 0.07 }}
      style={{
        padding:       "20px",
        borderRadius:  "var(--radius-xl)",
        border:        `1px solid ${item.color}20`,
        background:    `${item.color}05`,
        position:      "relative",
        overflow:      "hidden",
      }}
    >
      {/* Corner accent */}
      <div style={{ position: "absolute", top: 0, right: 0, width: 60, height: 60, background: `radial-gradient(circle at top right, ${item.color}15, transparent 70%)`, pointerEvents: "none" }} />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 20 }}>{item.icon}</span>
          <span style={{ fontSize: "var(--font-size-md)", fontWeight: 800, color: "#fff" }}>{item.title}</span>
        </div>
        <span style={{ fontSize: "9px", fontWeight: 700, color: item.color, background: `${item.color}15`, border: `1px solid ${item.color}25`, padding: "2px 7px", borderRadius: "var(--radius-pill)", letterSpacing: "0.04em", whiteSpace: "nowrap" }}>
          {item.status}
        </span>
      </div>

      {/* Detail */}
      <p style={{ margin: "0 0 14px", fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.45)", lineHeight: 1.55 }}>
        {item.detail}
      </p>

      {/* Stack chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
        {item.stack.map((s) => (
          <span key={s} style={{ fontSize: "9px", fontWeight: 600, color: "rgba(255,255,255,0.35)", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", padding: "2px 7px", borderRadius: "var(--radius-pill)", fontFamily: "monospace" }}>
            {s}
          </span>
        ))}
      </div>
    </motion.div>
  );
}

export default function TechExcellenceV3() {
  return (
    <section style={{ padding: "100px 24px", background: "var(--background)", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.025) 1px, transparent 1px)", backgroundSize: "28px 28px", pointerEvents: "none" }} />

      <div style={{ maxWidth: 1100, margin: "0 auto", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 3, height: 14, borderRadius: 2, background: "#4a8c70" }} />
          <span style={{ fontSize: "10px", fontWeight: 800, color: "#4a8c70", letterSpacing: "0.12em", textTransform: "uppercase" }}>Technical Excellence</span>
        </div>
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ margin: "0 0 8px", fontSize: "clamp(28px,4vw,44px)", fontWeight: 900, color: "#fff", letterSpacing: "-0.03em" }}
        >
          Built for Production
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          style={{ margin: "0 0 52px", fontSize: "var(--font-size-md)", color: "rgba(255,255,255,0.38)" }}
        >
          Every runtime component engineered to enterprise standards.
        </motion.p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
          {TECH_ITEMS.map((item, i) => (
            <TechCard key={item.title} item={item} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
