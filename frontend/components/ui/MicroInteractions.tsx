/**
 * CortexPrime — Micro Interaction Components
 *
 * Premium feel primitives:
 *   <HoverCard>       — lift + glow on hover
 *   <PressButton>     — tactile press feedback
 *   <GlowBorder>      — animated border glow
 *   <Shimmer>         — loading skeleton shimmer
 *   <DepthCard>       — 3-D tilt depth effect
 *   <FadeIn>          — standard entrance
 *   <StaggerList>     — staggered children entrance
 */
"use client"

import { forwardRef, useRef, useState, type CSSProperties, type ReactNode } from "react"
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion"
import { dur, ease, spring, variants, loop } from "@/lib/motion-tokens"

// ─── Types ─────────────────────────────────────────────────────────────────

interface BaseProps {
  children:  ReactNode
  className?: string
  style?:    CSSProperties
}

// ─── HoverCard — lift + subtle glow on hover ───────────────────────────────

interface HoverCardProps extends BaseProps {
  /** Lift distance in px (default 4) */
  lift?:    number
  /** Accent color for glow (default: --accent-primary) */
  glowColor?: string
  /** Scale on hover (default 1.012) */
  scale?:   number
  onClick?: () => void
}

export function HoverCard({
  children, className, style, lift = 4, glowColor, scale = 1.012, onClick,
}: HoverCardProps) {
  const [hovered, setHovered] = useState(false)

  return (
    <motion.div
      className={className}
      style={{ cursor: onClick ? "pointer" : "default", willChange: "transform", ...style }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      animate={{
        y:         hovered ? -lift : 0,
        scale:     hovered ? scale : 1,
        boxShadow: hovered
          ? `0 8px 32px rgba(0,0,0,0.35), 0 0 0 1px ${glowColor ?? "rgba(130,192,164,0.28)"}`
          : "0 2px 8px rgba(0,0,0,0.2)",
      }}
      transition={{ duration: dur.fast, ease: ease.out }}
      onClick={onClick}
    >
      {children}
    </motion.div>
  )
}

// ─── PressButton — full tactile feedback ───────────────────────────────────

interface PressButtonProps extends BaseProps {
  onClick?:  () => void
  disabled?: boolean
  type?:     "button" | "submit" | "reset"
}

export function PressButton({ children, className, style, onClick, disabled, type = "button" }: PressButtonProps) {
  return (
    <motion.button
      type={type}
      className={className}
      style={{ outline: "none", cursor: disabled ? "not-allowed" : "pointer", ...style }}
      whileHover={disabled ? {} : { scale: 1.03, y: -1, transition: { duration: dur.fast, ease: ease.out } }}
      whileTap={disabled  ? {} : { scale: 0.96,  y: 1,  transition: { duration: dur.snap, ease: ease.inOut } }}
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
    >
      {children}
    </motion.button>
  )
}

// ─── GlowBorder — animated accent border that brightens on hover ───────────

interface GlowBorderProps extends BaseProps {
  color?:     string
  intensity?: number   // 0-1
  radius?:    number
}

export function GlowBorder({ children, className, style, color = "rgba(130,192,164,0.4)", intensity = 1, radius = 14 }: GlowBorderProps) {
  const [hovered, setHovered] = useState(false)
  return (
    <motion.div
      className={className}
      style={{ position: "relative", borderRadius: radius, ...style }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
    >
      {/* Glow ring */}
      <motion.div
        aria-hidden
        style={{
          position:     "absolute",
          inset:        -1,
          borderRadius: radius + 1,
          border:       `1px solid ${color}`,
          pointerEvents:"none",
          zIndex:       0,
        }}
        animate={{ opacity: hovered ? intensity : intensity * 0.4 }}
        transition={{ duration: dur.fast }}
      />
      {/* Content */}
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </motion.div>
  )
}

// ─── Shimmer — skeleton loading shimmer ────────────────────────────────────

interface ShimmerProps {
  width?:    number | string
  height?:  number | string
  radius?:  number
  className?: string
}

export function Shimmer({ width = "100%", height = 16, radius = 6, className }: ShimmerProps) {
  return (
    <div
      className={className}
      style={{
        width,
        height,
        borderRadius: radius,
        background:   "var(--surface-raised, #1a2940)",
        overflow:     "hidden",
        position:     "relative",
      }}
    >
      <motion.div
        style={{
          position:   "absolute",
          inset:      0,
          background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.06) 40%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0.06) 60%, transparent 100%)",
        }}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        animate={loop.shimmer as any}
      />
    </div>
  )
}

/** A block of stacked shimmer lines — for card placeholder */
export function ShimmerCard({ lines = 3 }: { lines?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "16px" }}>
      <Shimmer height={14} width="60%" />
      {Array.from({ length: lines }).map((_, i) => (
        <Shimmer key={i} height={10} width={i === lines - 1 ? "45%" : "100%"} />
      ))}
    </div>
  )
}

// ─── DepthCard — mouse-tracking 3-D tilt ───────────────────────────────────

interface DepthCardProps extends BaseProps {
  maxTilt?: number   // degrees (default 8)
  depth?:   number   // translate Z equivalent (default 20)
}

