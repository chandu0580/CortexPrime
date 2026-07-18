"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import { performanceOverview } from "./dashboardData";
import { Activity, Clock, Award, Users } from "lucide-react";

// Dynamically import Recharts to avoid SSR hydration mismatches
const ResponsiveContainer = dynamic(
  () => import("recharts").then((mod) => mod.ResponsiveContainer),
  { ssr: false }
);
const AreaChart = dynamic(
  () => import("recharts").then((mod) => mod.AreaChart),
  { ssr: false }
);
const Area = dynamic(
  () => import("recharts").then((mod) => mod.Area),
  { ssr: false }
);
const XAxis = dynamic(
  () => import("recharts").then((mod) => mod.XAxis),
  { ssr: false }
);
const YAxis = dynamic(
  () => import("recharts").then((mod) => mod.YAxis),
  { ssr: false }
);
const Tooltip = dynamic(
  () => import("recharts").then((mod) => mod.Tooltip),
  { ssr: false }
);
const CartesianGrid = dynamic(
  () => import("recharts").then((mod) => mod.CartesianGrid),
  { ssr: false }
);
const LineChart = dynamic(
  () => import("recharts").then((mod) => mod.LineChart),
  { ssr: false }
);
const Line = dynamic(
  () => import("recharts").then((mod) => mod.Line),
  { ssr: false }
);

type MetricType = "volume" | "successRate" | "avgRuntime" | "usageCount";

export default function PerformanceChart() {
  const [selectedMetric, setSelectedMetric] = useState<MetricType>("volume");

  const config = {
    volume: {
      label: "Mission Volume",
      color: "#38B88A",
      gradientId: "colorVolume",
      unit: "missions",
      icon: Activity,
      desc: "Total number of autonomous missions executed.",
    },
    successRate: {
      label: "Mission Success Rate",
      color: "#2F9F77",
      gradientId: "colorSuccess",
      unit: "%",
      icon: Award,
      desc: "Percentage of missions completed without errors.",
    },
    avgRuntime: {
      label: "Average Runtime",
      color: "#A16207",
      gradientId: "colorRuntime",
      unit: "s",
      icon: Clock,
      desc: "Average runtime execution duration across agents.",
    },
    usageCount: {
      label: "Daily Usage",
      color: "#1D4ED8",
      gradientId: "colorUsage",
      unit: "users",
      icon: Users,
      desc: "Number of unique users triggering AI tasks daily.",
    },
  };

  const active = config[selectedMetric];

  // Custom tool tip component
  const CustomTooltip = ({ active: isTooltipActive, payload, label }: any) => {
    if (isTooltipActive && payload && payload.length) {
      return (
        <div className="rounded-2xl border border-[#E5E7EB] bg-white p-3.5 shadow-xl">
          <p className="text-xs font-bold text-[#6B7280]">{label}</p>
          <p className="mt-1 text-sm font-extrabold text-[#111827]">
            {payload[0].value.toLocaleString()} {active.unit}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      {/* Header and selector tabs */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            AI Performance Overview
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            {active.desc}
          </p>
        </div>

        {/* Tab Controls */}
        <div className="flex flex-wrap items-center gap-1 rounded-xl bg-[#F8FAFC] p-1 border border-[#E5E7EB]">
          {(Object.keys(config) as MetricType[]).map((key) => {
            const item = config[key];
            const isSelected = selectedMetric === key;
            const Icon = item.icon;

            return (
              <button
                key={key}
                onClick={() => setSelectedMetric(key)}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                  isSelected
                    ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                    : "text-[#6B7280] hover:text-[#111827]"
                }`}
              >
                <Icon className={`h-3.5 w-3.5 ${isSelected ? "text-[#38B88A]" : ""}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="mt-6 h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={performanceOverview}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            <defs>
              <linearGradient id={active.gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={active.color} stopOpacity={0.2} />
                <stop offset="95%" stopColor={active.color} stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
            <XAxis
              dataKey="name"
              stroke="#6B7280"
              fontSize={11}
              fontWeight={600}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#6B7280"
              fontSize={11}
              fontWeight={600}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => {
                if (selectedMetric === "successRate") return `${value}%`;
                return value.toLocaleString();
              }}
              domain={selectedMetric === "successRate" ? [95, 100] : ["auto", "auto"]}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey={selectedMetric}
              stroke={active.color}
              strokeWidth={2.5}
              fillOpacity={1}
              fill={`url(#${active.gradientId})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Quick stats bottom row */}
      <div className="mt-6 grid grid-cols-2 gap-4 border-t border-[#E5E7EB] pt-6 sm:grid-cols-4">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Daily Average</span>
          <p className="mt-1 text-lg font-extrabold text-[#111827]">
            {selectedMetric === "volume" && "1,840"}
            {selectedMetric === "successRate" && "98.7%"}
            {selectedMetric === "avgRuntime" && "38.4s"}
            {selectedMetric === "usageCount" && "834"}
          </p>
        </div>
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Weekly Peak</span>
          <p className="mt-1 text-lg font-extrabold text-[#111827]">
            {selectedMetric === "volume" && "2,240"}
            {selectedMetric === "successRate" && "99.6%"}
            {selectedMetric === "avgRuntime" && "46.0s"}
            {selectedMetric === "usageCount" && "1,010"}
          </p>
        </div>
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Performance Target</span>
          <p className="mt-1 text-lg font-extrabold text-[#38B88A]">
            {selectedMetric === "volume" && "1,500+"}
            {selectedMetric === "successRate" && "> 98.0%"}
            {selectedMetric === "avgRuntime" && "< 45.0s"}
            {selectedMetric === "usageCount" && "800+"}
          </p>
        </div>
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Current Trend</span>
          <p className="mt-1 text-lg font-extrabold text-[#2F9F77]">
            +4.2% Upward
          </p>
        </div>
      </div>
    </div>
  );
}
