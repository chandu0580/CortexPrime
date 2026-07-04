"use client";

import { motion } from "framer-motion";
import Link from "next/link";

const LINKS = [
  { label: "Executive Center", href: "/executive", color: "#82c0a4",   icon: "⊞", desc: "Full system command" },
  { label: "Start Demo",       href: "/demo",      color: "#818cf8",   icon: "▶", desc: "No setup required"  },
  { label: "Governance",       href: "/governance-center", color: "#f87171", icon: "⊕", desc: "Safety + compliance" },
  { label: "Memory Explorer",  href: "/memory-explorer",   color: "#4a8c70", icon: "◈", desc: "Knowledge graph"    },
  { label: "Voice Interface",  href: "/voice",     color: "#f59e0b",   icon: "◉", desc: "Natural language I/O" },
  { label: "Mission Replay",   href: "/replay",    color: "#4a8c70",   icon: "◎", desc: "Step-by-step playback" },
];

export default function FinalCTAV3() {
  return (
    <section style={{ padding: "100px 24px 80px", background: "var(--background)", position: "relative", overflow: "hidden" }}>
      {/* Radial bloom */}
      <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: 600, height: 600, borderRadius: "50%", background: "radial-gradient(circle, rgba(130,192,164,0.07) 0%, transparent 65%)", pointerEvents: "none" }} />
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)", backgroundSize: "28px 28px", pointerEvents: "none" }} />

      <div style={{ maxWidth: 900, margin: "0 auto", position: "relative", textAlign: "center" }}>
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "5px 14px", borderRadius: "var(--radius-pill)", border: "1px solid rgba(130,192,164,0.3)", background: "rgba(130,192,164,0.08)", marginBottom: 24 }}
        >
          <motion.div animate={{ opacity: [1, 0.3, 1] }} transition={{ repeat: Infinity, duration: 1.2 }}
            style={{ width: 5, height: 5, borderRadius: "50%", background: "#82c0a4", boxShadow: "0 0 8px #82c0a4" }} />
          <span style={{ fontSize: "10px", fontWeight: 800, color: "#82c0a4", letterSpacing: "0.1em" }}>
            READY TO DEPLOY
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          style={{ margin: "0 0 16px", fontSize: "clamp(36px, 6vw, 72px)", fontWeight: 900, color: "#fff", letterSpacing: "-0.04em", lineHeight: 1.05 }}
        >
          The Future of{" "}
          <span style={{
            background: "linear-gradient(135deg, #82c0a4, #96cead 40%, #4a8c70)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}>
            Autonomous AI
          </span>
          {" "}is Here
        </motion.h2>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
          style={{ margin: "0 0 48px", fontSize: "var(--font-size-md)", color: "rgba(255,255,255,0.4)", lineHeight: 1.7, maxWidth: 560, marginLeft: "auto", marginRight: "auto" }}
        >
          Five agents. Four memory stores. Voice. Computer-use. Real-time governance. This is CortexPrime — an AI operating system that thinks, acts, and learns continuously.
        </motion.p>

        {/* Primary CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
          style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap", marginBottom: 48 }}
        >
          <Link href="/executive">
            <motion.button
              whileHover={{ scale: 1.05, boxShadow: "0 0 50px rgba(130,192,164,0.55)" }}
              whileTap={{ scale: 0.97 }}
              style={{ padding: "16px 40px", borderRadius: "var(--radius-pill)", background: "linear-gradient(135deg, #82c0a4 0%, #4a8c70 100%)", color: "#fff", fontSize: "var(--font-size-md)", fontWeight: 800, border: "none", cursor: "pointer", boxShadow: "0 0 28px rgba(130,192,164,0.4)", letterSpacing: "-0.01em" }}
            >
              Launch CortexPrime →
            </motion.button>
          </Link>
          <Link href="/demo">
            <motion.button
              whileHover={{ scale: 1.04, borderColor: "rgba(255,255,255,0.3)" }}
              whileTap={{ scale: 0.97 }}
              style={{ padding: "16px 40px", borderRadius: "var(--radius-pill)", background: "transparent", color: "rgba(255,255,255,0.7)", fontSize: "var(--font-size-md)", fontWeight: 700, border: "1px solid rgba(255,255,255,0.15)", cursor: "pointer", letterSpacing: "-0.01em" }}
            >
              ▶ Try Demo — No Setup
            </motion.button>
          </Link>
        </motion.div>

        {/* Navigation grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10, maxWidth: 720, margin: "0 auto 60px" }}>
          {LINKS.map((l, i) => (
            <motion.a
              key={l.href}
              href={l.href}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 + i * 0.06 }}
              whileHover={{ y: -2, scale: 1.02 }}
              style={{
                display:        "flex",
                flexDirection:  "column",
                gap:            5,
                padding:        "14px",
                borderRadius:   "var(--radius-lg)",
                border:         `1px solid ${l.color}20`,
                background:     `${l.color}07`,
                textDecoration: "none",
                transition:     "border-color 0.15s",
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = `${l.color}45`; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = `${l.color}20`; }}
            >
              <span style={{ fontSize: 16, color: l.color }}>{l.icon}</span>
              <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: "#fff" }}>{l.label}</span>
              <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.35)" }}>{l.desc}</span>
            </motion.a>
          ))}
        </div>

        {/* Footer line */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: 32, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 16, height: 16, borderRadius: "50%", background: "radial-gradient(circle at 35% 35%, #96cead, #82c0a4)" }} />
            <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: "rgba(255,255,255,0.5)" }}>CortexPrime</span>
            <span style={{ fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.2)" }}>·</span>
            <span style={{ fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.3)" }}>Autonomous AI Operating System</span>
          </div>
          <div style={{ display: "flex", gap: 20 }}>
            {["Executive", "Demo", "Governance", "Memory", "Voice"].map((l) => (
              <a key={l} href={`/${l.toLowerCase()}`} style={{ fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.25)", textDecoration: "none", transition: "color 0.15s" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "rgba(255,255,255,0.6)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "rgba(255,255,255,0.25)"; }}
              >
                {l}
              </a>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
