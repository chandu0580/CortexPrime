"use client";

import { motion } from "framer-motion";
import { Save, RotateCcw, Upload, Download, CheckCircle2 } from "lucide-react";
import { dur, ease } from "@/lib/motion-tokens";

interface SettingsHeaderProps {
  onSave?: () => void;
  onReset?: () => void;
  onImport?: () => void;
  onExport?: () => void;
}

export default function SettingsHeader({
  onSave,
  onReset,
  onImport,
  onExport,
}: SettingsHeaderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: dur.base, ease: ease.out }}
      className="flex flex-col gap-4 border-b border-[#E5E7EB] pb-5 lg:flex-row lg:items-center lg:justify-between"
    >
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-[#111827]">
          Settings
        </h1>
        <p className="mt-1.5 text-sm font-medium text-[#6B7280]">
          Configure your CortexPrime AI Operating System, organization, users, models, security, and platform preferences.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Import Settings */}
        <button
          onClick={onImport}
          className="inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB] focus:outline-none focus:ring-2 focus:ring-[#38B88A] focus:ring-offset-2"
          aria-label="Import system settings configuration"
        >
          <Upload className="mr-1.5 h-3.5 w-3.5 text-[#6B7280]" />
          Import Settings
        </button>

        {/* Export Configuration */}
        <button
          onClick={onExport}
          className="inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-[#111827] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-[#F9FAFB] focus:outline-none focus:ring-2 focus:ring-[#38B88A] focus:ring-offset-2"
          aria-label="Export system configuration log"
        >
          <Download className="mr-1.5 h-3.5 w-3.5 text-[#6B7280]" />
          Export Configuration
        </button>

        {/* Reset */}
        <button
          onClick={onReset}
          className="inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-[#6B7280] shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:bg-red-50 hover:text-red-600 hover:border-red-200 focus:outline-none"
          aria-label="Reset forms to initial configuration"
        >
          <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
          Reset
        </button>

        {/* Save Changes */}
        <button
          onClick={onSave}
          className="inline-flex items-center rounded-xl bg-[#38B88A] px-4 py-2 text-xs font-bold text-white shadow-[0_4px_14px_rgba(56,184,138,0.25)] transition-all hover:bg-[#2F9F77] hover:shadow-[0_6px_16px_rgba(56,184,138,0.3)] active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-[#38B88A] focus:ring-offset-2"
        >
          <Save className="mr-1.5 h-4 w-4" />
          Save Changes
        </button>
      </div>
    </motion.div>
  );
}
