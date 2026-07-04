"use client";

import { motion } from "framer-motion";

// ── Memory graph nodes ─────────────────────────────────────────────────────

const GRAPH_NODES = [
  { id: "a", label: "AI Impact",    cx: 200, cy: 130, color: "#82c0a4", r: 18, type: "concept" },
  { id: "b", label: "DevOps P1",   cx: 360, cy: 80,  color: "#f87171", r: 14, type: "episode" },
  { id: "c", label: "APT-29 IOCs", cx: 480, cy: 160, color: "#f59e0b", r: 16, type: "semantic" },
  { id: "d", label: "Board Deck",  cx: 300, cy: 220, color: "#96cead", r: 14, type: "episode" },
  { id: "e", label: "McKinsey 26", cx: 120, cy: 230, color: "#4a8c70", r: 12, type: "source" },
  { id: "f", label: "Reflection",  cx: 420, cy: 270, color: "#818cf8", r: 13, type: "reflect" },
  { id: "g", label: "Market TAM",  cx: 240, cy: 310, color: "#38bdf8", r: 12, type: "semantic" },
  { id: "h", label: "Voice Query", cx: 540, cy: 240, color: "#f59e0b", r: 11, type: "episode" },
];

const GRAPH_EDGES = [
  ["a","b"], ["a","e"], ["a","d"], ["b","f"], ["c","f"], ["d","g"], ["d","a"], ["e","a"], ["f","h"], ["g","a"],
];

// ── Timeline items ─────────────────────────────────────────────────────────

const TIMELINE = [
  { time: "2m ago",  agent: "memory",  color: "#737373", label: "memory_stored",      detail: "23 research insights consolidated" },
  { time: "8m ago",  agent: "research", color: "#4a8c70", label: "memory_retrieved",  detail: "8 historical incidents recalled" },
  { time: "22m ago", agent: "planner",  color: "#4a8c70", label: "semantic_search",   detail: "Vector search: 14 relevant memories" },
  { time: "1h ago",  agent: "memory",   color: "#737373", label: "reflection",        detail: "Daily reflection loop completed" },
  { time: "3h ago",  agent: "critic",   color: "#f9a825", label: "memory_stored",     detail: "APT-29 threat intel indexed" },
];

// ── Memory type legend ─────────────────────────────────────────────────────

const MEM_TYPES = [
  { color: "#f87171", label: "Episodic" },
  { color: "#82c0a4", label: "Semantic" },
  { color: "#f59e0b", label: "Short-term" },
  { color: "#818cf8", label: "Reflection" },
  { color: "#4a8c70", label: "Source" },
];

