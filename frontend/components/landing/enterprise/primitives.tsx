"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import type { ComponentPropsWithoutRef, ReactNode } from "react";

import { ease } from "@/lib/motion-tokens";
import { cn } from "@/utils/cn";

type LandingButtonProps = {
  href: string;
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost";
  size?: "md" | "lg";
  className?: string;
  icon?: boolean;
  ariaLabel?: string;
};

type LandingBadgeProps = {
  children: ReactNode;
  className?: string;
};

type LandingCardProps = ComponentPropsWithoutRef<typeof motion.div> & {
  hover?: boolean;
};

type MetricCardProps = {
  label: string;
  value: string;
  delta?: string;
  footer?: string;
  trend: number[];
  accent?: "green" | "neutral";
  compact?: boolean;
};

function buildPoints(values: number[]) {
  const width = 84;
  const height = 28;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;

  return values
    .map((point, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((point - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");
}

export function LandingButton({
  href,
  children,
  variant = "primary",
  size = "md",
  className,
  icon = false,
  ariaLabel,
}: LandingButtonProps) {
  return (
    <motion.div
      whileHover={{ y: -2, scale: 1.01 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: 0.2, ease: ease.out }}
      className="inline-flex"
    >
      <Link
        href={href}
        aria-label={ariaLabel}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-[18px] border text-[0.96rem] font-semibold tracking-[-0.02em] transition-colors duration-200",
          size === "lg" ? "h-14 px-6" : "h-11 px-5",
          variant === "primary" &&
            "border-[#38B88A] bg-[#38B88A] text-white shadow-[0_12px_30px_rgba(56,184,138,0.24)] hover:border-[#2F9F77] hover:bg-[#2F9F77]",
          variant === "secondary" &&
            "border-[#E5E7EB] bg-white text-[#111827] shadow-[0_10px_24px_rgba(15,23,42,0.06)] hover:border-[#D1D5DB] hover:bg-[#F9FAFB]",
          variant === "ghost" &&
            "border-transparent bg-transparent text-[#6B7280] hover:text-[#111827]",
          className,
        )}
      >
        <span>{children}</span>
        {icon ? <ArrowRight className="h-4 w-4" aria-hidden="true" /> : null}
      </Link>
    </motion.div>
  );
}

export function LandingBadge({ children, className }: LandingBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-[#D6F0E5] bg-white/90 px-4 py-2 text-[0.92rem] font-medium tracking-[-0.02em] text-[#2F9F77] shadow-[0_8px_24px_rgba(148,163,184,0.08)] backdrop-blur",
        className,
      )}
    >
      <span className="h-2 w-2 rounded-full bg-[#38B88A]" aria-hidden="true" />
      {children}
    </span>
  );
}

export function LandingCard({
  className,
  hover = false,
  children,
  ...props
}: LandingCardProps) {
  return (
    <motion.div
      whileHover={hover ? { y: -4, scale: 1.01 } : undefined}
      transition={{ duration: 0.2, ease: ease.out }}
      className={cn(
        "rounded-[30px] border border-[#E5E7EB] bg-white shadow-[0_18px_50px_rgba(148,163,184,0.12)]",
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function MetricCard({
  label,
  value,
  delta,
  footer,
  trend,
  accent = "green",
  compact = false,
}: MetricCardProps) {
  const points = buildPoints(trend);

  /* ── Compact variant (used inside narrow dashboard preview) ── */
  if (compact) {
    return (
      <LandingCard
        hover
        className="flex flex-col gap-2 rounded-[16px] px-3 py-3 shadow-[0_4px_14px_rgba(148,163,184,0.08)]"
      >
        <p className="text-[0.65rem] font-medium leading-tight text-[#6B7280]">{label}</p>
        <div className="flex items-end justify-between gap-1">
          <span
            className="text-[1.2rem] font-semibold leading-none tracking-[-0.04em]"
            style={{ color: "#111827" }}
          >
            {value}
          </span>
          <svg
            viewBox="0 0 84 28"
            className="h-5 w-[44px] shrink-0"
            aria-hidden="true"
            fill="none"
          >
            <path
              d={`M0 27 L${points.split(" ").join(" L")} L84 27 Z`}
              fill="rgba(56,184,138,0.06)"
            />
            <polyline
              points={points}
              stroke="#38B88A"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </LandingCard>
    );
  }

  /* ── Default full-size variant ── */
  return (
    <LandingCard
      hover
      className="flex min-h-[110px] flex-col justify-between rounded-[20px] px-4 py-3.5 shadow-[0_8px_24px_rgba(148,163,184,0.09)]"
    >
      <div className="space-y-2">
        <p className="text-[0.72rem] font-medium text-[#6B7280]">{label}</p>
        <div className="flex items-end justify-between gap-3">
          <div className="flex items-end gap-1.5">
            {/* Special treatment for System Health — show green dot + value */}
            {accent === "neutral" && footer ? (
              <div className="flex flex-col gap-1">
                <span className="text-[1.5rem] font-semibold leading-none tracking-[-0.05em] text-[#111827]">
                  {value}
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-[#22C55E]" />
                  <span className="text-[0.65rem] text-[#22C55E] font-medium">Operational</span>
                </div>
              </div>
            ) : (
              <>
                <span className="text-[1.7rem] font-semibold leading-none tracking-[-0.05em] text-[#111827]">
                  {value}
                </span>
                {delta ? (
                  <span
                    className={cn(
                      "pb-0.5 text-[0.72rem] font-semibold",
                      accent === "green" ? "text-[#22C55E]" : "text-[#6B7280]",
                    )}
                  >
                    {delta}
                  </span>
                ) : null}
              </>
            )}
          </div>
          <svg
            viewBox="0 0 84 28"
            className="h-6 w-[70px] shrink-0"
            aria-hidden="true"
            fill="none"
          >
            <path
              d={`M0 27 L${points.split(" ").join(" L")} L84 27 Z`}
              fill="rgba(56,184,138,0.08)"
            />
            <polyline
              points={points}
              stroke={accent === "green" ? "#38B88A" : "#9CA3AF"}
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>
      {footer && accent !== "neutral" ? (
        <p className="text-[0.68rem] text-[#9CA3AF]">{footer}</p>
      ) : null}
    </LandingCard>
  );
}
