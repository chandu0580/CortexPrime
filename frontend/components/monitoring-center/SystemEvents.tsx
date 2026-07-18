"use client";

import { motion } from "framer-motion";
import { systemActivityEvents } from "./dashboardData";
import { Rocket, RefreshCw, HardDrive, Cpu, Heart, CheckCircle2 } from "lucide-react";
import { cn } from "@/utils/cn";
import { variants } from "@/lib/motion-tokens";

export default function SystemEvents() {
  const getIcon = (type: string) => {
    switch (type) {
      case "deployment":
        return Rocket;
      case "restart":
        return RefreshCw;
      case "scale":
        return Cpu;
      case "backup":
        return HardDrive;
      case "healthcheck":
        return Heart;
      default:
        return CheckCircle2;
    }
  };

  const getColors = (type: string) => {
    switch (type) {
      case "deployment":
        return {
          bg: "bg-[#EFF6FF]",
          border: "border-[#BFDBFE]",
          text: "text-blue-600",
        };
      case "restart":
        return {
          bg: "bg-amber-50",
          border: "border-amber-100",
          text: "text-amber-600",
        };
      case "scale":
        return {
          bg: "bg-purple-50",
          border: "border-purple-100",
          text: "text-purple-600",
        };
      case "backup":
        return {
          bg: "bg-indigo-50",
          border: "border-indigo-100",
          text: "text-indigo-600",
        };
      case "healthcheck":
      default:
        return {
          bg: "bg-[#E8F5EE]",
          border: "border-[#D6F0E5]",
          text: "text-[#2F9F77]",
        };
    }
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6">
        <h3 className="text-base font-bold text-[#111827]">
          Recent System Events
        </h3>
        <p className="mt-1 text-xs font-medium text-[#6B7280]">
          System deployments, restarts, automated scaling, and storage backups log.
        </p>
      </div>

      <div className="relative border-l border-[#E5E7EB] pl-6 ml-3 space-y-6">
        {systemActivityEvents.map((evt, index) => {
          const Icon = getIcon(evt.type);
          const color = getColors(evt.type);

          return (
            <motion.div
              key={evt.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25, delay: index * 0.04 }}
              className="relative group"
            >
              {/* Timeline dot */}
              <span className={cn(
                "absolute -left-[38px] top-1 flex h-6 w-6 items-center justify-center rounded-full border bg-white shadow-sm transition-all duration-300 group-hover:scale-110",
                color.border
              )}>
                <Icon className={cn("h-3 w-3", color.text)} />
              </span>

              {/* Event card wrapper */}
              <div className="rounded-xl border border-transparent p-1 transition-all duration-200 group-hover:border-[#E5E7EB] group-hover:bg-[#F8FAFC]">
                <div className="flex items-center justify-between gap-4">
                  <h4 className="text-xs font-extrabold text-[#111827]">
                    {evt.event}
                  </h4>
                  <span className="text-[10px] font-bold text-[#6B7280] whitespace-nowrap">
                    {evt.timestamp}
                  </span>
                </div>
                <p className="mt-1 text-[11px] font-semibold text-[#6B7280] leading-relaxed">
                  {evt.description}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