export default function MemoryPreviewV3() {
  return (
    <section id="memory" style={{ padding: "100px 24px", background: "var(--background)", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.025) 1px, transparent 1px)", backgroundSize: "28px 28px", pointerEvents: "none" }} />

      <div style={{ maxWidth: 1000, margin: "0 auto", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <div style={{ width: 3, height: 14, borderRadius: 2, background: "#4a8c70" }} />
          <span style={{ fontSize: "10px", fontWeight: 800, color: "#4a8c70", letterSpacing: "0.12em", textTransform: "uppercase" }}>Memory System</span>
        </div>
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ margin: "0 0 8px", fontSize: "clamp(28px,4vw,44px)", fontWeight: 900, color: "#fff", letterSpacing: "-0.03em" }}
        >
          Intelligence That Persists
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          style={{ margin: "0 0 44px", fontSize: "var(--font-size-md)", color: "rgba(255,255,255,0.38)" }}
        >
          Four memory stores. Every mission, every insight, every reflection — permanently retained.
        </motion.p>

        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          {/* Graph */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            style={{ flex: "1 1 380px", borderRadius: "var(--radius-xl)", border: "1px solid rgba(74,140,112,0.15)", background: "rgba(74,140,112,0.04)", overflow: "hidden" }}
          >
            <div style={{ padding: "14px 16px", borderBottom: "1px solid rgba(255,255,255,0.05)", display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: "rgba(255,255,255,0.5)", letterSpacing: "0.07em", textTransform: "uppercase" }}>Knowledge Graph</span>
              <span style={{ fontSize: "9px", color: "#4a8c70", marginLeft: "auto" }}>1,247 nodes</span>
            </div>
            <svg viewBox="0 0 660 360" width="100%" style={{ display: "block" }}>
              {GRAPH_EDGES.map(([a, b], i) => {
                const na = GRAPH_NODES.find((n) => n.id === a)!;
                const nb = GRAPH_NODES.find((n) => n.id === b)!;
                return (
                  <line key={i} x1={na.cx} y1={na.cy} x2={nb.cx} y2={nb.cy}
                    stroke="rgba(255,255,255,0.07)" strokeWidth={1} />
                );
              })}
              {GRAPH_NODES.map((n, i) => (
                <motion.g
                  key={n.id}
                  initial={{ opacity: 0, scale: 0 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.08, duration: 0.4 }}
                >
                  <circle cx={n.cx} cy={n.cy} r={n.r + 6} fill={`${n.color}12`} />
                  <circle cx={n.cx} cy={n.cy} r={n.r} fill={`${n.color}22`} stroke={`${n.color}60`} strokeWidth={1} />
                  <text x={n.cx} y={n.cy + 3} textAnchor="middle" style={{ fontSize: n.r > 15 ? 8 : 7, fill: n.color, fontWeight: 700 }}>
                    {n.label.split(" ")[0]}
                  </text>
                </motion.g>
              ))}
            </svg>
            {/* Legend */}
            <div style={{ padding: "8px 16px 14px", display: "flex", gap: 10, flexWrap: "wrap" }}>
              {MEM_TYPES.map((t) => (
                <div key={t.label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: t.color }} />
                  <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.3)", fontWeight: 600 }}>{t.label}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Timeline */}
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            style={{ flex: "0 0 280px", display: "flex", flexDirection: "column", gap: 14 }}
          >
            {/* Memory stats */}
            <div style={{ padding: "16px", borderRadius: "var(--radius-xl)", border: "1px solid rgba(255,255,255,0.07)", background: "rgba(255,255,255,0.02)" }}>
              <p style={{ margin: "0 0 12px", fontSize: "var(--font-size-xs)", fontWeight: 700, color: "rgba(255,255,255,0.5)", letterSpacing: "0.07em", textTransform: "uppercase" }}>Memory Stores</p>
              {[
                { label: "Episodic",  count: 483,  color: "#f87171" },
                { label: "Semantic",  count: 614,  color: "#82c0a4" },
                { label: "Short-term", count: 89,  color: "#f59e0b" },
                { label: "Reflections", count: 61, color: "#818cf8" },
              ].map((s) => (
                <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: s.color, flexShrink: 0 }} />
                  <span style={{ fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.45)", flex: 1 }}>{s.label}</span>
                  <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: s.color, fontFamily: "monospace" }}>{s.count.toLocaleString()}</span>
                </div>
              ))}
            </div>

            {/* Timeline */}
            <div style={{ padding: "16px", borderRadius: "var(--radius-xl)", border: "1px solid rgba(255,255,255,0.07)", background: "rgba(255,255,255,0.02)", flex: 1 }}>
              <p style={{ margin: "0 0 12px", fontSize: "var(--font-size-xs)", fontWeight: 700, color: "rgba(255,255,255,0.5)", letterSpacing: "0.07em", textTransform: "uppercase" }}>Recall Timeline</p>
              {TIMELINE.map((item, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  style={{ display: "flex", gap: 8, marginBottom: 10, paddingBottom: 10, borderBottom: i < TIMELINE.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none" }}
                >
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, flexShrink: 0 }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: item.color }} />
                    {i < TIMELINE.length - 1 && <div style={{ width: 1, flex: 1, background: "rgba(255,255,255,0.05)" }} />}
                  </div>
                  <div>
                    <div style={{ display: "flex", gap: 5, marginBottom: 2 }}>
                      <span style={{ fontSize: "9px", fontWeight: 700, color: item.color, textTransform: "uppercase" }}>{item.agent}</span>
                      <span style={{ fontSize: "9px", color: "rgba(255,255,255,0.2)" }}>{item.time}</span>
                    </div>
                    <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "rgba(255,255,255,0.45)", lineHeight: 1.3 }}>{item.detail}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          style={{ textAlign: "center", marginTop: 32 }}
        >
          <a href="/memory-explorer" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 28px", borderRadius: "var(--radius-pill)", background: "rgba(74,140,112,0.12)", border: "1.5px solid rgba(74,140,112,0.3)", color: "#4a8c70", fontSize: "var(--font-size-sm)", fontWeight: 800, textDecoration: "none" }}>
            Explore Memory System →
          </a>
        </motion.div>
      </div>
    </section>
  );
}
