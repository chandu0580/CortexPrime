"use client";

import { motion } from "framer-motion";
import { servicesHealthData, ServiceHealthData } from "./mockData";
import { variants } from "@/lib/motion-tokens";
import { Cpu, Clock, Layers, ShieldCheck } from "lucide-react";
import StatusBadge, { HealthStatusType } from "./StatusBadge";

export default function ServiceCard() {
  const getStyles = (status: string) => {
    switch (status) {
      case "healthy":
        return {
          border: "border-green-200 hover:border-[#38B88A]/40",
          indicator: "bg-[#38B88A]",
        };
      case "warning":
        return {
          border: "border-amber-200 hover:border-amber-400/40",
          indicator: "bg-amber-500",
        };
      case "critical":
        return {
          border: "border-red-200 hover:border-red-400/40",
          indicator: "bg-red-500",
        };
      default:
        return {
          border: "border-gray-200 hover:border-gray-400/40",
          indicator: "bg-gray-400",
        };
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
      {servicesHealthData.map((service, index) => {
        const styles = getStyles(service.status);

        return (
          <motion.div
            key={service.name}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.04 }}
            whileHover={variants.cardHover}
            className={`flex flex-col justify-between rounded-[20px] border bg-white p-4 shadow-[0_8px_30px_rgb(0,0,0,0.01)] transition-all duration-200 ${styles.border}`}
          >
            {/* Top row */}
            <div className="flex items-center justify-between border-b border-[#F3F4F6] pb-2.5">
              <span className="text-xs font-extrabold text-[#111827] truncate pr-2">
                {service.name}
              </span>
              <StatusBadge status={service.status as HealthStatusType}>
                {service.status}
              </StatusBadge>
            </div>

            {/* Middle metrics row */}
            <div className="mt-3 flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-[9px] font-bold uppercase tracking-wider text-[#6B7280]">Uptime</span>
                <span className="text-xs font-extrabold text-[#111827] mt-0.5">{service.uptime}</span>
              </div>

              <div className="flex flex-col text-right">
                <span className="text-[9px] font-bold uppercase tracking-wider text-[#6B7280]">Latency</span>
                <span className="text-xs font-bold text-[#111827] mt-0.5">{service.latency}</span>
              </div>
            </div>

            {/* Bottom details */}
            <div className="mt-3 flex items-center justify-between border-t border-[#F3F4F6] pt-2 text-[9px] font-semibold text-[#6B7280]">
              <span>Version: {service.version}</span>
              <div className="flex items-center gap-1">
                <span className={`h-1.5 w-1.5 rounded-full ${styles.indicator}`} />
                <span className="capitalize">{service.status}</span>
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
