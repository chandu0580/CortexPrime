"use client";

import { motion } from "framer-motion";
import { cn } from "@/utils/cn";
import { variants } from "@/lib/motion-tokens";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtext?: string;
  className?: string;
  icon?: React.ComponentType<{ className?: string }>;
  iconClassName?: string;
}

export default function MetricCard({
  title,
  value,
  subtext,
  className,
  icon: Icon,
  iconClassName,
}: MetricCardProps) {
  return (
    <motion.div
      whileHover={variants.cardHover}
      initial="hidden"
      animate="visible"
      variants={variants.fadeIn}
      className={cn(
        "rounded-[24px] border border-[#E5E7EB] bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-shadow duration-200 hover:shadow-[0_12px_36px_rgba(56,184,138,0.06)]",
        className
      )}
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-[#6B7280]">
            {title}
          </span>
          <h3 className="mt-1 text-2xl font-bold tracking-tight text-[#111827]">
            {value}
          </h3>
          {subtext && (
            <p className="mt-1 text-xs font-medium text-[#6B7280]">
              {subtext}
            </p>
          )}
        </div>
        {Icon && (
          <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl bg-[#E8F5EE] text-[#38B88A]", iconClassName)}>
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
    </motion.div>
  );
}
