"use client";

import { motion } from "framer-motion";
import { dependenciesStatus, DependencyStatusData } from "./dashboardData";
import { variants } from "@/lib/motion-tokens";
import { Database, Link2, Clock, Cpu } from "lucide-react";
import StatusBadge, { HealthStatusType } from "./StatusBadge";

export default function DependencyCard() {
  const getIcon = (name: string) => {
    switch (name.toLowerCase()) {
      case "postgresql":
      case "redis":
      case "rabbitmq":
      case "aws s3 storage":
        return Database;
      default:
        return Cpu;
    }
  };

  const getStyles = (health: string) => {
    switch (health) {
      case "healthy":
        return "border-green-200 hover:border-[#38B88A]/40";
      case "degraded":
        return "border-amber-200 hover:border-amber-400/40";
      default:
        return "border-red-200 hover:border-red-400/40";
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
      {dependenciesStatus.map((dep, index) => {
        const Icon = getIcon(dep.name);
        const style = getStyles(dep.health);

        return (
          <motion.div
            key={dep.name}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.04 }}
            whileHover={variants.cardHover}
            className={`flex flex-col justify-between rounded-[20px] border bg-white p-4 shadow-[0_8px_30px_rgb(0,0,0,0.01)] transition-all duration-200 ${style}`}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-[#F3F4F6] pb-2.5">
              <span className="text-xs font-extrabold text-[#111827] truncate pr-2">
                {dep.name}
              </span>
              <StatusBadge status={dep.health as HealthStatusType}>
                {dep.health}
              </StatusBadge>
            </div>

            {/* Info and statistics */}
            <div className="mt-3 flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="inline-flex items-center gap-1 font-semibold text-[#6B7280]">
                  <Link2 className="h-3.5 w-3.5" />
                  Connection
                </span>
                <span className="font-extrabold text-[#2F9F77]">{dep.connection}</span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="inline-flex items-center gap-1 font-semibold text-[#6B7280]">
                  <Clock className="h-3.5 w-3.5" />
                  Ping Latency
                </span>
                <span className="font-bold text-[#111827]">{dep.latency}</span>
              </div>
            </div>

            {/* Details footer */}
            <div className="mt-3 flex items-center justify-between border-t border-[#F3F4F6] pt-2 text-[9px] font-semibold text-[#6B7280]">
              <span>Ver: {dep.version}</span>
              <span>Checked {dep.lastChecked}</span>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
