import { cn } from "@/utils/cn"

export function Spinner({ className, size = "md" }: { className?: string; size?: "sm" | "md" | "lg" }) {
  return (
    <div
      className={cn(
        "animate-spin rounded-full border-2 border-[var(--border)] border-t-[var(--accent)]",
        size === "sm" && "h-4 w-4",
        size === "md" && "h-6 w-6",
        size === "lg" && "h-8 w-8",
        className,
      )}
    />
  )
}
