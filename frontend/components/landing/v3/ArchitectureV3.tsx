"use client";

import { useState } from "react";
import { motion } from "framer-motion";

// ── Architecture nodes ─────────────────────────────────────────────────────

interface ArchNode {
  id:     string;
  label:  string;
  icon:   string;
  color:  string;
  cx:     number;
  cy:     number;
  detail: string;
  href:   string;
}

const NODES: ArchNode[] = [
  { id: "llm",        label: "LLM Router",     icon: "⊞", color: "#82c0a4", cx: 400, cy: 250, detail: "Routes tasks to GPT-4o, Claude 3.5, Gemini 1.5, or local Ollama. Dynamic latency-cost optimization.", href: "/settings" },
  { id: "orchestrator", label: "Orchestrator", icon: "◎", color: "#4a8c70", cx: 400, cy: 140, detail: "Central coordination: dispatches agents, manages mission lifecycle, monitors progress.", href: "/command" },
  { id: "voice",      label: "Voice Runtime",  icon: "◉", color: "#f59e0b", cx: 175, cy: 185, detail: "Wake-word detection, Whisper STT, edge-TTS synthesis. Full natural-language I/O.", href: "/voice" },
  { id: "memory",     label: "Memory System",  icon: "◈", color: "#4a8c70", cx: 175, cy: 315, detail: "Episodic, semantic, short-term, and vector (ChromaDB) memory with reflection loops.", href: "/memory-explorer" },
  { id: "governance", label: "Governance",     icon: "⊕", color: "#f87171", cx: 625, cy: 185, detail: "Real-time guardrails, human approval queue, compliance scoring, audit trail.", href: "/governance-center" },
  { id: "replay",     label: "Replay Engine",  icon: "▶", color: "#818cf8", cx: 625, cy: 315, detail: "Step-by-step mission playback with full agent state reconstruction.", href: "/replay" },
  { id: "computer",   label: "Computer Agent", icon: "⊟", color: "#a78bfa", cx: 270, cy: 400, detail: "Desktop automation via pyautogui. Screenshot capture, OCR, GUI interaction.", href: "/operator" },
  { id: "browser",    label: "Browser Agent",  icon: "⊗", color: "#38bdf8", cx: 530, cy: 400, detail: "Full Playwright browser control. Web research, form filling, content extraction.", href: "/operator" },
];

const EDGES = [
  ["orchestrator", "llm"],
  ["orchestrator", "voice"],
  ["orchestrator", "governance"],
  ["llm", "memory"],
  ["llm", "computer"],
  ["llm", "browser"],
  ["memory", "computer"],
  ["governance", "replay"],
  ["browser", "governance"],
];

