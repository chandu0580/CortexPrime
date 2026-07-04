"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useExecutiveStore } from "@/store/executiveStore";
import { useRuntimeStore } from "@/store/runtimeStore";
import { useMissionStore } from "@/store/missionStore";

// ── Stage config ──────────────────────────────────────────────────────────

const STAGE_COLOR: Record<string, string> = {
  idle:        "#737373",
  initialized: "#38bdf8",
  planning:    "#818cf8",
  researching: "#34d399",
  executing:   "#82c0a4",
  validating:  "#fbbf24",
  reflecting:  "#a78bfa",
  completed:   "#34d399",
  running:     "#82c0a4",
  active:      "#82c0a4",
  failed:      "#f87171",
};

function stageColor(s: string) { return STAGE_COLOR[s?.toLowerCase()] ?? "#737373"; }

function formatElapsed(secs: number): string {
  if (secs < 60)   return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs/60)}m ${secs%60}s`;
  return `${Math.floor(secs/3600)}h ${Math.floor((secs%3600)/60)}m`;
}

// ── Progress arc ──────────────────────────────────────────────────────────

function ProgressArc({ pct, color, size = 80 }: { pct: number; color: string; size?: number }) {
  const r   = size / 2 - 6;
  const c   = size / 2;
  const circ = 2 * Math.PI * r;
  const fill = (pct / 100) * circ;

  return (
    <svg width={size} height={size} style={{ flexShrink: 0 }}>
      <circle cx={c} cy={c} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={5} />
      <motion.circle
        cx={c} cy={c} r={r}
        fill="none"
        stroke={color}
        strokeWidth={5}
        strokeLinecap="round"
        strokeDasharray={circ}
        initial={{ strokeDashoffset: circ }}
        animate={{ strokeDashoffset: circ - fill }}
        transition={{ duration: 1.2, ease: "easeOut" }}
        transform={`rotate(-90 ${c} ${c})`}
        style={{ filter: `drop-shadow(0 0 6px ${color})` }}
      />
      <text x={c} y={c + 1} textAnchor="middle" dominantBaseline="middle"
        style={{ fontSize: 13, fontWeight: 800, fill: color, fontFamily: "monospace" }}>
        {Math.round(pct)}%
      </text>
    </svg>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────

export function MissionControl() {
  const snapshot    = useExecutiveStore((s) => s.snapshot);
  const rStore      = useRuntimeStore();

  // Live mission from store (WebSocket driven)
  const liveStage   = useMissionStore?.((s: {stage: string}) => s.stage) ?? "idle";
  const liveGoal    = useMissionStore?.((s: {goal: string | null}) => s.goal) ?? null;
  const liveProgress = useMissionStore?.((s: {progress: number}) => s.progress) ?? 0;

  const mission     = snapshot?.current_mission;
  const stage       = liveStage !== "idle" ? liveStage : (mission?.stage ?? "idle");
  const goal        = liveGoal ?? mission?.goal ?? "No active mission";
  const progress    = liveProgress > 0 ? liveProgress : (mission?.progress ?? 0);
  const color       = stageColor(stage);

  const hasMission  = stage !== "idle" && stage !== "completed";

  // Agent activity overlay
  const agentActivity = rStore.agentActivity;
  const activeAgentId = Object.entries(agentActivity).find(([, s]) => s === "active" || s === "processing")?.[0];

  const AGENT_COLORS: Record<string, string> = {
    orchestrator: "#82c0a4",
    planner:      "#4a8c70",
    research:     "#4a8c70",
    critic:       "#f9a825",
    optimizer:    "#96cead",
    memory:       "#737373",
  };

  const STAGE_PHASES = [
    { id: "initialized", label: "Init"     },
    { id: "planning",    label: "Plan"     },
    { id: "researching", label: "Research" },
    { id: "executing",   label: "Execute"  },
    { id: "validating",  label: "Validate" },
    { id: "reflecting",  label: "Reflect"  },
    { id: "completed",   label: "Done"     },
  ];

  const currentPhaseIdx = STAGE_PHASES.findIndex((p) =>
    p.id === stage || (stage === "running" && p.id === "executing")
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, height: "100%" }}>

      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <ProgressArc pct={progress} color={color} size={72} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
            <motion.span
              key={stage}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{
                fontSize: "10px", fontWeight: 700, letterSpacing: "0.06em",
                color: color, background: `${color}15`, padding: "2px 8px",
                borderRadius: "var(--radius-pill)", border: `1px solid ${color}30`,
              }}
            >
              {stage.toUpperCase()}
            </motion.span>

            {hasMission && (
              <motion.div
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ repeat: Infinity, duration: 1.4 }}
                style={{ width: 6, height: 6, borderRadius: "50%", background: color, boxShadow: `0 0 8px ${color}` }}
              />
            )}

            {mission?.elapsed_secs != null && mission.elapsed_secs > 0 && (
              <span className="label-mono" style={{ fontSize: "10px", color: "var(--text-muted)", marginLeft: "auto" }}>
                {formatElapsed(mission.elapsed_secs)}
              </span>
            )}
          </div>

          <p style={{
            margin: 0, fontSize: "var(--font-size-sm)", fontWeight: 600,
            color: hasMission ? "var(--text-primary)" : "var(--text-muted)",
            lineHeight: 1.4, overflow: "hidden",
            display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const,
          }}>
            {goal}
          </p>
        </div>
      </div>

      {/* Active agent */}
      <AnimatePresence>
        {activeAgentId && (
          <motion.div
            key={activeAgentId}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            style={{
              display:      "flex",
              alignItems:   "center",
              gap:          8,
              padding:      "7px 10px",
              borderRadius: "var(--radius-md)",
              border:       `1px solid ${AGENT_COLORS[activeAgentId] ?? "#737373"}33`,
              background:   `${AGENT_COLORS[activeAgentId] ?? "#737373"}08`,
            }}
          >
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: AGENT_COLORS[activeAgentId] ?? "#737373", boxShadow: `0 0 8px ${AGENT_COLORS[activeAgentId] ?? "#737373"}` }} />
            <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: AGENT_COLORS[activeAgentId] ?? "#737373", textTransform: "capitalize" }}>
              {activeAgentId}
            </span>
            <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)" }}>
              {rStore.agentLastAction[activeAgentId] || "Processing…"}
            </span>
            <motion.span
              animate={{ opacity: [1, 0] }}
              transition={{ repeat: Infinity, duration: 0.6, repeatType: "reverse" }}
              style={{ marginLeft: "auto", fontSize: "var(--font-size-xs)", color: AGENT_COLORS[activeAgentId] ?? "#737373" }}
            >
              ●
            </motion.span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Phase timeline */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
          {STAGE_PHASES.map((phase, i) => {
            const isActive = i === currentPhaseIdx;
            const isPast   = i < currentPhaseIdx;
            const phaseColor = isActive ? color : isPast ? "#34d399" : "var(--border-default)";

            return (
              <div key={phase.id} style={{ display: "flex", alignItems: "center", flex: "1 1 0" }}>
                {/* Dot */}
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
                  <div style={{
                    width:        isActive ? 10 : 7,
                    height:       isActive ? 10 : 7,
                    borderRadius: "50%",
                    background:   phaseColor,
                    boxShadow:    isActive ? `0 0 10px ${color}` : "none",
                    transition:   "all 0.3s",
                    flexShrink:   0,
                  }} />
                  <span style={{ fontSize: "9px", color: isActive ? color : isPast ? "#34d399" : "var(--text-muted)", fontWeight: isActive ? 700 : 500, whiteSpace: "nowrap" }}>
                    {phase.label}
                  </span>
                </div>
                {/* Connector */}
                {i < STAGE_PHASES.length - 1 && (
                  <div style={{ flex: 1, height: 1, background: isPast || isActive ? `linear-gradient(to right, ${phaseColor}, ${STAGE_PHASES[i+1] ? (i+1 <= currentPhaseIdx ? "#34d399" : "var(--border-default)") : "var(--border-default)"})` : "var(--border-subtle)", margin: "0 1px", marginBottom: 15, position: "relative", overflow: "hidden" }}>
                    {isActive && (
                      <motion.div
                        animate={{ x: ["−100%", "200%"] }}
                        transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                        style={{ position: "absolute", top: 0, width: "40%", height: "100%", background: `linear-gradient(to right, transparent, ${color}, transparent)` }}
                      />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Replay shortcut */}
      {mission?.execution_id && (
        <a
          href={`/replay/${mission.execution_id}`}
          style={{
            display:     "flex",
            alignItems:  "center",
            gap:         6,
            fontSize:    "var(--font-size-xs)",
            color:       "var(--text-muted)",
            textDecoration: "none",
            padding:     "5px 8px",
            borderRadius: "var(--radius-sm)",
            border:      "1px solid var(--border-subtle)",
            background:  "transparent",
            marginTop:   "auto",
            transition:  "border-color 0.12s, color 0.12s",
          }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--accent)"; (e.currentTarget as HTMLElement).style.borderColor = "rgba(130,192,164,0.35)"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-muted)"; (e.currentTarget as HTMLElement).style.borderColor = "var(--border-subtle)"; }}
        >
          ▶ Replay this mission
          <span className="label-mono" style={{ fontSize: "10px", opacity: 0.6 }}>{mission.execution_id.slice(0, 12)}…</span>
        </a>
      )}
    </div>
  );
}
