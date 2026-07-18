"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { syncActivity, SyncActivityRow } from "./dashboardData";
import { RefreshCw, Play, Pause, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import StatusBadge, { IntegrationStatusType } from "./StatusBadge";

export default function SyncTable() {
  const [syncRows, setSyncRows] = useState<SyncActivityRow[]>(syncActivity);

  const handleAction = (id: string, currentStatus: string) => {
    // If the sync is running, we can pause it (Queued). If failed, we retry (Running)
    setSyncRows(prev =>
      prev.map(row => {
        if (row.id === id) {
          if (currentStatus === "Running") {
            return { ...row, status: "Queued", duration: "Paused" };
          } else if (currentStatus === "Failed" || currentStatus === "Retrying" || currentStatus === "Queued") {
            return { ...row, status: "Running", lastSync: "Running...", duration: "Calculating..." };
          } else if (currentStatus === "Completed") {
            // Trigger a re-run
            return { ...row, status: "Running", lastSync: "Running...", duration: "Calculating...", recordsProcessed: 0 };
          }
        }
        return row;
      })
    );
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "Running":
        return <RefreshCw className="h-3.5 w-3.5 animate-spin text-blue-600" />;
      case "Completed":
        return <CheckCircle className="h-3.5 w-3.5 text-[#38B88A]" />;
      case "Failed":
        return <AlertTriangle className="h-3.5 w-3.5 text-red-600" />;
      case "Queued":
        return <Clock className="h-3.5 w-3.5 text-gray-500" />;
      default:
        return <RefreshCw className="h-3.5 w-3.5 text-amber-500" />;
    }
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            Synchronization Activity
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Monitor current integration sync flows, processing durations, and records transfer history.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[#E5E7EB] pb-3 text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              <th scope="col" className="py-3.5 pl-4 pr-3">Integration</th>
              <th scope="col" className="px-3 py-3.5 text-right">Last Sync</th>
              <th scope="col" className="px-3 py-3.5 text-right">Records Processed</th>
              <th scope="col" className="px-3 py-3.5 text-right">Duration</th>
              <th scope="col" className="px-3 py-3.5 text-center">Status</th>
              <th scope="col" className="px-3 py-3.5 text-center">Triggered By</th>
              <th scope="col" className="py-3.5 pl-3 pr-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB] font-medium text-[#111827]">
            <AnimatePresence initial={false}>
              {syncRows.map((row) => (
                <motion.tr
                  key={row.id}
                  layoutId={row.id}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="transition-colors hover:bg-[#F8FAFC]"
                >
                  {/* Integration Name */}
                  <td className="whitespace-nowrap py-4 pl-4 pr-3">
                    <div className="flex items-center gap-2.5 text-xs font-bold text-[#111827]">
                      {getStatusIcon(row.status)}
                      <span>{row.integration}</span>
                    </div>
                  </td>

                  {/* Last Sync */}
                  <td className="whitespace-nowrap px-3 py-4 text-right text-xs text-[#6B7280]">
                    {row.lastSync}
                  </td>

                  {/* Records Processed */}
                  <td className="whitespace-nowrap px-3 py-4 text-right text-xs font-bold text-[#111827]">
                    {row.recordsProcessed > 0 ? row.recordsProcessed.toLocaleString() : "—"}
                  </td>

                  {/* Duration */}
                  <td className="whitespace-nowrap px-3 py-4 text-right text-xs text-[#6B7280]">
                    {row.duration}
                  </td>

                  {/* Status */}
                  <td className="whitespace-nowrap px-3 py-4 text-center">
                    <StatusBadge status={row.status as IntegrationStatusType}>{row.status}</StatusBadge>
                  </td>

                  {/* Triggered By */}
                  <td className="whitespace-nowrap px-3 py-4 text-center text-xs text-[#6B7280] font-semibold">
                    {row.triggeredBy}
                  </td>

                  {/* Actions */}
                  <td className="whitespace-nowrap py-4 pl-3 pr-4 text-center">
                    <button
                      onClick={() => handleAction(row.id, row.status)}
                      className="rounded-lg p-1.5 text-[#6B7280] hover:bg-[#F3F4F6] hover:text-[#111827] transition-all"
                      title={row.status === "Running" ? "Pause synchronization" : "Trigger synchronization"}
                    >
                      {row.status === "Running" ? (
                        <Pause className="h-4 w-4" />
                      ) : (
                        <Play className="h-4 w-4 text-[#38B88A]" />
                      )}
                    </button>
                  </td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </div>
  );
}
