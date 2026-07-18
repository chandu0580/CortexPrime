"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { costOverview, spendTrend, modelCostBreakdown } from "./dashboardData";
import { DollarSign, Cpu, Layers } from "lucide-react";

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
const PieChart = dynamic(
  () => import("recharts").then((mod) => mod.PieChart),
  { ssr: false }
);
const Pie = dynamic(
  () => import("recharts").then((mod) => mod.Pie),
  { ssr: false }
);
const Cell = dynamic(
  () => import("recharts").then((mod) => mod.Cell),
  { ssr: false }
);

export default function CostChart() {
  const [activeTab, setActiveTab] = useState<"spend" | "models">("spend");

  // Custom tool tip component
  const CustomSpendTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const total = payload.reduce((sum: number, p: any) => sum + p.value, 0);
      return (
        <div className="rounded-2xl border border-[#E5E7EB] bg-white p-3.5 shadow-xl text-xs">
          <p className="font-bold text-[#6B7280]">{label}</p>
          <div className="mt-2 flex flex-col gap-1 border-b border-[#F3F4F6] pb-2">
            {payload.map((p: any) => (
              <div key={p.name} className="flex justify-between gap-6 font-semibold">
                <span className="text-[#6B7280]">{p.name}</span>
                <span style={{ color: p.color }}>${p.value}</span>
              </div>
            ))}
          </div>
          <div className="mt-2 flex justify-between font-bold text-[#111827]">
            <span>Total Spend</span>
            <span>${total}</span>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      {/* Header and selector tabs */}
      <div className="flex flex-col gap-4 border-b border-[#F3F4F6] pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            Cost & Spend Intelligence
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Analyze token usage, model execution fee distributions, and cloud compute costs.
          </p>
        </div>

        {/* Tab Controls */}
        <div className="flex items-center gap-1 rounded-xl bg-[#F8FAFC] p-1 border border-[#E5E7EB]">
          <button
            onClick={() => setActiveTab("spend")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all ${
              activeTab === "spend"
                ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                : "text-[#6B7280] hover:text-[#111827]"
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Spend Analysis</span>
          </button>
          <button
            onClick={() => setActiveTab("models")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all ${
              activeTab === "models"
                ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                : "text-[#6B7280] hover:text-[#111827]"
            }`}
          >
            <Cpu className="h-3.5 w-3.5" />
            <span>Model Costs</span>
          </button>
        </div>
      </div>

      {/* Grid containing metrics on left and charts on right */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Side: Spend Metrics Column */}
        <div className="flex flex-col justify-between gap-4 lg:border-r lg:border-[#F3F4F6] lg:pr-6">
          <div className="flex flex-col gap-4">
            {/* Daily Spend */}
            <div className="rounded-xl border border-[#E5E7EB] bg-[#F8FAFC] p-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Daily Spend Today</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-extrabold text-[#111827]">${costOverview.dailySpend.toLocaleString()}</span>
                <span className="text-[10px] font-bold text-[#2F9F77]">-11.2%</span>
              </div>
            </div>

            {/* Monthly Spend */}
            <div className="rounded-xl border border-[#E5E7EB] bg-[#F8FAFC] p-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Monthly Spend (MTD)</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-extrabold text-[#111827]">${costOverview.monthlySpend.toLocaleString()}</span>
                <span className="text-[10px] font-bold text-[#6B7280]">Target $15k</span>
              </div>
            </div>

            {/* Projected Spend */}
            <div className="rounded-xl border border-[#E5E7EB] bg-[#F8FAFC] p-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Projected Monthly Spend</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-2xl font-extrabold text-[#111827]">${costOverview.projectedSpend.toLocaleString()}</span>
                <span className="text-[10px] font-bold text-[#2F9F77]">Within Budget</span>
              </div>
            </div>
          </div>

          {/* Token Usage Stats */}
          <div className="rounded-xl border border-[#D6F0E5] bg-[#E8F5EE]/40 p-4">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#2F9F77]">Total Token Volume</span>
            <p className="mt-1 text-xl font-extrabold text-[#111827]">
              {(costOverview.tokenUsage / 1000000).toFixed(1)}M tokens
            </p>
            <p className="mt-1 text-[10px] font-medium text-[#6B7280]">
              Cache Hit Ratio: <span className="font-bold text-[#2F9F77]">32.4%</span>
            </p>
          </div>
        </div>

        {/* Right Side: Charts Column */}
        <div className="lg:col-span-2">
          {activeTab === "spend" ? (
            <div className="h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={spendTrend}
                  margin={{ top: 10, right: 10, left: -25, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                  <XAxis dataKey="date" stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} />
                  <YAxis stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} unit="$" />
                  <Tooltip content={<CustomSpendTooltip />} />
                  <Legend verticalAlign="top" height={36} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: "11px", fontWeight: 600 }} />
                  
                  {/* Category curves */}
                  <Area type="monotone" name="Tokens" dataKey="tokens" stackId="1" stroke="#38B88A" fill="#38B88A" fillOpacity={0.15} />
                  <Area type="monotone" name="Models" dataKey="models" stackId="1" stroke="#4a8c70" fill="#4a8c70" fillOpacity={0.15} />
                  <Area type="monotone" name="Infrastructure" dataKey="infrastructure" stackId="1" stroke="#96cead" fill="#96cead" fillOpacity={0.15} />
                  <Area type="monotone" name="Voice" dataKey="voice" stackId="1" stroke="#FEF08A" fill="#FEF08A" fillOpacity={0.15} />
                  <Area type="monotone" name="Computer Use" dataKey="computerUse" stackId="1" stroke="#EF4444" fill="#EF4444" fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex h-[280px] flex-col items-center justify-center gap-6 sm:flex-row">
              <div className="h-[200px] w-[200px] shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={modelCostBreakdown}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {modelCostBreakdown.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => [`$${value}`, "Cost"]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Legends details */}
              <div className="flex flex-col gap-3">
                {modelCostBreakdown.map((item) => (
                  <div key={item.name} className="flex items-center gap-2.5">
                    <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: item.fill }} />
                    <div>
                      <p className="text-xs font-bold text-[#111827]">{item.name}</p>
                      <p className="text-[10px] font-semibold text-[#6B7280]">
                        ${item.value.toLocaleString()} Spend ({(item.value / costOverview.modelCost * 100).toFixed(0)}%)
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
