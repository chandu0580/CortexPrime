"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { apiTrendsData } from "./mockData";
import { Activity, ShieldAlert, Cpu, ChevronDown } from "lucide-react";

// Dynamic Recharts imports to prevent Next.js App Router hydration errors
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

export default function APIChart() {
  const [activeTab, setActiveTab] = useState<"volume" | "performance" | "security">("volume");
  const [timeRange, setTimeRange] = useState("Last 24 Hours");

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="rounded-2xl border border-[#E5E7EB] bg-white p-3.5 shadow-xl text-xs font-semibold">
          <p className="font-bold text-[#6B7280]">{label}</p>
          <div className="mt-2 flex flex-col gap-1.5">
            {payload.map((p: any) => (
              <div key={p.name} className="flex justify-between gap-6">
                <span className="text-[#6B7280]">{p.name}</span>
                <span style={{ color: p.color }} className="font-extrabold">
                  {p.value.toLocaleString()}
                  {p.name.includes("Rate") || p.name.includes("Limit") ? "%" : p.name.includes("Latency") ? " ms" : p.name.includes("Traffic") ? " MB" : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      {/* Header */}
      <div className="flex flex-col gap-4 border-b border-[#F3F4F6] pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            API Integration Activity Logs
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Review API requests volume, success rates, latency response times, and limits.
          </p>
        </div>

        {/* Tab Selection Controls */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 rounded-xl bg-[#F8FAFC] p-1 border border-[#E5E7EB]">
            <button
              onClick={() => setActiveTab("volume")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                activeTab === "volume"
                  ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                  : "text-[#6B7280] hover:text-[#111827]"
              }`}
            >
              <Activity className="h-3.5 w-3.5" />
              Volume
            </button>
            <button
              onClick={() => setActiveTab("performance")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                activeTab === "performance"
                  ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                  : "text-[#6B7280] hover:text-[#111827]"
              }`}
            >
              <Cpu className="h-3.5 w-3.5" />
              Performance
            </button>
            <button
              onClick={() => setActiveTab("security")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                activeTab === "security"
                  ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                  : "text-[#6B7280] hover:text-[#111827]"
              }`}
            >
              <ShieldAlert className="h-3.5 w-3.5" />
              Security
            </button>
          </div>

          <div className="relative inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3 py-1.5 text-xs font-bold text-[#111827] cursor-pointer">
            <span>{timeRange}</span>
            <ChevronDown className="ml-1 h-3 w-3 text-[#6B7280]" />
          </div>
        </div>
      </div>

      {/* Chart visualization */}
      <div className="mt-6 h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={apiTrendsData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorPrimary" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38B88A" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#38B88A" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="colorSecondary" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="colorDanger" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#EF4444" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#EF4444" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F3F4F6" />
            <XAxis
              dataKey="time"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#9CA3AF", fontSize: 10, fontWeight: "bold" }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#9CA3AF", fontSize: 10, fontWeight: "bold" }}
            />
            <Tooltip content={<CustomTooltip />} />

            {activeTab === "volume" && (
              <>
                <Area
                  type="monotone"
                  dataKey="requests"
                  name="API Requests"
                  stroke="#38B88A"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorPrimary)"
                />
                <Area
                  type="monotone"
                  dataKey="traffic"
                  name="Traffic Sent (MB)"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorSecondary)"
                />
              </>
            )}

            {activeTab === "performance" && (
              <>
                <Area
                  type="monotone"
                  dataKey="responseTime"
                  name="Avg Latency (ms)"
                  stroke="#38B88A"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorPrimary)"
                />
                <Area
                  type="monotone"
                  dataKey="successRate"
                  name="Success Rate (%)"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorSecondary)"
                />
              </>
            )}

            {activeTab === "security" && (
              <>
                <Area
                  type="monotone"
                  dataKey="rateLimitUsage"
                  name="Rate Limit Usage (%)"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorSecondary)"
                />
                <Area
                  type="monotone"
                  dataKey="authErrors"
                  name="Auth Errors Count"
                  stroke="#EF4444"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorDanger)"
                />
              </>
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