// ── Section wrap helpers ───────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
      <div style={{ width: 3, height: 14, borderRadius: 2, background: "#82c0a4" }} />
      <span style={{ fontSize: "10px", fontWeight: 800, color: "#82c0a4", letterSpacing: "0.12em", textTransform: "uppercase" }}>{children}</span>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export default function ArchitectureV3() {
  const [hovered, setHovered] = useState<string | null>(null);
  const hoveredNode = NODES.find((n) => n.id === hovered);

  const SCALE = 0.65;

  return (
    <section id="architecture" style={{ padding: "100px 24px", position: "relative", background: "var(--background)" }}>
      {/* Grid */}
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)", backgroundSize: "28px 28px", pointerEvents: "none" }} />

      <div style={{ maxWidth: 960, margin: "0 auto", position: "relative" }}>
        <SectionLabel>Live Architecture</SectionLabel>
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ margin: "0 0 8px", fontSize: "clamp(28px,4vw,44px)", fontWeight: 900, color: "#fff", letterSpacing: "-0.03em" }}
        >
          Every Subsystem, Interconnected
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          style={{ margin: "0 0 48px", fontSize: "var(--font-size-md)", color: "rgba(255,255,255,0.4)" }}
        >
          Hover any node to explore the subsystem. Click to navigate.
        </motion.p>

        <div style={{ display: "flex", gap: 32, alignItems: "flex-start", flexWrap: "wrap" }}>
          {/* SVG diagram */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            style={{
              flex:          "1 1 460px",
              borderRadius:  "var(--radius-xl)",
              border:        "1px solid rgba(255,255,255,0.06)",
              background:    "rgba(255,255,255,0.02)",
              overflow:      "hidden",
            }}
          >
            <svg
              viewBox="0 0 800 540"
              width="100%"
              style={{ display: "block" }}
            >
              {/* Edges */}
              {EDGES.map(([a, b], i) => {
                const na = NODES.find((n) => n.id === a)!;
                const nb = NODES.find((n) => n.id === b)!;
                const isActive = hovered === a || hovered === b;
                return (
                  <g key={i}>
                    <line
                      x1={na.cx} y1={na.cy} x2={nb.cx} y2={nb.cy}
                      stroke={isActive ? na.color : "rgba(255,255,255,0.07)"}
                      strokeWidth={isActive ? 1.5 : 1}
                      strokeDasharray={isActive ? "none" : "4 4"}
                      style={{ transition: "stroke 0.2s, stroke-width 0.2s" }}
                    />
                    {isActive && (
                      <circle r={3} fill={na.color} opacity={0.8}>
                        <animateMotion
                          dur="1.4s"
                          repeatCount="indefinite"
                          path={`M ${na.cx},${na.cy} L ${nb.cx},${nb.cy}`}
                        />
                      </circle>
                    )}
                  </g>
                );
              })}

              {/* Nodes */}
              {NODES.map((node) => {
                const isHov = hovered === node.id;
                return (
                  <g
                    key={node.id}
                    style={{ cursor: "pointer" }}
                    onMouseEnter={() => setHovered(node.id)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => { window.location.href = node.href; }}
                  >
                    {/* Glow */}
                    <circle cx={node.cx} cy={node.cy} r={isHov ? 28 : 22} fill={`${node.color}${isHov ? "22" : "10"}`} style={{ transition: "r 0.2s, fill 0.2s" }} />
                    {/* Ring */}
                    <circle cx={node.cx} cy={node.cy} r={22} fill="none" stroke={isHov ? node.color : `${node.color}50`} strokeWidth={isHov ? 1.5 : 1} style={{ transition: "stroke 0.2s" }} />
                    {/* Inner */}
                    <circle cx={node.cx} cy={node.cy} r={15} fill={`${node.color}18`} />
                    {/* Icon */}
                    <text x={node.cx} y={node.cy + 5} textAnchor="middle" dominantBaseline="middle" style={{ fontSize: 14, fill: node.color, fontWeight: 700 }}>
                      {node.icon}
                    </text>
                    {/* Label */}
                    <text x={node.cx} y={node.cy + 32} textAnchor="middle" style={{ fontSize: 9, fill: isHov ? "#fff" : "rgba(255,255,255,0.5)", fontWeight: 600, letterSpacing: "0.04em" }}>
                      {node.label}
                    </text>
                    {/* Active pulse */}
                    {isHov && (
                      <circle cx={node.cx} cy={node.cy} r={26} fill="none" stroke={node.color} strokeWidth={1} opacity={0.4}>
                        <animate attributeName="r" values="22;36;22" dur="1.5s" repeatCount="indefinite" />
                        <animate attributeName="opacity" values="0.4;0;0.4" dur="1.5s" repeatCount="indefinite" />
                      </circle>
                    )}
                  </g>
                );
              })}
            </svg>
          </motion.div>

          {/* Detail panel */}
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            style={{ flex: "0 0 240px", minHeight: 300, display: "flex", flexDirection: "column", gap: 12 }}
          >
            {hoveredNode ? (
              <motion.div
                key={hoveredNode.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  padding:      "20px",
                  borderRadius: "var(--radius-xl)",
                  border:       `1px solid ${hoveredNode.color}35`,
                  background:   `${hoveredNode.color}0a`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                  <span style={{ fontSize: 22, color: hoveredNode.color }}>{hoveredNode.icon}</span>
                  <span style={{ fontSize: "var(--font-size-md)", fontWeight: 800, color: "#fff" }}>{hoveredNode.label}</span>
                </div>
                <p style={{ margin: "0 0 16px", fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.55)", lineHeight: 1.6 }}>
                  {hoveredNode.detail}
                </p>
                <a href={hoveredNode.href} style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "6px 12px", borderRadius: "var(--radius-pill)", border: `1px solid ${hoveredNode.color}40`, color: hoveredNode.color, fontSize: "var(--font-size-xs)", fontWeight: 700, textDecoration: "none" }}>
                  Open {hoveredNode.label} →
                </a>
              </motion.div>
            ) : (
              <div style={{ padding: "20px", borderRadius: "var(--radius-xl)", border: "1px solid rgba(255,255,255,0.06)", background: "rgba(255,255,255,0.02)", flex: 1 }}>
                <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.25)", lineHeight: 1.7 }}>
                  Hover any node in the diagram to explore its capabilities, data flows, and integrations.
                </p>
                <div style={{ marginTop: 20, display: "flex", flexDirection: "column", gap: 6 }}>
                  {NODES.map((n) => (
                    <div key={n.id} style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <div style={{ width: 4, height: 4, borderRadius: "50%", background: n.color }} />
                      <span style={{ fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.35)", fontWeight: 500 }}>{n.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
