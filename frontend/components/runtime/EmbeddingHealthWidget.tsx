"use client"
import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { runtimeService, type EmbeddingHealth } from "@/services/runtime"
import GlassPanel from "@/components/ui/GlassPanel"
import SectionHeader from "@/components/ui/SectionHeader"
import StatusPill from "@/components/ui/StatusPill"
import { POLL_INTERVAL_MS } from "@/lib/constants"

// ==========================================
// EMBEDDING HEALTH WIDGET
// ==========================================

const STATUS_CONFIG = {
    healthy:  { pill: "success"  as const, dot: "bg-emerald-400", label: "Healthy",      glow: "shadow-[0_0_12px_2px_rgba(52,211,153,0.25)]" },
    degraded: { pill: "warning"  as const, dot: "bg-amber-400",   label: "Degraded",     glow: "shadow-[0_0_12px_2px_rgba(251,191,36,0.25)]"  },
    failed:   { pill: "error"    as const, dot: "bg-red-500",     label: "Failed",        glow: "shadow-[0_0_12px_2px_rgba(239,68,68,0.30)]"   },
    loading:  { pill: "info"     as const, dot: "bg-sky-400",     label: "Checking…",    glow: "" },
} as const

type StatusKey = keyof typeof STATUS_CONFIG

function MetricRow({ label, value }: { label: string; value: string | number }) {
    return (
        <div className="flex items-center justify-between py-0.5 text-xs">
            <span className="text-[var(--text-muted)] font-medium">{label}</span>
            <span className="font-mono text-[var(--text-secondary)] tabular-nums">{value}</span>
        </div>
    )
}

function PulsingDot({ color, glow }: { color: string; glow: string }) {
    return (
        <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${color} ${glow}`}>
            <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${color}`} />
        </span>
    )
}

export default function EmbeddingHealthWidget() {
    const [data, setData]       = useState<EmbeddingHealth | null>(null)
    const [error, setError]     = useState<string | null>(null)
    const [lastPoll, setLastPoll] = useState<Date | null>(null)

    useEffect(() => {
        const poll = async () => {
            try {
                const result = await runtimeService.getEmbeddingHealth()
                setData(result)
                setError(null)
            } catch (err) {
                setError("Health endpoint unreachable")
            }
            setLastPoll(new Date())
        }

        poll()
        const t = setInterval(poll, POLL_INTERVAL_MS)
        return () => clearInterval(t)
    }, [])

    const statusKey: StatusKey = !data
        ? "loading"
        : (data.embedding_status as StatusKey) ?? "loading"

    const cfg = STATUS_CONFIG[statusKey] ?? STATUS_CONFIG.loading

    const cacheTotal  = (data?.cache_hits ?? 0) + (data?.cache_misses ?? 0)
    const hitRate     = cacheTotal > 0
        ? `${((data!.cache_hits / cacheTotal) * 100).toFixed(0)}%`
        : "—"

    return (
        <GlassPanel>
            {/* ── Header ─────────────────────────────────────────── */}
            <div className="flex items-center justify-between mb-3">
                <SectionHeader
                    title="Embedding Health"
                    subtitle={data?.active_model ?? "loading…"}
                />
                <div className="flex items-center gap-2">
                    <PulsingDot color={cfg.dot} glow={cfg.glow} />
                    <StatusPill label={cfg.label} variant={cfg.pill} />
                </div>
            </div>

            {/* ── Warning banner ──────────────────────────────────── */}
            <AnimatePresence>
                {data?.warning && (
                    <motion.div
                        key="warning"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mb-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300 leading-relaxed"
                    >
                        ⚠ {data.warning}
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Error state ─────────────────────────────────────── */}
            {error && (
                <p className="mb-3 text-xs text-red-400">{error}</p>
            )}

            {/* ── Dimension row ───────────────────────────────────── */}
            {data && (
                <div className="mb-3 flex items-center gap-2 rounded-lg bg-white/5 px-3 py-2">
                    <span className="text-xs text-[var(--text-muted)]">Dimensions</span>
                    <span className="ml-auto font-mono text-sm font-semibold text-[var(--text-primary)]">
                        {data.actual_dimension}
                    </span>
                    {data.actual_dimension !== data.expected_dimension && (
                        <span className="text-xs text-red-400 font-medium">
                            (expected {data.expected_dimension})
                        </span>
                    )}
                    {data.actual_dimension === data.expected_dimension && (
                        <span className="text-xs text-emerald-400">✓</span>
                    )}
                </div>
            )}

            {/* ── Metrics grid ────────────────────────────────────── */}
            {data && (
                <div className="divide-y divide-white/5 rounded-lg bg-white/5 px-3 py-1">
                    <MetricRow label="Cache hit rate"   value={hitRate} />
                    <MetricRow label="Cache hits"       value={data.cache_hits} />
                    <MetricRow label="Cache misses"     value={data.cache_misses} />
                    <MetricRow label="OpenAI calls"     value={data.openai_calls} />
                    <MetricRow label="Local calls"      value={data.local_calls} />
                    <MetricRow label="Failures"         value={data.failures} />
                    <MetricRow label="Dim mismatches"   value={data.mismatch_count} />
                </div>
            )}

            {/* ── Degraded mode badge ─────────────────────────────── */}
            {data?.degraded_mode && (
                <p className="mt-2 text-[11px] text-amber-400/80 text-center">
                    Local fallback active — pgvector rows stored without embeddings
                </p>
            )}

            {/* ── Last updated ────────────────────────────────────── */}
            {lastPoll && (
                <p className="mt-2 text-[10px] text-[var(--text-muted)] text-right">
                    Updated {lastPoll.toLocaleTimeString()}
                </p>
            )}
        </GlassPanel>
    )
}
