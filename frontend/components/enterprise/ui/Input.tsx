import { cn } from "@/utils/cn"
import type { InputHTMLAttributes } from "react"

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string
  error?: string
  wrapperClassName?: string
}

export function Input({ label, error, className, wrapperClassName, id, ...props }: InputProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-")

  return (
    <div className={cn("space-y-1.5", wrapperClassName)}>
      {label && (
        <label htmlFor={inputId} className="type-body-sm text-[var(--text-primary)]">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={cn(
          "h-10 w-full rounded-xl border border-[var(--border)] bg-[var(--surface-panel)] px-3 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]",
          "focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-muted)]",
          error && "border-[var(--danger)]",
          className,
        )}
        {...props}
      />
      {error && <p className="type-caption text-[var(--danger)]">{error}</p>}
    </div>
  )
}
