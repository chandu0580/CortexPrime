"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { defaultIntegrationPreferences, ConnectedIntegrationPreference } from "./mockData";
import { Settings, RefreshCw, LogOut, CheckCircle2, XCircle } from "lucide-react";
import { variants } from "@/lib/motion-tokens";
import StatusBadge, { SettingsStatusType } from "./StatusBadge";

export default function IntegrationCard() {
  const [integrations, setIntegrations] = useState<ConnectedIntegrationPreference[]>(defaultIntegrationPreferences);

  const handleToggleConnection = (id: string, currentStatus: string) => {
    setIntegrations(prev =>
      prev.map(item => {
        if (item.id === id) {
          const newStatus = currentStatus === "connected" ? "disconnected" : "connected";
          return { ...item, status: newStatus };
        }
        return item;
      })
    );
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
      {integrations.map((item) => {
        const isConnected = item.status === "connected";

        return (
          <motion.div
            key={item.id}
            whileHover={variants.cardHover}
            className={`flex flex-col justify-between rounded-[20px] border bg-white p-4 shadow-[0_8px_30px_rgb(0,0,0,0.01)] transition-all duration-200 ${
              isConnected
                ? "border-green-200 hover:border-[#38B88A]/40"
                : "border-gray-200 hover:border-gray-400/40"
            }`}
          >
            {/* Logo and Name */}
            <div className="flex items-center justify-between border-b border-[#F3F4F6] pb-2.5">
              <span className="text-xs font-extrabold text-[#111827]">
                {item.name}
              </span>
              <StatusBadge status={isConnected ? "Connected" : "Disconnected"}>
                {item.status}
              </StatusBadge>
            </div>

            {/* Config options */}
            <div className="mt-3 flex items-center justify-between">
              <span className="text-[10px] font-semibold text-[#6B7280]">Access Level</span>
              <span className="text-[10px] font-bold text-[#111827]">
                {isConnected ? "Read & Write" : "None"}
              </span>
            </div>

            {/* Operational Actions */}
            <div className="mt-4 grid grid-cols-2 gap-2 border-t border-[#F3F4F6] pt-3">
              <button
                disabled={!isConnected}
                className="inline-flex items-center justify-center gap-1 rounded-xl border border-[#E5E7EB] bg-white py-1.5 text-[9px] font-bold text-[#6B7280] hover:bg-[#F9FAFB] hover:text-[#111827] transition-all disabled:opacity-50"
              >
                <Settings className="h-3 w-3" />
                Configure
              </button>

              <button
                disabled={!isConnected}
                className="inline-flex items-center justify-center gap-1 rounded-xl border border-[#E5E7EB] bg-white py-1.5 text-[9px] font-bold text-[#6B7280] hover:bg-[#F9FAFB] hover:text-[#111827] transition-all disabled:opacity-50"
              >
                <RefreshCw className="h-3 w-3" />
                Reconnect
              </button>

              <button
                onClick={() => handleToggleConnection(item.id, item.status)}
                className={`col-span-2 inline-flex items-center justify-center gap-1 rounded-xl py-1.5 text-[9px] font-bold transition-all ${
                  isConnected
                    ? "border border-red-100 bg-red-50 text-[#B91C1C] hover:bg-red-100"
                    : "border border-green-100 bg-green-50 text-[#2F9F77] hover:bg-green-100"
                }`}
              >
                <LogOut className="h-3 w-3" />
                {isConnected ? "Disconnect Service" : "Connect Service"}
              </button>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
