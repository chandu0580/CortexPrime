"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";

// ── Live cognition feed data (static for landing) ──────────────────────────

const FEED_EVENTS = [
  { agent: "orchestrator", color: "#82c0a4", type: "mission_started",    msg: "Autonomous research mission initialized — 5 agents deployed" },
  { agent: "planner",      color: "#4a8c70", type: "planning",           msg: "Decomposing task into 8 research queries across 4 domains" },
  { agent: "research",     color: "#4a8c70", type: "tool_called",        msg: "web_search: querying 3 academic databases simultaneously" },
  { agent: "critic",       color: "#f9a825", type: "tool_completed",     msg: "Quality validation: 96/100 confidence — 14 sources verified" },
  { agent: "memory",       color: "#737373", type: "memory_stored",      msg: "Consolidating 23 insights to semantic memory store" },
  { agent: "optimizer",    color: "#96cead", type: "response_generated", msg: "Executive summary generated — 5 key findings synthesized" },
  { agent: "orchestrator", color: "#82c0a4", type: "mission_completed",  msg: "Mission complete — all agents returning to standby" },
  { agent: "research",     color: "#4a8c70", type: "memory_retrieved",   msg: "Episodic recall: 8 similar past missions retrieved" },
];

// ── Floating agent chips ───────────────────────────────────────────────────

const AGENTS = [
  { id: "orchestrator", color: "#82c0a4", label: "Orchestrator", x: "8%",  y: "28%" },
  { id: "planner",      color: "#4a8c70", label: "Planner",      x: "78%", y: "22%" },
  { id: "research",     color: "#4a8c70", label: "Research",     x: "72%", y: "68%" },
  { id: "critic",       color: "#f9a825", label: "Critic",       x: "14%", y: "72%" },
  { id: "memory",       color: "#737373", label: "Memory",       x: "88%", y: "46%" },
  { id: "optimizer",    color: "#96cead", label: "Optimizer",    x: "5%",  y: "52%" },
];

function FloatingAgent({ agent, delay }: { agent: typeof AGENTS[0]; delay: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.7 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.6 }}
      style={{
        position:     "absolute",
        left:         agent.x,
        top:          agent.y,
        display:      "flex",
        alignItems:   "center",
        gap:          6,
        padding:      "5px 10px",
        borderRadius: "var(--radius-pill)",
        border:       `1px solid ${agent.color}35`,
        background:   `${agent.color}10`,
        backdropFilter: "blur(8px)",
        pointerEvents: "none",
      }}
    >
      <motion.div
        animate={{ opacity: [1, 0.4, 1] }}
        transition={{ repeat: Infinity, duration: 1.8, delay: delay * 0.5 }}
        style={{ width: 5, height: 5, borderRadius: "50%", background: agent.color, boxShadow: `0 0 8px ${agent.color}` }}
      />
      <span style={{ fontSize: "10px", fontWeight: 700, color: agent.color, letterSpacing: "0.04em" }}>
        {agent.label}
      </span>
    </motion.div>
  );
}

// ── AI Orb ─────────────────────────────────────────────────────────────────

function AIOrb() {
  return (
    <div style={{ position: "relative", width: 200, height: 200, flexShrink: 0 }}>
      {/* Outer rings */}
      {[140, 160, 180, 200].map((size, i) => (
        <motion.div
          key={size}
          animate={{ rotate: i % 2 === 0 ? 360 : -360, scale: [1, 1.02, 1] }}
          transition={{ rotate: { repeat: Infinity, duration: 12 + i * 4, ease: "linear" }, scale: { repeat: Infinity, duration: 3 + i, ease: "easeInOut" } }}
          style={{
            position:     "absolute",
            inset:        `${(200 - size) / 2}px`,
            borderRadius: "50%",
            border:       `1px solid rgba(130,192,164,${0.12 - i * 0.02})`,
            boxShadow:    `0 0 ${12 + i * 4}px rgba(130,192,164,${0.06 - i * 0.01})`,
          }}
        />
      ))}
      {/* Core orb */}
      <motion.div
        animate={{ scale: [1, 1.06, 1] }}
        transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
        style={{
          position:     "absolute",
          inset:        50,
          borderRadius: "50%",
          background:   "radial-gradient(circle at 35% 35%, rgba(150,206,173,0.95), rgba(130,192,164,0.75) 40%, rgba(74,140,112,0.85))",
          boxShadow:    "0 0 60px rgba(130,192,164,0.5), inset 0 0 30px rgba(150,206,173,0.25)",
        }}
      />
      {/* Inner particles */}
      {[0, 60, 120, 180, 240, 300].map((deg, i) => (
        <motion.div
          key={deg}
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 6 + i, ease: "linear" }}
          style={{ position: "absolute", inset: 0, borderRadius: "50%" }}
        >
          <div style={{
            position:     "absolute",
            top:          "50%",
            left:         "50%",
            width:        3,
            height:       3,
            borderRadius: "50%",
            background:   "#96cead",
            boxShadow:    "0 0 6px #96cead",
            transform:    `rotate(${deg}deg) translateX(45px) translateY(-50%)`,
          }} />
        </motion.div>
      ))}
      {/* Central pulse */}
      <motion.div
        animate={{ scale: [1, 1.5, 1], opacity: [0.6, 0, 0.6] }}
        transition={{ repeat: Infinity, duration: 2.5, ease: "easeOut" }}
        style={{ position: "absolute", inset: 45, borderRadius: "50%", border: "1px solid rgba(130,192,164,0.5)" }}
      />
    </div>
  );
}

