"use client"

import { motion } from "framer-motion"
import type { ReactNode } from "react"
import { cn } from "@/utils/cn"

export function Card({
  className,
  children,
  hover = false,
  ...props
}: {
  className?: string
  children: ReactNode
  hover?: boolean
}) {
  return (
    <motion.div
      whileHover={hover ? { y: -2, scale: 1.005 } : undefined}
      transition={{ duration: 0.2 }}
      className={cn("surface-panel p-5", className)}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export function CardHeader({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return <div className={cn("mb-4", className)}>{children}</div>
}

export function CardTitle({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return <h3 className={cn("type-heading-sm text-[var(--text-primary)]", className)}>{children}</h3>
}

export function CardContent({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return <div className={cn(className)}>{children}</div>
}
