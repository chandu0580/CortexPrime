"use client";

import { liveSystemMetrics } from "./dashboardData";
import { Cpu, Layers, MoreVertical } from "lucide-react";
import StatusBadge, { HealthStatusType } from "./StatusBadge";

export default function MetricsTable() {
  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            Live System Metrics
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Review real-time transaction volumes, error rates, and response durations for core AI modules.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[#E5E7EB] pb-3 text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              <th scope="col" className="py-3.5 pl-4 pr-3">Service Name</th>
              <th scope="col" className="px-3 py-3.5 text-right">Requests/sec</th>
              <th scope="col" className="px-3 py-3.5 text-right">Latency</th>
              <th scope="col" className="px-3 py-3.5 text-right">Error Rate</th>
              <th scope="col" className="px-3 py-3.5 text-right">Availability</th>
              <th scope="col" className="px-3 py-3.5 text-right">Response Time</th>
              <th scope="col" className="px-3 py-3.5 text-center">Status</th>
              <th scope="col" className="py-3.5 pl-3 pr-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB] font-medium text-[#111827]">
            {liveSystemMetrics.map((row) => {
              return (
                <tr key={row.service} className="transition-colors hover:bg-[#F8FAFC]">
                  <td className="whitespace-nowrap py-4 pl-4 pr-3">
                    <div className="flex items-center gap-2 text-xs font-bold text-[#111827]">
                      <Cpu className="h-3.5 w-3.5 text-[#6B7280]" />
                      <span>{row.service}</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right font-semibold text-[#111827]">
                    {row.requestsPerSec.toLocaleString()} req/s
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right text-xs text-[#6B7280]">
                    {row.latency}
                  </td>
                  <td className={`whitespace-nowrap px-3 py-4 text-right text-xs font-bold ${
                    parseFloat(row.errorRate) > 1 ? "text-[#B91C1C]" : "text-[#6B7280]"
                  }`}>
                    {row.errorRate}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right text-xs font-semibold text-[#2F9F77]">
                    {row.availability}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right text-xs text-[#6B7280]">
                    {row.responseTime}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-center">
                    <StatusBadge status={row.status as HealthStatusType}>{row.status}</StatusBadge>
                  </td>
                  <td className="whitespace-nowrap py-4 pl-3 pr-4 text-center">
                    <button className="rounded-lg p-1 text-[#6B7280] hover:bg-[#F3F4F6] hover:text-[#111827]">
                      <MoreVertical className="h-4 w-4" />
                    </button>
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