// ── Cognition feed ─────────────────────────────────────────────────────────

function CognitionFeed() {
  const [visible, setVisible] = useState<typeof FEED_EVENTS>([]);
  const idx = useRef(0);

  useEffect(() => {
    setVisible([FEED_EVENTS[0]]);
    idx.current = 1;
    const id = setInterval(() => {
      setVisible((prev) => [FEED_EVENTS[idx.current % FEED_EVENTS.length], ...prev].slice(0, 5));
      idx.current++;
    }, 1800);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, width: 360, maxWidth: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 6 }}>
        <motion.div animate={{ opacity: [1, 0.3, 1] }} transition={{ repeat: Infinity, duration: 1.2 }}
          style={{ width: 5, height: 5, borderRadius: "50%", background: "#82c0a4" }} />
        <span style={{ fontSize: "9px", fontWeight: 800, color: "#82c0a4", letterSpacing: "0.1em" }}>LIVE COGNITION STREAM</span>
      </div>
      <AnimatePresence initial={false} mode="popLayout">
        {visible.map((ev, i) => (
          <motion.div
            key={`${ev.agent}-${ev.type}-${i}`}
            initial={{ opacity: 0, x: -10, height: 0 }}
            animate={{ opacity: 1 - i * 0.18, x: 0, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              display:      "flex",
              alignItems:   "flex-start",
              gap:          7,
              padding:      "5px 8px",
              borderRadius: "var(--radius-md)",
              border:       `1px solid ${ev.color}${i === 0 ? "30" : "15"}`,
              background:   `${ev.color}${i === 0 ? "0c" : "05"}`,
            }}
          >
            <div style={{ width: 4, height: 4, borderRadius: "50%", background: ev.color, flexShrink: 0, marginTop: 4 }} />
            <div style={{ minWidth: 0 }}>
              <span style={{ fontSize: "9px", fontWeight: 700, color: ev.color, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                {ev.agent}
              </span>
              <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: i === 0 ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.4)", lineHeight: 1.4, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical" as const }}>
                {ev.msg}
              </p>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

// ── Neural grid background ─────────────────────────────────────────────────

function NeuralGrid() {
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
      {/* Base deep gradient */}
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse at 50% 0%, rgba(130,192,164,0.12) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, rgba(74,140,112,0.06) 0%, transparent 50%), var(--background)" }} />
      {/* Grid dots */}
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)", backgroundSize: "32px 32px" }} />
      {/* Horizon glow */}
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "40%", background: "linear-gradient(to top, rgba(130,192,164,0.04), transparent)" }} />
      {/* Scan line */}
      <motion.div
        animate={{ y: ["-100%", "200%"] }}
        transition={{ repeat: Infinity, duration: 8, ease: "linear", repeatDelay: 4 }}
        style={{ position: "absolute", left: 0, right: 0, height: 1, background: "linear-gradient(to right, transparent, rgba(130,192,164,0.15), transparent)", boxShadow: "0 0 20px rgba(130,192,164,0.1)" }}
      />
    </div>
  );
}

// ── Main hero ──────────────────────────────────────────────────────────────

