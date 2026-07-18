"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { monthlyComplianceTrend, riskDistribution, violationCategories } from "./dashboardData";
import { TrendingUp, ShieldAlert, AlertTriangle } from "lucide-react";

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
const BarChart = dynamic(
  () => import("recharts").then((mod) => mod.BarChart),
  { ssr: false }
);
const Bar = dynamic(
  () => import("recharts").then((mod) => mod.Bar),
  { ssr: false }
);

export default function ComplianceChart() {
  const [activeTab, setActiveTab] = useState<"trend" | "risk" | "violations">("trend");

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      {/* Header and selector tabs */}
      <div className="flex flex-col gap-4 border-b border-[#F3F4F6] pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            Compliance & Safety Analytics
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Monitor system-wide policy safety compliance rates, threat breakdowns, and risk distributions.
          </p>
        </div>

        {/* Tab Controls */}
        <div className="flex items-center gap-1 rounded-xl bg-[#F8FAFC] p-1 border border-[#E5E7EB]">
          <button
            onClick={() => setActiveTab("trend")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all ${
              activeTab === "trend"
                ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                : "text-[#6B7280] hover:text-[#111827]"
            }`}
          >
            <TrendingUp className="h-3.5 w-3.5" />
            <span>Compliance Trend</span>
          </button>
          <button
            onClick={() => setActiveTab("risk")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all ${
              activeTab === "risk"
                ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                : "text-[#6B7280] hover:text-[#111827]"
            }`}
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            <span>Risk Spread</span>
          </button>
          <button
            onClick={() => setActiveTab("violations")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all ${
              activeTab === "violations"
                ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                : "text-[#6B7280] hover:text-[#111827]"
            }`}
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Violations Category</span>
          </button>
        </div>
      </div>

      {/* Charts section */}
      <div className="mt-6 h-[300px] w-full">
        {activeTab === "trend" ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={monthlyComplianceTrend}
              margin={{ top: 10, right: 10, left: -25, bottom: 0 }}
            >
              <defs>
                <linearGradient id="colorComplianceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#38B88A" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#38B88A" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
              <XAxis dataKey="date" stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} />
              <YAxis stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} unit="%" domain={[95, 100]} />
              <Tooltip formatter={(value) => [`${value}%`, "Compliance Score"]} />
              <Area type="monotone" name="Compliance" dataKey="compliance" stroke="#38B88A" strokeWidth={2.5} fillOpacity={1} fill="url(#colorComplianceGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : activeTab === "risk" ? (
          <div className="flex h-full flex-col items-center justify-center gap-6 sm:flex-row">
            <div className="h-[200px] w-[200px] shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={riskDistribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={70}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {riskDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => [value, "Risks"]} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Legends */}
            <div className="flex flex-col gap-3">
              {riskDistribution.map((item) => (
                <div key={item.name} className="flex items-center gap-2.5">
                  <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: item.fill }} />
                  <div>
                    <p className="text-xs font-bold text-[#111827]">{item.name}</p>
                    <p className="text-[10px] font-semibold text-[#6B7280]">
                      {item.value} actions flagged
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={violationCategories}
              margin={{ top: 10, right: 10, left: -25, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
              <XAxis dataKey="category" stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} />
              <YAxis stroke="#6B7280" fontSize={11} fontWeight={600} tickLine={false} axisLine={false} />
              <Tooltip formatter={(value) => [value, "Occurrences"]} />
              <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                {violationCategories.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
