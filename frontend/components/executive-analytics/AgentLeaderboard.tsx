"use client";

import { motion } from "framer-motion";
import { workforcePerformance } from "./mockData";
import { Award, Zap, Heart, ShieldCheck } from "lucide-react";
import StatusBadge from "./StatusBadge";

export default function AgentLeaderboard() {
  // Sort agents by completed missions or success rate to determine top performers
  const sortedAgents = [...workforcePerformance].sort((a, b) => b.completedMissions - a.completedMissions);

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            AI Workforce Performance
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Review core operational stats, resource allocation, and overall agent execution health.
          </p>
        </div>
        <div className="inline-flex items-center gap-1.5 rounded-xl border border-[#E5E7EB] bg-[#F8FAFC] px-3.5 py-1.5 text-xs font-bold text-[#111827]">
          <ShieldCheck className="h-3.5 w-3.5 text-[#38B88A]" />
          <span>All Agents Operational</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[#E5E7EB] pb-3 text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              <th scope="col" className="py-3.5 pl-4 pr-3">Rank & Agent</th>
              <th scope="col" className="px-3 py-3.5">Role</th>
              <th scope="col" className="px-3 py-3.5 text-right">Missions Completed</th>
              <th scope="col" className="px-3 py-3.5 text-right">Success Rate</th>
              <th scope="col" className="px-3 py-3.5 text-right">Avg Runtime</th>
              <th scope="col" className="px-3 py-3.5 text-right">Avg Latency</th>
              <th scope="col" className="px-3 py-3.5">Resource Usage</th>
              <th scope="col" className="px-3 py-3.5 text-right">Health Score</th>
              <th scope="col" className="py-3.5 pl-3 pr-4 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB] font-medium text-[#111827]">
            {sortedAgents.map((agent, index) => {
              const isTopThree = index < 3;
              
              return (
                <tr
                  key={agent.agent}
                  className="transition-colors hover:bg-[#F8FAFC]"
                >
                  <td className="whitespace-nowrap py-4 pl-4 pr-3">
                    <div className="flex items-center gap-3">
                      <span className="flex h-5 w-5 items-center justify-center rounded-md bg-[#F3F4F6] text-[10px] font-extrabold text-[#6B7280]">
                        {index + 1}
                      </span>
                      <div className="flex flex-col">
                        <span className="font-bold text-[#111827] flex items-center gap-1.5">
                          {agent.agent}
                          {isTopThree && (
                            <span title="Top Performing Agent">
                              <Award className="h-3.5 w-3.5 text-[#38B88A]" />
                            </span>
                          )}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-xs font-semibold text-[#6B7280]">
                    {agent.role}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right font-semibold text-[#111827]">
                    {agent.completedMissions.toLocaleString()}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right">
                    <span className="inline-flex items-center gap-1 font-bold text-[#2F9F77]">
                      {agent.successRate}%
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right text-xs text-[#6B7280]">
                    {agent.avgRuntime}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right text-xs text-[#6B7280]">
                    {agent.avgLatency}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-xs">
                    <span className={`inline-flex items-center rounded-lg px-2.5 py-0.5 font-bold ${
                      agent.resourceUsage.includes("High")
                        ? "bg-[#FEF2F2] text-[#B91C1C]"
                        : agent.resourceUsage.includes("Medium")
                        ? "bg-[#FFFBEB] text-[#D97706]"
                        : "bg-[#F0FDF4] text-[#15803D]"
                    }`}>
                      {agent.resourceUsage}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Heart className="h-3 w-3 fill-[#38B88A] text-[#38B88A]" />
                      <span className="font-extrabold text-[#111827]">{agent.healthScore}%</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap py-4 pl-3 pr-4 text-center">
                    <StatusBadge status={agent.status === "active" ? "success" : "neutral"}>
                      {agent.status}
                    </StatusBadge>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
