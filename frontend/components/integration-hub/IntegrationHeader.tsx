"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Plus, Key, Upload, Filter, RefreshCw, CheckCircle2, ChevronDown } from "lucide-react";
import { dur, ease } from "@/lib/motion-tokens";

interface IntegrationHeaderProps {
  onAddIntegration?: () => void;
  onCreateApiKey?: () => void;
  onImportConfig?: () => void;
  onRefresh?: () => void;
}

export default function IntegrationHeader({
  onAddIntegration,
  onCreateApiKey,
  onImportConfig,
  onRefresh,
}: IntegrationHeaderProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefreshClick = () => {
    setIsRefreshing(true);
    if (onRefresh) onRefresh();
    setTimeout(() => setIsRefreshing(false), 800);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: dur.base, ease: ease.out }}
      className="flex flex-col gap-4 border-b border-[#E5E7EB] pb-5 lg:flex-row lg:items-center lg:justify-between"
    >
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-[#111827]">
          Integration Hub
        </h1>
        <p className="mt-1.5 text-sm font-medium text-[#6B7280]">
          Connect CortexPrime with your enterprise ecosystem and monitor every integration from one unified workspace.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Connection status indicator */}
        <div className="inline-flex items-center gap-1.5 rounded-xl border border-[#D6F0E5] bg-[#E8F5EE] px-3.5 py-2 text-xs font-bold text-[#2F9F77] shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
          <CheckCircle2 className="h-3.5 w-3.5 text-[#38B88A]" />
          <span>Ecosystem Connected</span>
        </div>

        {/* Import Configuration */}
        <button
          onClick={onImportConfig}
          className="inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB] focus:outline-none focus:ring-2 focus:ring-[#38B88A] focus:ring-offset-2"
          aria-label="Import Configuration"
        >
          <Upload className="mr-1.5 h-3.5 w-3.5 text-[#6B7280]" />
          Import Configuration
        </button>

        {/* Create API Key */}
        <button
          onClick={onCreateApiKey}
          className="inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB] focus:outline-none focus:ring-2 focus:ring-[#38B88A] focus:ring-offset-2"
          aria-label="Create API Key"
        >
          <Key className="mr-1.5 h-3.5 w-3.5 text-[#6B7280]" />
          Create API Key
        </button>

        {/* Filters */}
        <button className="inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB] focus:outline-none focus:ring-2 focus:ring-[#38B88A] focus:ring-offset-2">
          <Filter className="mr-1.5 h-3.5 w-3.5 text-[#6B7280]" />
          Filters
          <ChevronDown className="ml-1 h-3 w-3 text-[#6B7280]" />
        </button>

        {/* Refresh */}
        <button
          onClick={handleRefreshClick}
          className="inline-flex items-center justify-center rounded-xl border border-[#E5E7EB] bg-white p-2.5 text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB] focus:outline-none focus:ring-2 focus:ring-[#38B88A] focus:ring-offset-2"
          aria-label="Refresh integration statuses"
        >
          <RefreshCw className={`h-3.5 w-3.5 text-[#6B7280] ${isRefreshing ? "animate-spin text-[#38B88A]" : ""}`} />
        </button>

        {/* Add Integration */}
        <button
          onClick={onAddIntegration}
          className="inline-flex items-center rounded-xl bg-[#38B88A] px-4 py-2 text-xs font-bold text-white shadow-[0_4px_14px_rgba(56,184,138,0.25)] transition-all hover:bg-[#2F9F77] hover:shadow-[0_6px_16px_rgba(56,184,138,0.3)] active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-[#38B88A] focus:ring-offset-2"
        >
          <Plus className="mr-1.5 h-4 w-4" />
          Add Integration
        </button>
      </div>
    </motion.div>
  );
}
