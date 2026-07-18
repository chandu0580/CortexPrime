"use client"

import { motion } from "framer-motion"
import { Loader2 } from "lucide-react"
import type { ButtonHTMLAttributes, ReactNode } from "react"
import { cn } from "@/utils/cn"

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger"
type ButtonSize = "sm" | "md" | "lg"

type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart"> & {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  leftIcon,
  rightIcon,
  className,
  children,
  type = "button",
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading

  return (
    <motion.button
      type={type}
      whileHover={isDisabled ? undefined : { y: -1 }}
      whileTap={isDisabled ? undefined : { scale: 0.98 }}
      disabled={isDisabled}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" && "h-8 px-3 text-xs",
        size === "md" && "h-10 px-4 text-sm",
        size === "lg" && "h-12 px-6 text-base",
        variant === "primary" && "bg-[var(--accent)] text-white hover:opacity-90",
        variant === "secondary" && "border border-[var(--border)] bg-[var(--surface-panel)] text-[var(--text-primary)] hover:bg-[var(--surface-raised)]",
        variant === "ghost" && "bg-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-raised)]",
        variant === "danger" && "bg-[var(--danger)] text-white hover:opacity-90",
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : leftIcon}
      <span>{children}</span>
      {!loading ? rightIcon : null}
    </motion.button>
  )
}
