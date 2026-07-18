import type { StageMetrics } from "@/types/enterprise"

export function StageMetricsPanel({
  metrics,
}: {
  metrics: [string, StageMetrics][]
}) {
  if (!metrics.length) return null

  return (
    <div className="surface-panel p-5">
      <h3 className="type-label-sm text-[var(--text-muted)] mb-3">Stage Metrics</h3>
      <div className="space-y-3">
        {metrics.map(([stage, m]) => (
          <div key={stage} className="flex items-center justify-between p-2 rounded-lg bg-[var(--surface-raised)]">
            <span className="type-body-sm text-[var(--text-secondary)]">{stage.replace(/_/g, " ")}</span>
            <span className="type-label-sm text-[var(--text-muted)]">
              {m.duration_seconds.toFixed(1)}s
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
