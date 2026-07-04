"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { performanceTrendsData } from "./mockData";
import { Cpu, HardDrive, Layers, Clock, ChevronDown } from "lucide-react";

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
const Legend = dynamic(
  () => import("recharts").then((mod) => mod.Legend),
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

export default function PerformanceChart() {
  const [activeTab, setActiveTab] = useState<"resources" | "traffic" | "queues">("resources");
  const [timeRange, setTimeRange] = useState("Last 24 Hours");

  const ranges = ["Last Hour", "Last 24 Hours", "Last 7 Days", "Last 30 Days"];

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="rounded-2xl border border-[#E5E7EB] bg-white p-3.5 shadow-xl text-xs">
          <p className="font-bold text-[#6B7280]">{label}</p>
          <div className="mt-2 flex flex-col gap-1">
            {payload.map((p: any) => (
              <div key={p.name} className="flex justify-between gap-6 font-semibold">
                <span className="text-[#6B7280]">{p.name}</span>
                <span style={{ color: p.color }}>
                  {p.value.toLocaleString()} {p.name.includes("Usage") || p.name.includes("Rate") ? "%" : p.name.includes("Network") ? "MB/s" : "req/s"}
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
            Resource Usage & Performance Trends
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Analyze cluster node metrics, event requests, queue depths, and memory rates.
          </p>
        </div>

        {/* Tab Controls & Time selector */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Tab buttons */}
          <div className="flex items-center gap-1 rounded-xl bg-[#F8FAFC] p-1 border border-[#E5E7EB]">
            <button
              onClick={() => setActiveTab("resources")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                activeTab === "resources"
                  ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                  : "text-[#6B7280] hover:text-[#111827]"
              }`}
            >
              <Cpu className="h-3.5 w-3.5" />
              <span>Resource Usage</span>
            </button>
            <button
              onClick={() => setActiveTab("traffic")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                activeTab === "traffic"
                  ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                  : "text-[#6B7280] hover:text-[#111827]"
              }`}
            >
              <HardDrive className="h-3.5 w-3.5" />
              <span>System Traffic</span>
            </button>
            <button
              onClick={() => setActiveTab("queues")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                activeTab === "queues"
                  ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                  : "text-[#6B7280] hover:text-[#111827]"
              }`}
            >
              <Layers className="h-3.5 w-3.5" />
              <span>Queues & Lag</span>
            </button>
          </div>

          {/* Time range selector */}
          <div className="relative">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="appearance-none rounded-xl border border-[#E5E7EB] bg-white pl-3.5 pr-8 py-2 text-xs font-semibold text-[#111827] shadow-sm outline-none cursor-pointer hover:bg-[#F9FAFB]"
            >
              {ranges.map(range => (
                <option key={range} value={range}>{range}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-[#6B7280] pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="mt-6 h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          {activeTab === "resources" ? (
            <AreaChart
              data={performanceTrendsData}
              margin={{ top: 10, right: 10, left: -25, bottom: 0 }}
            >
              <defs>
                <linearGradient id="colorCPUGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#38B88A" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#38B88A" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="colorMemGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#1D4ED8" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#1D4ED8" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
              <XAxis dataKey="time" stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} />
              <YAxis stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} unit="%" />
              <Tooltip content={<CustomTooltip />} />
              <Legend verticalAlign="top" height={36} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: "11px", fontWeight: 600 }} />
              <Area type="monotone" name="CPU Usage" dataKey="cpu" stroke="#38B88A" strokeWidth={2.5} fillOpacity={1} fill="url(#colorCPUGrad)" />
              <Area type="monotone" name="Memory Usage" dataKey="memory" stroke="#1D4ED8" strokeWidth={2} fillOpacity={1} fill="url(#colorMemGrad)" />
            </AreaChart>
          ) : activeTab === "traffic" ? (
            <LineChart
              data={performanceTrendsData}
              margin={{ top: 10, right: 10, left: -25, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
              <XAxis dataKey="time" stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} />
              <YAxis stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend verticalAlign="top" height={36} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: "11px", fontWeight: 600 }} />
              <Line type="monotone" name="API Requests" dataKey="requests" stroke="#38B88A" strokeWidth={2.5} dot={false} />
              <Line type="monotone" name="Network traffic" dataKey="network" stroke="#A16207" strokeWidth={2} dot={false} />
            </LineChart>
          ) : (
            <AreaChart
              data={performanceTrendsData}
              margin={{ top: 10, right: 10, left: -25, bottom: 0 }}
            >
              <defs>
                <linearGradient id="colorLatencyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#EF4444" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#EF4444" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
              <XAxis dataKey="time" stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} />
              <YAxis stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} unit="ms" />
              <Tooltip content={<CustomTooltip />} />
              <Legend verticalAlign="top" height={36} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: "11px", fontWeight: 600 }} />
              <Area type="monotone" name="Error Rate" dataKey="errorRate" stroke="#EF4444" strokeWidth={2.5} fillOpacity={1} fill="url(#colorLatencyGrad)" />
              <Area type="monotone" name="Average Latency" dataKey="latency" stroke="#38B88A" strokeWidth={2} fillOpacity={0} />
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
