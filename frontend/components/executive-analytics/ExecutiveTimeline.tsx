"use client";

import { motion } from "framer-motion";
import { timelineEvents } from "./dashboardData";
import { Zap, Cpu, ShieldAlert, Award, FileSpreadsheet, Activity } from "lucide-react";

export default function ExecutiveTimeline() {
  const getIcon = (type: string) => {
    switch (type) {
      case "milestone":
        return Award;
      case "agent":
        return Cpu;
      case "report":
        return FileSpreadsheet;
      case "policy":
        return ShieldAlert;
      case "governance":
        return Activity;
      default:
        return Zap;
    }
  };

  const getColors = (type: string) => {
    switch (type) {
      case "milestone":
        return {
          bg: "bg-[#E8F5EE]",
          border: "border-[#D6F0E5]",
          text: "text-[#2F9F77]",
        };
      case "agent":
        return {
          bg: "bg-blue-50",
          border: "border-blue-100",
          text: "text-blue-600",
        };
      case "policy":
        return {
          bg: "bg-red-50",
          border: "border-red-100",
          text: "text-red-600",
        };
      case "governance":
        return {
          bg: "bg-purple-50",
          border: "border-purple-100",
          text: "text-purple-600",
        };
      default:
        return {
          bg: "bg-gray-50",
          border: "border-gray-100",
          text: "text-gray-600",
        };
    }
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6">
        <h3 className="text-base font-bold text-[#111827]">
          Executive Audit & Timeline
        </h3>
        <p className="mt-1 text-xs font-medium text-[#6B7280]">
          Real-time updates regarding agent updates, department milestones, policy constraints, and audit reports.
        </p>
      </div>

      <div className="relative border-l border-[#E5E7EB] pl-6 ml-3 space-y-6">
        {timelineEvents.map((event, index) => {
          const Icon = getIcon(event.type);
          const color = getColors(event.type);

          return (
            <motion.div
              key={event.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25, delay: index * 0.04 }}
              className="relative group"
            >
              {/* Vertical timeline circle wrapper with icon */}
              <span className={`absolute -left-[38px] top-1 flex h-6 w-6 items-center justify-center rounded-full border bg-white shadow-sm transition-all duration-300 group-hover:scale-110 ${color.border}`}>
                <Icon className={`h-3 w-3 ${color.text}`} />
              </span>

              {/* Event card details */}
              <div className="rounded-xl border border-transparent p-1 transition-all duration-200 group-hover:border-[#E5E7EB] group-hover:bg-[#F8FAFC]">
                <div className="flex items-center justify-between gap-4">
                  <h4 className="text-xs font-extrabold text-[#111827]">
                    {event.title}
                  </h4>
                  <span className="text-[10px] font-bold text-[#6B7280] whitespace-nowrap">
                    {event.timestamp}
                  </span>
                </div>
                <p className="mt-1 text-[11px] font-semibold text-[#6B7280] leading-relaxed">
                  {event.description}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
