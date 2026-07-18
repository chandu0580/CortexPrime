import { cn } from "@/utils/cn"
import type { SelectHTMLAttributes } from "react"

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string
  options: { value: string; label: string }[]
}

export function Select({ label, options, className, id, ...props }: SelectProps) {
  const selectId = id ?? label?.toLowerCase().replace(/\s+/g, "-")

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={selectId} className="type-body-sm text-[var(--text-primary)]">
          {label}
        </label>
      )}
      <select
        id={selectId}
        className={cn(
          "h-10 w-full rounded-xl border border-[var(--border)] bg-[var(--surface-panel)] px-3 text-sm text-[var(--text-primary)] outline-none",
          "focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-muted)]",
          className,
        )}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
