"use client"

import {
  Component,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ErrorInfo,
  type ReactNode,
} from "react"
import { motion } from "framer-motion"
import {
  AlertCircle,
  RotateCcw,
  Loader2,
  ChevronRight,
} from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { dur, ease, spring, variants } from "@/lib/motion-tokens"
import { cn } from "@/utils/cn"

// ─── Skeleton ──────────────────────────────────────────────────────────────

interface SkeletonProps {
  variant?: "line" | "card" | "avatar" | "table" | "stat"
  width?: string | number
  height?: string | number
  className?: string
  count?: number
  rounded?: string
}

export function Skeleton({
  variant = "line",
  width,
  height,
  className,
  count = 1,
  rounded,
}: SkeletonProps) {
  const variantsMap: Record<string, { w: string; h: string; r: string }> = {
    line: { w: "100%", h: "16px", r: "6px" },
    card: { w: "100%", h: "128px", r: "18px" },
    avatar: { w: "40px", h: "40px", r: "9999px" },
    stat: { w: "100%", h: "80px", r: "14px" },
    table: { w: "100%", h: "48px", r: "0" },
  }

  const def = variantsMap[variant] ?? variantsMap.line

  const items = Array.from({ length: Math.max(1, count) })

  if (variant === "table") {
    return (
      <div className="flex flex-col overflow-hidden rounded-[14px] border border-[#E8EDF3]">
        {Array.from({ length: 5 }).map((_, row) => (
          <div key={row} className="flex border-b border-[#E8EDF3] last:border-b-0">
            {Array.from({ length: 4 }).map((_, col) => (
              <div
                key={col}
                className="flex-1 border-r border-[#E8EDF3] last:border-r-0 p-4"
              >
                <Skeleton variant="line" width={col === 0 ? "60%" : "80%"} />
              </div>
            ))}
          </div>
        ))}
      </div>
    )
  }

  return (
    <>
      {items.map((_, i) => (
        <div
          key={i}
          className={cn("relative overflow-hidden bg-[#F3F4F6]", className)}
          style={{
            width: width ?? def.w,
            height: height ?? def.h,
            borderRadius: rounded ?? def.r,
          }}
        >
          <motion.div
            className="absolute inset-0"
            style={{
              background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.5) 40%, rgba(255,255,255,0.8) 50%, rgba(255,255,255,0.5) 60%, transparent 100%)",
            }}
            animate={{ x: ["-100%", "100%"] }}
            transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
          />
        </div>
      ))}
    </>
  )
}

// ─── SkeletonPage ──────────────────────────────────────────────────────────

export function SkeletonPage({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton variant="line" width="200px" height="24px" />
          <Skeleton variant="line" width="300px" height="14px" />
        </div>
        <Skeleton variant="line" width="120px" height="44px" rounded="14px" />
      </div>

      {/* 3 Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} variant="card" />
        ))}
      </div>

      {/* Table */}
      <Skeleton variant="table" />
    </div>
  )
}

// ─── ErrorBoundary ────────────────────────────────────────────────────────

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="flex flex-col items-center justify-center rounded-[18px] border border-[#FECACA] bg-[#FEF2F2] p-8 text-center">
          <AlertCircle className="mb-3 h-10 w-10 text-[#EF4444]" />
          <h3 className="text-lg font-bold text-[#111827]">Something went wrong</h3>
          <p className="mt-1 max-w-md text-sm text-[#6B7280]">
            {this.state.error?.message ?? "An unexpected error occurred."}
          </p>
          <motion.button
            onClick={this.handleRetry}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="mt-4 flex items-center gap-2 rounded-[14px] border border-[#E8EDF3] bg-white px-5 py-2.5 text-sm font-semibold text-[#374151] shadow-[0_2px_8px_rgba(148,163,184,0.1)] transition-colors hover:bg-[#F9FAFB]"
          >
            <RotateCcw className="h-4 w-4" />
            Try Again
          </motion.button>
        </div>
      )
    }

    return this.props.children
  }
}

// ─── LoadingOverlay ────────────────────────────────────────────────────────

interface LoadingOverlayProps {
  isLoading: boolean
  message?: string
  children?: ReactNode
  className?: string
}

