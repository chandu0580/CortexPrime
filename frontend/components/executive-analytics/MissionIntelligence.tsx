"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { missionTypes, missionStats, missionPriorityData } from "./dashboardData";
import { Award, ShieldAlert, BarChart3, PieChartIcon } from "lucide-react";

// Dynamically import Recharts to avoid SSR hydration mismatches
const ResponsiveContainer = dynamic(
  () => import("recharts").then((mod) => mod.ResponsiveContainer),
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
const Tooltip = dynamic(
  () => import("recharts").then((mod) => mod.Tooltip),
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
const XAxis = dynamic(
  () => import("recharts").then((mod) => mod.XAxis),
  { ssr: false }
);
const YAxis = dynamic(
  () => import("recharts").then((mod) => mod.YAxis),
  { ssr: false }
);
const CartesianGrid = dynamic(
  () => import("recharts").then((mod) => mod.CartesianGrid),
  { ssr: false }
);

export default function MissionIntelligence() {
  const [activeTab, setActiveTab] = useState<"distribution" | "priority">("distribution");

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      {/* Header */}
      <div className="flex flex-col gap-4 border-b border-[#F3F4F6] pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            Mission Intelligence & Category Analysis
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Review mission categorization, completion vs failures rates, and duration profiles.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center gap-1 rounded-xl bg-[#F8FAFC] p-1 border border-[#E5E7EB]">
          <button
            onClick={() => setActiveTab("distribution")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all ${
              activeTab === "distribution"
                ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                : "text-[#6B7280] hover:text-[#111827]"
            }`}
          >
            <PieChartIcon className="h-3.5 w-3.5" />
            <span>Mission Types</span>
          </button>
          <button
            onClick={() => setActiveTab("priority")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-bold transition-all ${
              activeTab === "priority"
                ? "bg-white text-[#111827] shadow-[0_2px_8px_rgba(0,0,0,0.04)]"
                : "text-[#6B7280] hover:text-[#111827]"
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            <span>Priority Spread</span>
          </button>
        </div>
      </div>

      {/* Content grid */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Side: Pie charts */}
        <div className="flex flex-col items-center justify-center border-[#F3F4F6] lg:border-r lg:pr-6">
          {activeTab === "distribution" ? (
            <div className="flex flex-col items-center">
              <div className="h-[180px] w-[180px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={missionTypes}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={70}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {missionTypes.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => [value, "Missions"]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              
              {/* Legend */}
              <div className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-1.5 text-[10px] font-bold text-[#6B7280]">
                {missionTypes.map((item) => (
                  <div key={item.name} className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.fill }} />
                    <span>{item.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <div className="h-[180px] w-[180px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={missionPriorityData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={70}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {missionPriorityData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => [value, "Missions"]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Legend */}
              <div className="mt-4 flex flex-wrap justify-center gap-x-4 gap-y-1.5 text-[10px] font-bold text-[#6B7280]">
                {missionPriorityData.map((item) => (
                  <div key={item.name} className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.fill }} />
                    <span>{item.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Side: Detailed stats table / list */}
        <div className="lg:col-span-2 overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs font-semibold text-[#6B7280]">
            <thead>
              <tr className="border-b border-[#E5E7EB] pb-2 font-bold uppercase text-[#6B7280]">
                <th scope="col" className="py-2 pr-3">Mission Category</th>
                <th scope="col" className="px-3 py-2 text-right">Volume</th>
                <th scope="col" className="px-3 py-2 text-right">Success</th>
                <th scope="col" className="px-3 py-2 text-right">Failures</th>
                <th scope="col" className="px-3 py-2 text-right">Avg Duration</th>
                <th scope="col" className="py-2 pl-3 text-center">Priority</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB] text-[#111827]">
              {missionStats.map((stat) => (
                <tr key={stat.type} className="hover:bg-[#F8FAFC]">
                  <td className="whitespace-nowrap py-3 pr-3 font-bold text-[#111827]">
                    {stat.type}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-right">
                    {stat.count.toLocaleString()}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-right text-[#2F9F77] font-bold">
                    {stat.successCount.toLocaleString()}
                  </td>
                  <td className={`whitespace-nowrap px-3 py-3 text-right font-bold ${stat.failureCount > 10 ? "text-[#B91C1C]" : "text-[#6B7280]"}`}>
                    {stat.failureCount}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-right">
                    {stat.avgDuration}s
                  </td>
                  <td className="whitespace-nowrap py-3 pl-3 text-center">
                    <span className={`inline-block rounded-md px-2 py-0.5 text-[9px] font-extrabold uppercase ${
                      stat.priority === "high"
                        ? "bg-[#FEF2F2] text-[#B91C1C]"
                        : stat.priority === "medium"
                        ? "bg-[#FFFBEB] text-[#D97706]"
                        : "bg-[#F3F4F6] text-[#6B7280]"
                    }`}>
                      {stat.priority}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