export default function HeroV3() {
  return (
    <section style={{ position: "relative", minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", overflow: "hidden", padding: "100px 24px 60px" }}>
      <NeuralGrid />

      {/* Floating agents */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        {AGENTS.map((a, i) => (
          <FloatingAgent key={a.id} agent={a} delay={1.2 + i * 0.15} />
        ))}
      </div>

      {/* Main content */}
      <div style={{ position: "relative", zIndex: 2, display: "flex", flexDirection: "column", alignItems: "center", gap: 32, maxWidth: 960, width: "100%" }}>

        {/* Status chip */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          style={{ display: "flex", alignItems: "center", gap: 7, padding: "5px 14px", borderRadius: "var(--radius-pill)", border: "1px solid rgba(130,192,164,0.3)", background: "rgba(130,192,164,0.08)" }}>
          <motion.div animate={{ opacity: [1, 0.3, 1] }} transition={{ repeat: Infinity, duration: 1.2 }}
            style={{ width: 5, height: 5, borderRadius: "50%", background: "#82c0a4", boxShadow: "0 0 8px #82c0a4" }} />
          <span style={{ fontSize: "10px", fontWeight: 800, color: "#82c0a4", letterSpacing: "0.1em" }}>AUTONOMOUS AI OPERATING SYSTEM · ONLINE</span>
        </motion.div>

        {/* Headline */}
        <div style={{ textAlign: "center" }}>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.7 }}
            style={{
              margin:        0,
              fontSize:      "clamp(52px, 9vw, 112px)",
              fontWeight:    900,
              lineHeight:    1.0,
              letterSpacing: "-0.04em",
              background:    "linear-gradient(135deg, #ffffff 0%, #dceee4 40%, rgba(20,184,166,0.9) 70%, #82c0a4 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            CortexPrime
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.55, duration: 0.6 }}
            style={{ margin: "16px 0 0", fontSize: "clamp(16px, 2.5vw, 22px)", color: "rgba(255,255,255,0.5)", fontWeight: 400, letterSpacing: "-0.01em" }}
          >
            Autonomous AI Operating System
          </motion.p>
        </div>

        {/* Orb + Feed row */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.7, duration: 0.8 }}
          style={{ display: "flex", alignItems: "center", gap: 48, flexWrap: "wrap", justifyContent: "center" }}
        >
          <AIOrb />
          <CognitionFeed />
        </motion.div>

        {/* Subtext */}
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.0 }}
          style={{ margin: 0, textAlign: "center", fontSize: "var(--font-size-md)", color: "rgba(255,255,255,0.38)", maxWidth: 520, lineHeight: 1.7 }}
        >
          Five specialized AI agents. Real-time cognition. Persistent memory. Voice. Computer-use. Governance. Running as one unified autonomous system.
        </motion.p>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.1 }}
          style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}
        >
          <Link href="/executive">
            <motion.button
              whileHover={{ scale: 1.04, boxShadow: "0 0 40px rgba(130,192,164,0.5)" }}
              whileTap={{ scale: 0.97 }}
              style={{ padding: "14px 32px", borderRadius: "var(--radius-pill)", background: "linear-gradient(135deg, #82c0a4 0%, #4a8c70 100%)", color: "#fff", fontSize: "var(--font-size-md)", fontWeight: 800, border: "none", cursor: "pointer", boxShadow: "0 0 24px rgba(130,192,164,0.35)", letterSpacing: "-0.01em" }}
            >
              Launch Executive Center →
            </motion.button>
          </Link>
          <Link href="/demo">
            <motion.button
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.97 }}
              style={{ padding: "14px 32px", borderRadius: "var(--radius-pill)", background: "transparent", color: "rgba(255,255,255,0.75)", fontSize: "var(--font-size-md)", fontWeight: 700, border: "1px solid rgba(255,255,255,0.15)", cursor: "pointer", letterSpacing: "-0.01em" }}
            >
              ▶ Start Demo
            </motion.button>
          </Link>
        </motion.div>

        {/* Metrics row */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.3 }}
          style={{ display: "flex", gap: 32, flexWrap: "wrap", justifyContent: "center", paddingTop: 8 }}
        >
          {[
            { val: "5",  label: "Specialized Agents" },
            { val: "6",  label: "Memory Stores" },
            { val: "21", label: "Platform Pages" },
            { val: "∞",  label: "Autonomous Missions" },
          ].map((m) => (
            <div key={m.label} style={{ textAlign: "center" }}>
              <p style={{ margin: 0, fontSize: "var(--font-size-2xl)", fontWeight: 900, color: "#fff", letterSpacing: "-0.03em" }}>{m.val}</p>
              <p style={{ margin: 0, fontSize: "9px", color: "rgba(255,255,255,0.3)", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600 }}>{m.label}</p>
            </div>
          ))}
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.8 }}
        style={{ position: "absolute", bottom: 28, left: "50%", transform: "translateX(-50%)", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}
      >
        <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.25)", letterSpacing: "0.1em", textTransform: "uppercase" }}>Scroll</span>
        <motion.div animate={{ y: [0, 6, 0] }} transition={{ repeat: Infinity, duration: 1.5 }}
          style={{ width: 1, height: 24, background: "linear-gradient(to bottom, rgba(130,192,164,0.6), transparent)" }} />
      </motion.div>
    </section>
  );
}
