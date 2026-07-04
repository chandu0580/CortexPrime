"use client";

import { motion } from "framer-motion";
import { operationalAlerts } from "./mockData";
import { ShieldAlert, AlertTriangle, EyeOff, Lock, CheckCircle2, RefreshCw } from "lucide-react";

export default function AlertTimeline() {
  const getIcon = (severity: string) => {
    switch (severity) {
      case "critical":
        return ShieldAlert;
      case "warning":
        return AlertTriangle;
      case "resolved":
        return CheckCircle2;
      default:
        return RefreshCw;
    }
  };

  const getColors = (severity: string) => {
    switch (severity) {
      case "critical":
        return {
          bg: "bg-red-50",
          border: "border-red-100",
          text: "text-red-600",
        };
      case "warning":
        return {
          bg: "bg-amber-50",
          border: "border-amber-100",
          text: "text-amber-600",
        };
      case "resolved":
        return {
          bg: "bg-[#E8F5EE]",
          border: "border-[#D6F0E5]",
          text: "text-[#2F9F77]",
        };
      default:
        return {
          bg: "bg-blue-50",
          border: "border-blue-100",
          text: "text-blue-600",
        };
    }
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6">
        <h3 className="text-base font-bold text-[#111827]">
          Live Operational Alerts
        </h3>
        <p className="mt-1 text-xs font-medium text-[#6B7280]">
          Active incidents, warnings, auto-heals, and resolution events timeline.
        </p>
      </div>

      <div className="relative border-l border-[#E5E7EB] pl-6 ml-3 space-y-6">
        {operationalAlerts.map((alert, index) => {
          const Icon = getIcon(alert.severity);
          const color = getColors(alert.severity);

          return (
            <motion.div
              key={alert.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25, delay: index * 0.04 }}
              className="relative group"
            >
              {/* Timeline dot */}
              <span className={`absolute -left-[38px] top-1 flex h-6 w-6 items-center justify-center rounded-full border bg-white shadow-sm transition-all duration-300 group-hover:scale-110 ${color.border}`}>
                <Icon className={`h-3 w-3 ${color.text}`} />
              </span>

              {/* Card wrapper */}
              <div className="rounded-xl border border-transparent p-1 transition-all duration-200 group-hover:border-[#E5E7EB] group-hover:bg-[#F8FAFC]">
                <div className="flex items-center justify-between gap-4">
                  <h4 className="text-xs font-extrabold text-[#111827]">
                    {alert.title}
                  </h4>
                  <span className="text-[10px] font-bold text-[#6B7280] whitespace-nowrap">
                    {alert.timestamp}
                  </span>
                </div>
                <p className="mt-1 text-[11px] font-semibold text-[#6B7280] leading-relaxed">
                  {alert.description}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
