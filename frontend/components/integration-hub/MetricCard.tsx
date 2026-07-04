"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/utils/cn";
import { variants } from "@/lib/motion-tokens";
import StatusBadge, { IntegrationStatusType } from "./StatusBadge";

interface MetricCardProps {
  title: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral";
  sparkline: number[];
  status: IntegrationStatusType;
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
  // Sparkline builder
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

    // Color indicators based on trend types
    const strokeColor =
      trend === "up"
        ? "#38B88A" // Green for positive trends
        : trend === "down"
        ? "#EF4444" // Red for down trends
        : "#6B7280"; // Gray for neutral

    return (
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible" aria-hidden="true">
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

  // Trend styling overrides (for failed connections, down is positive, up is negative)
  const isFailedCard = title.toLowerCase().includes("failed");
  const isPositiveTrend = (isUp && !isFailedCard) || (isDown && isFailedCard);

  const trendStyles = isPositiveTrend
    ? "text-[#2F9F77] bg-[#E8F5EE]"
    : trend === "neutral"
    ? "text-[#4B5563] bg-[#F3F4F6]"
    : "text-[#B91C1C] bg-[#FEE2E2]";

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: delayIndex * 0.05 }}
      whileHover={variants.cardHover}
      className="flex flex-col justify-between rounded-[24px] border border-[#E5E7EB] bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-shadow duration-200 hover:shadow-[0_12px_36px_rgba(56,184,138,0.06)]"
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <span className="text-xs font-bold uppercase tracking-wider text-[#6B7280]">
          {title}
        </span>
        <StatusBadge status={status}>{statusText}</StatusBadge>
      </div>

      {/* Main Metric Section */}
      <div className="mt-4 flex items-baseline justify-between">
        <div>
          <span className="text-3xl font-extrabold tracking-tight text-[#111827]">
            {value}
          </span>
          <div className="mt-2 flex items-center gap-1.5">
            <span className={cn("inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-bold", trendStyles)}>
              {isUp && <TrendingUp className="h-3 w-3" />}
              {isDown && <TrendingDown className="h-3 w-3" />}
              {trend === "neutral" && <Minus className="h-3 w-3" />}
              <span>{change}</span>
            </span>
          </div>
        </div>

        {/* Sparkline Graph */}
        <div className="flex items-center">{drawSparkline(sparkline)}</div>
      </div>
    </motion.div>
  );
}
