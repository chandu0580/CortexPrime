"use client";

import { useState } from "react";
import { auditHistory, AuditHistoryEntry } from "./mockData";
import { HelpCircle, ChevronDown, RefreshCw, FileText, Filter } from "lucide-react";
import StatusBadge from "./StatusBadge";

export default function AuditTable() {
  const [logs, setLogs] = useState<AuditHistoryEntry[]>(auditHistory);
  const [severityFilter, setSeverityFilter] = useState("All Severities");
  const [outcomeFilter, setOutcomeFilter] = useState("All Outcomes");

  const severities = ["All Severities", "low", "medium", "high", "critical"];
  const outcomes = ["All Outcomes", "passed", "blocked", "approved", "rejected", "reviewed", "updated"];

  const filteredLogs = logs.filter(log => {
    const matchesSeverity = severityFilter === "All Severities" || log.severity === severityFilter;
    const matchesOutcome = outcomeFilter === "All Outcomes" || log.outcome === outcomeFilter;
    return matchesSeverity && matchesOutcome;
  });

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            Durable Audit Trail & History
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Immutable record of security triggers, constraint updates, threat reviews, and operational passes.
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Severity filter */}
          <div className="relative">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="appearance-none rounded-xl border border-[#E5E7EB] bg-white pl-3.5 pr-8 py-2 text-xs font-semibold text-[#111827] shadow-sm outline-none cursor-pointer hover:bg-[#F9FAFB]"
            >
              {severities.map(sev => (
                <option key={sev} value={sev}>{sev === "All Severities" ? sev : `${sev.charAt(0).toUpperCase() + sev.slice(1)} Severity`}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-[#6B7280] pointer-events-none" />
          </div>

          {/* Outcome filter */}
          <div className="relative">
            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value)}
              className="appearance-none rounded-xl border border-[#E5E7EB] bg-white pl-3.5 pr-8 py-2 text-xs font-semibold text-[#111827] shadow-sm outline-none cursor-pointer hover:bg-[#F9FAFB]"
            >
              {outcomes.map(out => (
                <option key={out} value={out}>{out === "All Outcomes" ? out : `${out.charAt(0).toUpperCase() + out.slice(1)} Outcome`}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-[#6B7280] pointer-events-none" />
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[#E5E7EB] pb-3 text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              <th scope="col" className="py-3 pl-4 pr-3">Audit ID</th>
              <th scope="col" className="px-3 py-3">Event Action</th>
              <th scope="col" className="px-3 py-3">AI Agent</th>
              <th scope="col" className="px-3 py-3">Actor / User</th>
              <th scope="col" className="px-3 py-3">Timestamp</th>
              <th scope="col" className="px-3 py-3 text-center">Outcome</th>
              <th scope="col" className="px-3 py-3 text-center">Severity</th>
              <th scope="col" className="py-3 pl-3 pr-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB] font-medium text-[#111827]">
            {filteredLogs.map((log) => {
              return (
                <tr key={log.id} className="transition-colors hover:bg-[#F8FAFC]">
                  <td className="whitespace-nowrap py-4 pl-4 pr-3 text-xs font-mono font-bold text-[#111827]">
                    {log.id}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-xs font-bold text-[#111827]">
                    {log.event}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-xs text-[#6B7280]">
                    {log.agent}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-xs text-[#111827]">
                    {log.user}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-xs text-[#6B7280]">
                    {log.timestamp}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-center">
                    <StatusBadge status={log.outcome}>{log.outcome}</StatusBadge>
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-center">
                    <StatusBadge status={log.severity}>{log.severity}</StatusBadge>
                  </td>
                  <td className="whitespace-nowrap py-4 pl-3 pr-4 text-center">
                    <button className="inline-flex items-center gap-1 rounded-lg border border-[#E5E7EB] bg-white px-2.5 py-1 text-[10px] font-bold text-[#374151] hover:bg-[#F9FAFB] active:scale-[0.98]">
                      <FileText className="h-3 w-3" />
                      <span>Details</span>
                    </button>
                  </td>
                </tr>
              );
            })}

            {filteredLogs.length === 0 && (
              <tr>
                <td colSpan={8} className="py-8 text-center text-xs font-semibold text-[#6B7280]">
                  No audit logs found matching criteria.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
