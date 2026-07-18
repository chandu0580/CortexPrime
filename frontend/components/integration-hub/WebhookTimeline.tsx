"use client";

import { motion } from "framer-motion";
import { webhookEventLogs } from "./dashboardData";
import { Code, MessageSquare, RefreshCw, AlertTriangle, FileText, Send, Zap } from "lucide-react";
import { cn } from "@/utils/cn";

export default function WebhookTimeline() {
  const getIcon = (event: string) => {
    const e = event.toLowerCase();
    if (e.includes("github")) return Code;
    if (e.includes("slack") || e.includes("teams")) return MessageSquare;
    if (e.includes("salesforce")) return FileText;
    if (e.includes("failed")) return AlertTriangle;
    if (e.includes("jira")) return Send;
    return Zap;
  };

  const getColors = (status: string) => {
    switch (status) {
      case "success":
        return {
          bg: "bg-[#E8F5EE]",
          border: "border-[#D6F0E5]",
          text: "text-[#2F9F77]",
        };
      case "failed":
        return {
          bg: "bg-red-50",
          border: "border-red-100",
          text: "text-red-600",
        };
      default:
        return {
          bg: "bg-amber-50",
          border: "border-amber-100",
          text: "text-amber-600",
        };
    }
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6">
        <h3 className="text-base font-bold text-[#111827]">
          Webhook & Event Activity
        </h3>
        <p className="mt-1 text-xs font-medium text-[#6B7280]">
          Audit log of events received or broadcasted through CortexPrime connectors.
        </p>
      </div>

      <div className="relative border-l border-[#E5E7EB] pl-6 ml-3 space-y-6">
        {webhookEventLogs.map((log, index) => {
          const Icon = getIcon(log.event);
          const color = getColors(log.status);

          return (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25, delay: index * 0.04 }}
              className="relative group animate-fade-in"
            >
              {/* Timeline Indicator Dot */}
              <span className={cn(
                "absolute -left-[38px] top-1 flex h-6 w-6 items-center justify-center rounded-full border bg-white shadow-sm transition-all duration-300 group-hover:scale-110",
                color.border
              )}>
                <Icon className={cn("h-3 w-3", color.text)} />
              </span>

              {/* Event card details */}
              <div className="rounded-xl border border-transparent p-1 transition-all duration-200 group-hover:border-[#E5E7EB] group-hover:bg-[#F8FAFC]">
                <div className="flex items-center justify-between gap-4">
                  <h4 className="text-xs font-extrabold text-[#111827]">
                    {log.event}
                  </h4>
                  <span className="text-[10px] font-bold text-[#6B7280] whitespace-nowrap">
                    {log.timestamp}
                  </span>
                </div>
                <p className="mt-1 text-[11px] font-semibold text-[#6B7280] leading-relaxed">
                  {log.description}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
