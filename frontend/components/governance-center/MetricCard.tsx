"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/utils/cn";
import { variants } from "@/lib/motion-tokens";
import StatusBadge, { GovStatusType } from "./StatusBadge";

interface MetricCardProps {
  title: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral";
  sparkline: number[];
  status: GovStatusType;
  statusText: string;
  delayIndex?: number;
}

export default function MetricCard({
  title,
  value,
  change,
  trend,
  sparkline,
  status,
  statusText,
  delayIndex = 0,
}: MetricCardProps) {
  // SVG Sparkline drawing helper
  const drawSparkline = (data: number[]) => {
    if (!data || data.length === 0) return null;
    const width = 120;
    const height = 30;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const points = data.map((val, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const y = height - ((val - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    });

    const pathD = `M ${points.join(" L ")}`;

    // Set line color based on trend and title
    const isRisk = title.toLowerCase().includes("risk") || title.toLowerCase().includes("events");
    const strokeColor = trend === "down" 
      ? (isRisk ? "#38B88A" : "#EF4444") // Red if non-risk falls, Green if risk falls
      : (isRisk ? "#EF4444" : "#38B88A");

    return (
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
        <path
          d={pathD}
          fill="none"
          stroke={strokeColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  };

  const isUp = trend === "up";
  const isDown = trend === "down";

  // Trend behavior adjustments (cost/risks going down is positive)
  const isRiskOrEvents = title.toLowerCase().includes("risk") || title.toLowerCase().includes("events");
  const isPositiveTrend = (isUp && !isRiskOrEvents) || (isDown && isRiskOrEvents);

  const trendStyles = isPositiveTrend
    ? "text-[#2F9F77] bg-[#E8F5EE]"
    : (trend === "neutral" ? "text-[#4B5563] bg-[#F3F4F6]" : "text-[#B91C1C] bg-[#FEE2E2]");

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: delayIndex * 0.05 }}
      whileHover={variants.cardHover}
      className="flex flex-col justify-between rounded-[24px] border border-[#E5E7EB] bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-shadow duration-200 hover:shadow-[0_12px_36px_rgba(56,184,138,0.06)]"
    >
      <div className="flex items-start justify-between">
        <span className="text-xs font-bold uppercase tracking-wider text-[#6B7280]">
          {title}
        </span>
        <StatusBadge status={status}>{statusText}</StatusBadge>
      </div>

      <div className="mt-4 flex items-baseline justify-between">
        <div>
          <span className="text-3xl font-extrabold tracking-tight text-[#111827]">
            {value}
          </span>
          <div className="mt-2 flex items-center gap-1.5">
            <span className={cn("inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-bold", trendStyles)}>
              {isUp && <TrendingUp className="h-3 w-3" />}
              {isDown && <TrendingDown className="h-3 w-3" />}
              {!isUp && !isDown && <Minus className="h-3 w-3" />}
              {change}
            </span>
            <span className="text-[10px] font-semibold text-[#6B7280]">vs last week</span>
          </div>
        </div>

        <div className="h-8 shrink-0 self-end">
          {drawSparkline(sparkline)}
        </div>
      </div>
    </motion.div>
  );
}
