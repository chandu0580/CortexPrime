import type { ReasoningStep } from "@/types/enterprise"

export function ReasoningTrace({ steps }: { steps: ReasoningStep[] }) {
  if (!steps?.length) return null

  return (
    <div className="space-y-2">
      {steps.map((step, i) => (
        <div key={i} className="flex items-start gap-3 p-2.5 rounded-xl bg-[var(--surface-raised)]">
          <span className="type-label-sm text-[var(--accent)] w-6 shrink-0">#{i + 1}</span>
          <div>
            <p className="type-body-sm text-[var(--text-primary)]">{step.description}</p>
            {step.decision && <p className="type-caption text-[var(--text-muted)]">Decision: {step.decision}</p>}
          </div>
        </div>
      ))}
    </div>
  )
}
