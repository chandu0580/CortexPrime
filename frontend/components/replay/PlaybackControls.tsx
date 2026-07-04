"use client";

import { useCallback, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { useReplayStore, PlaybackSpeed } from "@/store/replayStore";

// ── Icons (inline SVG to avoid dependency) ───────────────────────────────

function IconPlay({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M4 2.5l10 5.5-10 5.5V2.5z" fill="currentColor" />
    </svg>
  );
}

function IconPause({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="3" y="2" width="3.5" height="12" rx="1" fill="currentColor" />
      <rect x="9.5" y="2" width="3.5" height="12" rx="1" fill="currentColor" />
    </svg>
  );
}

function IconPrev({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M13.5 2.5L3.5 8l10 5.5V2.5z" fill="currentColor" />
      <rect x="2" y="2" width="2" height="12" rx="1" fill="currentColor" />
    </svg>
  );
}

function IconNext({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M2.5 2.5l10 5.5-10 5.5V2.5z" fill="currentColor" />
      <rect x="12" y="2" width="2" height="12" rx="1" fill="currentColor" />
    </svg>
  );
}

// ── Playback speed selector ───────────────────────────────────────────────

const SPEEDS: PlaybackSpeed[] = [0.25, 0.5, 1, 2, 4];

// ── Tick interval per speed (ms between advances) ───────────────────────

function tickMs(speed: PlaybackSpeed): number {
  // Base interval 800ms at 1x
  return Math.round(800 / speed);
}

function formatOffset(ms: number | null): string {
  if (ms === null || ms === undefined) return "0:00.00";
  const totalSec = ms / 1000;
  const m = Math.floor(totalSec / 60);
  const s = (totalSec % 60).toFixed(2).padStart(5, "0");
  return `${m}:${s}`;
}

// ── Main component ────────────────────────────────────────────────────────

export function PlaybackControls() {
  const isPlaying      = useReplayStore((s) => s.isPlaying);
  const play           = useReplayStore((s) => s.play);
  const pause          = useReplayStore((s) => s.pause);
  const next           = useReplayStore((s) => s.next);
  const previous       = useReplayStore((s) => s.previous);
  const seekTo         = useReplayStore((s) => s.seekTo);
  const setSpeed       = useReplayStore((s) => s.setPlaybackSpeed);
  const tick           = useReplayStore((s) => s._tick);
  const speed          = useReplayStore((s) => s.playbackSpeed);
  const currentSeq     = useReplayStore((s) => s.currentSequence);
  const totalSequences = useReplayStore((s) => s.totalSequences);
  const events         = useReplayStore((s) => s.events);
  const summary        = useReplayStore((s) => s.summary);

  // Auto-advance timer
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (isPlaying) {
      intervalRef.current = setInterval(tick, tickMs(speed));
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [isPlaying, speed, tick]);

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === "Space") { e.preventDefault(); isPlaying ? pause() : play(); }
      if (e.code === "ArrowRight") { e.preventDefault(); next(); }
      if (e.code === "ArrowLeft")  { e.preventDefault(); previous(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isPlaying, play, pause, next, previous]);

  const currentEvent  = events[currentSeq];
  const currentOffset = currentEvent?.offset_ms ?? 0;
  const totalOffset   = events[events.length - 1]?.offset_ms ?? 0;
  const progress      = totalSequences > 1 ? currentSeq / (totalSequences - 1) : 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "10px 16px",
        borderRadius: "var(--radius-lg)",
        background: "#ffffff",
        border: "1px solid var(--border-default)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Transport buttons */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <button
          onClick={previous}
          disabled={currentSeq === 0}
          title="Previous (←)"
          style={btnStyle(currentSeq === 0)}
        >
          <IconPrev size={14} />
        </button>

        <motion.button
          onClick={isPlaying ? pause : play}
          disabled={totalSequences === 0}
          title={isPlaying ? "Pause (Space)" : "Play (Space)"}
          style={{
            ...btnStyle(totalSequences === 0),
            width: 36,
            height: 36,
            borderRadius: "50%",
            background: totalSequences > 0 ? "var(--accent)" : "var(--border-default)",
            color: "#fff",
            boxShadow: totalSequences > 0 ? "0 2px 8px rgba(130,192,164,0.3)" : "none",
          }}
          whileHover={totalSequences > 0 ? { scale: 1.06 } : {}}
          whileTap={totalSequences > 0 ? { scale: 0.94 } : {}}
        >
          {isPlaying ? <IconPause size={14} /> : <IconPlay size={14} />}
        </motion.button>

        <button
          onClick={next}
          disabled={currentSeq >= totalSequences - 1}
          title="Next (→)"
          style={btnStyle(currentSeq >= totalSequences - 1)}
        >
          <IconNext size={14} />
        </button>
      </div>

      {/* Progress scrubber */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 10 }}>
        <span
          className="label-mono"
          style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", minWidth: 52 }}
        >
          {formatOffset(currentOffset)}
        </span>

        <div
          style={{
            flex: 1,
            height: 5,
            borderRadius: 999,
            background: "var(--border-subtle)",
            cursor: totalSequences > 0 ? "pointer" : "default",
            position: "relative",
          }}
          onClick={(e) => {
            if (!totalSequences) return;
            const rect = (e.currentTarget).getBoundingClientRect();
            const pct  = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            seekTo(Math.round(pct * (totalSequences - 1)));
          }}
        >
          <motion.div
            style={{
              height: "100%",
              borderRadius: 999,
              background: "var(--accent)",
              transformOrigin: "left",
            }}
            animate={{ width: `${progress * 100}%` }}
            transition={{ duration: 0.1 }}
          />
          {/* Thumb */}
          <motion.div
            style={{
              position: "absolute",
              top: "50%",
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: "#ffffff",
              border: "2px solid var(--accent)",
              boxShadow: "0 1px 4px rgba(0,0,0,0.12)",
              transform: "translate(-50%,-50%)",
              pointerEvents: "none",
            }}
            animate={{ left: `${progress * 100}%` }}
            transition={{ duration: 0.1 }}
          />
        </div>

        <span
          className="label-mono"
          style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", minWidth: 52, textAlign: "right" }}
        >
          {formatOffset(totalOffset)}
        </span>
      </div>

      {/* Step counter */}
      <span
        className="label-mono"
        style={{ fontSize: "var(--font-size-xs)", color: "var(--text-secondary)", whiteSpace: "nowrap" }}
      >
        {totalSequences > 0 ? `${currentSeq + 1} / ${totalSequences}` : "— / —"}
      </span>

      {/* Speed selector */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        {SPEEDS.map((s) => (
          <button
            key={s}
            onClick={() => setSpeed(s)}
            style={{
              padding: "3px 7px",
              borderRadius: "var(--radius-sm)",
              border: `1px solid ${speed === s ? "var(--accent)" : "var(--border-default)"}`,
              background: speed === s ? "rgba(130,192,164,0.08)" : "transparent",
              color: speed === s ? "var(--accent)" : "var(--text-muted)",
              fontSize: "var(--font-size-xs)",
              fontWeight: speed === s ? 700 : 500,
              cursor: "pointer",
              lineHeight: 1,
            }}
          >
            {s}×
          </button>
        ))}
      </div>

      {/* Duration badge */}
      {summary?.duration_ms != null && (
        <span
          style={{
            fontSize: "var(--font-size-xs)",
            color: "var(--text-muted)",
            padding: "2px 8px",
            borderRadius: "var(--radius-pill)",
            background: "var(--border-subtle)",
            whiteSpace: "nowrap",
          }}
        >
          {(summary.duration_ms / 1000).toFixed(1)}s total
        </span>
      )}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────

function btnStyle(disabled: boolean): React.CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 32,
    height: 32,
    borderRadius: "var(--radius-md)",
    border: "1px solid var(--border-default)",
    background: "transparent",
    color: disabled ? "var(--text-placeholder)" : "var(--text-secondary)",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.45 : 1,
    transition: "all 0.12s ease",
  };
}
