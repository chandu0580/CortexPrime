"use client";

import { motion } from "framer-motion";
import { authStatusCards } from "./dashboardData";
import { Key, ShieldAlert, CheckCircle, Clock, RefreshCw } from "lucide-react";
import StatusBadge, { IntegrationStatusType } from "./StatusBadge";
import { variants } from "@/lib/motion-tokens";

export default function AuthCard() {
  const getIcon = (health: string) => {
    switch (health) {
      case "healthy":
        return <CheckCircle className="h-4 w-4 text-[#38B88A]" />;
      case "warning":
        return <Clock className="h-4 w-4 text-amber-500" />;
      default:
        return <ShieldAlert className="h-4 w-4 text-red-500" />;
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
      {authStatusCards.map((card, index) => {
        const isCritical = card.health === "critical";
        const isWarning = card.health === "warning";

        const borderStyle = isCritical
          ? "border-red-200 hover:border-red-400/40"
          : isWarning
          ? "border-amber-200 hover:border-amber-400/40"
          : "border-[#E5E7EB] hover:border-[#38B88A]/40";

        return (
          <motion.div
            key={card.connectionType}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.04 }}
            whileHover={variants.cardHover}
            className={`flex flex-col justify-between rounded-[20px] border bg-white p-4 shadow-[0_8px_30px_rgb(0,0,0,0.01)] transition-all duration-200 ${borderStyle}`}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-[#F3F4F6] pb-2.5">
              <span className="text-xs font-extrabold text-[#111827] truncate pr-1">
                {card.connectionType}
              </span>
              {getIcon(card.health)}
            </div>

            {/* Content Details */}
            <div className="mt-3 flex flex-col gap-2">
              <div className="flex items-center justify-between text-[11px] font-semibold text-[#6B7280]">
                <span>Expiration</span>
                <span className={`font-bold ${isCritical ? "text-[#B91C1C]" : "text-[#111827]"}`}>
                  {card.expires}
                </span>
              </div>

              <div className="flex items-center justify-between text-[11px] font-semibold text-[#6B7280]">
                <span>Rotation Status</span>
                <span className="font-bold text-[#111827]">{card.rotationStatus}</span>
              </div>

              <div className="flex items-center justify-between text-[11px] font-semibold text-[#6B7280]">
                <span>Last Verified</span>
                <span className="font-bold text-[#111827]">{card.lastVerified}</span>
              </div>
            </div>

            {/* Footer with Badge */}
            <div className="mt-3 flex items-center justify-between border-t border-[#F3F4F6] pt-2 text-[9px] font-bold">
              <span className="text-[#6B7280] uppercase tracking-wider">Health status</span>
              <StatusBadge status={card.health as IntegrationStatusType} className="py-0 px-2 text-[10px]">
                {card.health}
              </StatusBadge>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
