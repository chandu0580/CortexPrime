"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { risksData, RiskData } from "./mockData";
import { variants } from "@/lib/motion-tokens";
import { AlertCircle, AlertTriangle, ShieldAlert, Cpu } from "lucide-react";
import StatusBadge from "./StatusBadge";

export default function RiskCard() {
  const [risks, setRisks] = useState<RiskData[]>(risksData);

  const getRiskIcon = (level: string) => {
    switch (level) {
      case "critical":
        return ShieldAlert;
      case "high":
        return AlertCircle;
      default:
        return AlertTriangle;
    }
  };

  const getStyles = (level: string) => {
    switch (level) {
      case "critical":
        return {
          border: "border-red-200",
          iconBg: "bg-red-50 text-red-600",
          badge: "bg-red-50 text-red-600 border-red-200",
        };
      case "high":
        return {
          border: "border-amber-200",
          iconBg: "bg-amber-50 text-amber-600",
          badge: "bg-amber-50 text-amber-600 border-amber-200",
        };
      default:
        return {
          border: "border-yellow-100",
          iconBg: "bg-yellow-50 text-yellow-600",
          badge: "bg-yellow-50 text-yellow-600 border-yellow-200",
        };
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {risks.map((risk, index) => {
        const Icon = getRiskIcon(risk.level);
        const styles = getStyles(risk.level);

        return (
          <motion.div
            key={risk.id}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            whileHover={variants.cardHover}
            className={`flex flex-col justify-between rounded-[24px] border bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.02)] transition-shadow duration-200 hover:shadow-[0_12px_36px_rgba(56,184,138,0.06)] ${styles.border}`}
          >
            <div>
              {/* Header */}
              <div className="flex items-center justify-between border-b border-[#F3F4F6] pb-3">
                <span className="text-xs font-extrabold text-[#111827]">
                  {risk.title}
                </span>
                <StatusBadge status={risk.level}>{risk.level}</StatusBadge>
              </div>

              {/* Stats & Agent */}
              <div className="mt-4 flex items-start gap-3">
                <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${styles.iconBg}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <Cpu className="h-3.5 w-3.5 text-[#6B7280]" />
                    <span className="text-xs font-bold text-[#111827]">{risk.affectedAgent}</span>
                  </div>
                  <p className="mt-2 text-xs font-semibold text-[#6B7280]">
                    Occurrences today: <span className="font-extrabold text-[#111827]">{risk.occurrences}</span>
                  </p>
                  <p className="mt-0.5 text-xs font-semibold text-[#6B7280]">
                    Status: <span className="font-bold text-[#111827]">{risk.status}</span>
                  </p>
                </div>
              </div>
            </div>

            {/* Actionable containment footer */}
            <div className="mt-5 rounded-xl bg-[#F8FAFC] border border-[#E5E7EB] p-3 text-[11px] font-semibold text-[#111827]">
              <span className="block text-[9px] font-bold uppercase tracking-wider text-[#6B7280] mb-0.5">Recommended Action</span>
              {risk.recommendation}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
