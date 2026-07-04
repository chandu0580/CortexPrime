"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { approvalRequests, ApprovalRequest } from "./mockData";
import { Check, X, ShieldAlert, Cpu, User } from "lucide-react";
import StatusBadge from "./StatusBadge";

export default function ApprovalTable() {
  const [requests, setRequests] = useState<ApprovalRequest[]>(approvalRequests);
  const [actionHistory, setActionHistory] = useState<Record<string, "approved" | "rejected">>({});

  const handleApprove = (id: string) => {
    setActionHistory(prev => ({ ...prev, [id]: "approved" }));
    setTimeout(() => {
      setRequests(prev => prev.filter(r => r.id !== id));
    }, 800);
  };

  const handleReject = (id: string) => {
    setActionHistory(prev => ({ ...prev, [id]: "rejected" }));
    setTimeout(() => {
      setRequests(prev => prev.filter(r => r.id !== id));
    }, 800);
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            Pending Approvals Queue
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Review human-in-the-loop overrides and sensitive data access authorization requests.
          </p>
        </div>
        <div className="inline-flex items-center gap-1.5 rounded-xl bg-[#F8FAFC] border border-[#E5E7EB] px-3.5 py-1.5 text-xs font-bold text-[#111827]">
          <span>{requests.length} Requests Pending</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[#E5E7EB] pb-3 text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              <th scope="col" className="py-3.5 pl-4 pr-3">Operation / Request</th>
              <th scope="col" className="px-3 py-3.5">AI Agent</th>
              <th scope="col" className="px-3 py-3.5">Requested By</th>
              <th scope="col" className="px-3 py-3.5 text-center">Risk Level</th>
              <th scope="col" className="px-3 py-3.5">Requested Time</th>
              <th scope="col" className="py-3.5 pl-3 pr-4 text-center">Decision</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB] font-medium text-[#111827]">
            <AnimatePresence mode="popLayout">
              {requests.map((req) => {
                const historyStatus = actionHistory[req.id];
                
                return (
                  <motion.tr
                    key={req.id}
                    layout
                    exit={{ opacity: 0, x: historyStatus === "approved" ? 50 : -50, backgroundColor: historyStatus === "approved" ? "rgba(56,184,138,0.05)" : "rgba(239,68,68,0.05)" }}
                    transition={{ duration: 0.3 }}
                    className="transition-colors hover:bg-[#F8FAFC]"
                  >
                    <td className="py-4 pl-4 pr-3">
                      <div className="flex flex-col">
                        <span className="font-bold text-[#111827]">{req.request}</span>
                        <span className="text-[10px] text-[#6B7280] mt-0.5">Request ID: {req.id}</span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-4">
                      <div className="flex items-center gap-1 text-xs text-[#111827]">
                        <Cpu className="h-3.5 w-3.5 text-[#6B7280]" />
                        <span>{req.agent}</span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-4">
                      <div className="flex items-center gap-1 text-xs text-[#111827]">
                        <User className="h-3.5 w-3.5 text-[#6B7280]" />
                        <span>{req.requestedBy}</span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-4 text-center">
                      <StatusBadge status={req.riskLevel}>{req.riskLevel}</StatusBadge>
                    </td>
                    <td className="whitespace-nowrap px-3 py-4 text-xs text-[#6B7280]">
                      {req.requestedTime}
                    </td>
                    <td className="whitespace-nowrap py-4 pl-3 pr-4 text-center">
                      {historyStatus ? (
                        <div className="flex items-center justify-center">
                          <StatusBadge status={historyStatus === "approved" ? "approved" : "rejected"}>
                            {historyStatus === "approved" ? "Approved" : "Rejected"}
                          </StatusBadge>
                        </div>
                      ) : (
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            onClick={() => handleApprove(req.id)}
                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[#D6F0E5] bg-[#E8F5EE] text-[#2F9F77] hover:bg-[#D6F0E5] active:scale-[0.92]"
                            aria-label="Approve request"
                            title="Approve"
                          >
                            <Check className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleReject(req.id)}
                            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[#FCA5A5] bg-[#FEE2E2] text-[#B91C1C] hover:bg-[#FCA5A5] active:scale-[0.92]"
                            aria-label="Reject request"
                            title="Reject"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </td>
                  </motion.tr>
                );
              })}
            </AnimatePresence>

            {requests.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-xs font-semibold text-[#6B7280]">
                  No pending approvals. Queue is clear!
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