export function DepthCard({ children, className, style, maxTilt = 8, depth = 20 }: DepthCardProps) {
  const ref = useRef<HTMLDivElement>(null)

  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  const rotateX = useSpring(useTransform(mouseY, [-0.5, 0.5], [maxTilt, -maxTilt]), { stiffness: 400, damping: 40 })
  const rotateY = useSpring(useTransform(mouseX, [-0.5, 0.5], [-maxTilt, maxTilt]), { stiffness: 400, damping: 40 })
  const z       = useSpring(useMotionValue(0), { stiffness: 400, damping: 40 })

  function onMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const rect = ref.current?.getBoundingClientRect()
    if (!rect) return
    mouseX.set((e.clientX - rect.left) / rect.width  - 0.5)
    mouseY.set((e.clientY - rect.top)  / rect.height - 0.5)
    z.set(depth)
  }

  function onMouseLeave() {
    mouseX.set(0)
    mouseY.set(0)
    z.set(0)
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      style={{ ...style, perspective: 900, transformStyle: "preserve-3d" }}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
    >
      <motion.div style={{ rotateX, rotateY, translateZ: z }}>
        {children}
      </motion.div>
    </motion.div>
  )
}

// ─── FadeIn — standard entrance animation ──────────────────────────────────

interface FadeInProps extends BaseProps {
  delay?: number
  direction?: "up" | "down" | "left" | "right" | "none"
  distance?: number
}

export function FadeIn({ children, className, style, delay = 0, direction = "up", distance = 16 }: FadeInProps) {
  const initial: Record<string, number> = { opacity: 0 }
  if (direction === "up")    initial.y = distance
  if (direction === "down")  initial.y = -distance
  if (direction === "left")  initial.x = distance
  if (direction === "right") initial.x = -distance

  return (
    <motion.div
      className={className}
      style={style}
      initial={initial}
      whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: dur.base, ease: ease.out, delay }}
    >
      {children}
    </motion.div>
  )
}

// ─── StaggerList — staggered children entrance ─────────────────────────────

interface StaggerListProps extends BaseProps {
  staggerDelay?: number
  childDelay?:   number
}

export function StaggerList({ children, className, style, staggerDelay = 0.07, childDelay = 0 }: StaggerListProps) {
  return (
    <motion.div
      className={className}
      style={style}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-40px" }}
      variants={{
        hidden:  {},
        visible: { transition: { staggerChildren: staggerDelay, delayChildren: childDelay } },
      }}
    >
      {children}
    </motion.div>
  )
}

/** Pair with <StaggerList> — each direct child should be wrapped in this */
export function StaggerItem({ children, className, style }: BaseProps) {
  return (
    <motion.div
      className={className}
      style={style}
      variants={variants.fadeUp}
    >
      {children}
    </motion.div>
  )
}

// ─── PulsingDot — animated status indicator ────────────────────────────────

interface PulsingDotProps {
  color?: string
  size?:  number
}

export function PulsingDot({ color = "#4a8c70", size = 7 }: PulsingDotProps) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: size, height: size, flexShrink: 0 }}>
      {/* Ping ring */}
      <motion.span
        style={{
          position:     "absolute",
          inset:        0,
          borderRadius: "50%",
          background:   color,
          opacity:      0.4,
        }}
        animate={{ scale: [1, 2.2], opacity: [0.5, 0] }}
        transition={{ repeat: Infinity, duration: 1.6, ease: "easeOut" }}
      />
      {/* Core dot */}
      <span style={{ width: size, height: size, borderRadius: "50%", background: color, display: "block", flexShrink: 0 }} />
    </span>
  )
}

// ─── GlowText — text with animated accent glow ─────────────────────────────

export function GlowText({ children, color = "#82c0a4", className, style }: BaseProps & { color?: string }) {
  return (
    <motion.span
      className={className}
      style={{ color, ...style }}
      animate={{
        textShadow: [
          `0 0 20px ${color}40`,
          `0 0 40px ${color}70`,
          `0 0 20px ${color}40`,
        ],
      }}
      transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
    >
      {children}
    </motion.span>
  )
}

// ─── NumberTick — animated counter ────────────────────────────────────────

import { useEffect } from "react"
import { useMotionValue as useMV, animate as fmAnimate } from "framer-motion"

interface NumberTickProps {
  value:      number
  decimals?:  number
  prefix?:    string
  suffix?:    string
  className?: string
  style?:     CSSProperties
}

export function NumberTick({ value, decimals = 0, prefix = "", suffix = "", className, style }: NumberTickProps) {
  const mv     = useMV(0)
  const ref    = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const ctrl = fmAnimate(mv, value, {
      duration: dur.slow,
      ease: ease.out,
      onUpdate(v) {
        if (ref.current) {
          ref.current.textContent = prefix + v.toFixed(decimals) + suffix
        }
      },
    })
    return () => ctrl.stop()
  }, [value, decimals, prefix, suffix])

  return (
    <span ref={ref} className={className} style={style}>
      {prefix}{(0).toFixed(decimals)}{suffix}
    </span>
  )
}
