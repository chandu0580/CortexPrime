"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { defaultAIModels, AIModelConfig } from "./dashboardData";
import { Cpu, CheckCircle2, AlertTriangle, Layers, Sliders } from "lucide-react";
import StatusBadge, { SettingsStatusType } from "./StatusBadge";
import { variants } from "@/lib/motion-tokens";

export default function ModelCard() {
  const [models, setModels] = useState<AIModelConfig[]>(defaultAIModels);

  const handleTempChange = (id: string, newTemp: number) => {
    setModels(prev =>
      prev.map(m => (m.id === id ? { ...m, temperature: newTemp } : m))
    );
  };

  const handleSetDefault = (id: string) => {
    setModels(prev =>
      prev.map(m => ({ ...m, isDefault: m.id === id }))
    );
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return <CheckCircle2 className="h-4 w-4 text-[#38B88A]" />;
      case "degraded":
        return <AlertTriangle className="h-4 w-4 text-amber-500" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      {models.map((model) => {
        const isOffline = model.status === "offline";
        const isDefault = model.isDefault;

        return (
          <motion.div
            key={model.id}
            whileHover={variants.cardHover}
            className={`flex flex-col justify-between rounded-[24px] border bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.01)] transition-all duration-200 ${
              isDefault
                ? "border-[#38B88A] hover:border-[#38B88A]/60"
                : isOffline
                ? "border-red-200 hover:border-red-400/40"
                : "border-[#E5E7EB] hover:border-[#38B88A]/40"
            }`}
          >
            {/* Model Card Header */}
            <div>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <Cpu className={`h-5 w-5 ${isDefault ? "text-[#38B88A]" : "text-[#6B7280]"}`} />
                  <div>
                    <h4 className="text-xs font-extrabold text-[#111827] leading-tight">
                      {model.name}
                    </h4>
                    <span className="text-[9px] font-bold uppercase tracking-wider text-[#6B7280]">
                      {model.provider}
                    </span>
                  </div>
                </div>
                {getStatusIcon(model.status)}
              </div>

              {/* Specs */}
              <div className="mt-4 flex flex-col gap-2 border-t border-[#F3F4F6] pt-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#6B7280]">Context Window</span>
                  <span className="font-bold text-[#111827]">{model.contextWindow}</span>
                </div>

                {/* Temperature slider control */}
                <div className="flex flex-col gap-1 mt-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#6B7280]">Temperature</span>
                    <span className="font-mono text-[10px] font-bold text-[#38B88A]">
                      {model.temperature.toFixed(1)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    disabled={isOffline}
                    value={model.temperature}
                    onChange={(e) => handleTempChange(model.id, parseFloat(e.target.value))}
                    className="w-full h-1 bg-[#F3F4F6] rounded-lg appearance-none cursor-pointer accent-[#38B88A] disabled:opacity-50"
                  />
                </div>
              </div>
            </div>

            {/* Default logic card footer */}
            <div className="mt-5 flex items-center justify-between border-t border-[#F3F4F6] pt-3">
              <button
                onClick={() => !isOffline && handleSetDefault(model.id)}
                disabled={isOffline}
                className={`inline-flex items-center gap-1 rounded-xl px-2.5 py-1 text-[10px] font-bold transition-all ${
                  isDefault
                    ? "bg-[#E8F5EE] text-[#2F9F77]"
                    : "border border-[#E5E7EB] bg-white text-[#6B7280] hover:bg-[#F9FAFB] hover:text-[#111827] disabled:opacity-50"
                }`}
              >
                {isDefault ? "Default Engine" : "Make Default"}
              </button>

              <StatusBadge status={model.status as SettingsStatusType}>
                {model.status}
              </StatusBadge>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