export function LoadingOverlay({
  isLoading,
  message = "Loading...",
  children,
  className,
}: LoadingOverlayProps) {
  if (!isLoading) return <>{children}</>

  return (
    <div className={cn("relative", className)}>
      {children && (
        <div className="pointer-events-none select-none opacity-30 blur-sm">
          {children}
        </div>
      )}
      <div className="absolute inset-0 z-50 flex flex-col items-center justify-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
          className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-[#E8EDF3] border-t-[#38B88A]"
        >
          <Loader2 className="h-5 w-5 text-[#38B88A]" />
        </motion.div>
        {message && (
          <p className="mt-3 text-sm font-medium text-[#6B7280]">{message}</p>
        )}
      </div>
    </div>
  )
}

// ─── MicroInteraction ──────────────────────────────────────────────────────

interface MicroInteractionProps {
  children: ReactNode
  hoverScale?: number
  tapScale?: number
  className?: string
  as?: "div" | "span"
}

export function MicroInteraction({
  children,
  hoverScale = 1.02,
  tapScale = 0.98,
  className,
  as = "div",
}: MicroInteractionProps) {
  const Component = as === "span" ? motion.span : motion.div

  return (
    <Component
      whileHover={{ scale: hoverScale }}
      whileTap={{ scale: tapScale }}
      transition={{ duration: dur.fast, ease: ease.out }}
      className={cn("will-change-transform", className)}
    >
      {children}
    </Component>
  )
}

// ─── FadeIn ────────────────────────────────────────────────────────────────

interface FadeInProps {
  children: ReactNode
  delay?: number
  direction?: "up" | "down" | "left" | "right" | "none"
  distance?: number
  className?: string
  once?: boolean
}

export function FadeIn({
  children,
  delay = 0,
  direction = "up",
  distance = 24,
  className,
  once = true,
}: FadeInProps) {
  const initial: Record<string, number> = { opacity: 0 }
  if (direction === "up") initial.y = distance
  if (direction === "down") initial.y = -distance
  if (direction === "left") initial.x = distance
  if (direction === "right") initial.x = -distance

  return (
    <motion.div
      className={className}
      initial={initial}
      whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={{ once, margin: "-40px" }}
      transition={{ duration: dur.base, ease: ease.out, delay }}
    >
      {children}
    </motion.div>
  )
}

// ─── StaggerContainer ──────────────────────────────────────────────────────

interface StaggerContainerProps {
  children: ReactNode
  staggerDelay?: number
  className?: string
}

export function StaggerContainer({
  children,
  staggerDelay = 0.05,
  className,
}: StaggerContainerProps) {
  const childrenArray = useMemo(
    () => (Array.isArray(children) ? children : [children]),
    [children],
  )

  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-40px" }}
      variants={{
        hidden: {},
        visible: {
          transition: {
            staggerChildren: staggerDelay,
          },
        },
      }}
    >
      {childrenArray.map((child, i) => (
        <motion.div
          key={i}
          variants={{
            hidden: { opacity: 0, y: 16 },
            visible: { opacity: 1, y: 0, transition: { duration: dur.base, ease: ease.out } },
          }}
        >
          {child}
        </motion.div>
      ))}
    </motion.div>
  )
}

// ─── TransitionLink ────────────────────────────────────────────────────────

const TransitionContext = createContext<{
  isTransitioning: boolean
  setIsTransitioning: (v: boolean) => void
}>({
  isTransitioning: false,
  setIsTransitioning: () => {},
})

export function TransitionProvider({ children }: { children: ReactNode }) {
  const [isTransitioning, setIsTransitioning] = useState(false)

  const value = useMemo(
    () => ({ isTransitioning, setIsTransitioning }),
    [isTransitioning],
  )

  return (
    <TransitionContext.Provider value={value}>
      {children}
      <TransitionOverlay isTransitioning={isTransitioning} />
    </TransitionContext.Provider>
  )
}

function TransitionOverlay({ isTransitioning }: { isTransitioning: boolean }) {
  return (
    <motion.div
      className="pointer-events-none fixed inset-0 z-[99999] bg-white"
      initial={false}
      animate={isTransitioning ? { opacity: 1 } : { opacity: 0 }}
      transition={{ duration: dur.fast }}
      style={{ pointerEvents: isTransitioning ? "auto" : "none" }}
    />
  )
}

interface TransitionLinkProps {
  href: string
  children: ReactNode
  className?: string
}

export function TransitionLink({ href, children, className }: TransitionLinkProps) {
  const { setIsTransitioning } = useContext(TransitionContext)
  const pathname = usePathname()

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (pathname === href) {
      e.preventDefault()
      return
    }
    setIsTransitioning(true)
    setTimeout(() => {
      setIsTransitioning(false)
    }, 350)
  }

  return (
    <Link
      href={href}
      onClick={handleClick}
      className={cn(
        "transition-opacity duration-200 hover:opacity-80",
        className,
      )}
    >
      {children}
    </Link>
  )
}

// ─── ResponsiveContainer ───────────────────────────────────────────────────

interface ResponsiveContainerProps {
  children: ReactNode
  className?: string
  as?: "div" | "main" | "section"
}

export function ResponsiveContainer({
  children,
  className,
  as: Tag = "div",
}: ResponsiveContainerProps) {
  return (
    <Tag
      className={cn(
        "mx-auto w-full max-w-[1500px] px-4 sm:px-6 lg:px-8",
        className,
      )}
    >
      {children}
    </Tag>
  )
}

// ─── PageHeader ────────────────────────────────────────────────────────────

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: ReactNode
  className?: string
  backLink?: string
  onBack?: () => void
}

export function PageHeader({
  title,
  subtitle,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 pb-6 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-[#111827]">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm font-medium text-[#6B7280]">{subtitle}</p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 items-center gap-3">{actions}</div>
      )}
    </div>
  )
}