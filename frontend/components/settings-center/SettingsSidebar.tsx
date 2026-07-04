"use client";

import { motion } from "framer-motion";
import { cn } from "@/utils/cn";
import {
  Building2,
  FolderOpen,
  Users,
  Fingerprint,
  ShieldCheck,
  Brain,
  Mic,
  Database,
  Plug,
  Bell,
  Key,
  CreditCard,
  Palette,
  Sliders,
  Info,
} from "lucide-react";

export type SettingsTabId =
  | "organization"
  | "workspace"
  | "users"
  | "authentication"
  | "security"
  | "models"
  | "voice"
  | "memory"
  | "integrations"
  | "notifications"
  | "api_keys"
  | "billing"
  | "appearance"
  | "system_prefs"
  | "about";

interface SettingsTabItem {
  id: SettingsTabId;
  label: string;
  icon: React.ComponentType<any>;
}

export const settingsTabs: SettingsTabItem[] = [
  { id: "organization", label: "Organization", icon: Building2 },
  { id: "workspace", label: "Workspace", icon: FolderOpen },
  { id: "users", label: "Users & Roles", icon: Users },
  { id: "authentication", label: "Authentication", icon: Fingerprint },
  { id: "security", label: "Security & Trust", icon: ShieldCheck },
  { id: "models", label: "AI Models", icon: Brain },
  { id: "voice", label: "Voice & Speech", icon: Mic },
  { id: "memory", label: "Memory System", icon: Database },
  { id: "integrations", label: "Integrations", icon: Plug },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "api_keys", label: "API Keys & Secrets", icon: Key },
  { id: "billing", label: "Billing & Plans", icon: CreditCard },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "system_prefs", label: "System Preferences", icon: Sliders },
  { id: "about", label: "About System", icon: Info },
];

interface SettingsSidebarProps {
  activeTab: SettingsTabId;
  onChangeTab: (id: SettingsTabId) => void;
  className?: string;
}

export default function SettingsSidebar({
  activeTab,
  onChangeTab,
  className,
}: SettingsSidebarProps) {
  return (
    <div className={cn("flex flex-col gap-1 w-full rounded-[24px] border border-[#E5E7EB] bg-white p-3.5 shadow-[0_8px_30px_rgb(0,0,0,0.01)]", className)}>
      <span className="px-3 pb-2 text-[10px] font-extrabold uppercase tracking-wider text-[#6B7280]">
        System Settings
      </span>
      <nav className="flex flex-col gap-0.5">
        {settingsTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onChangeTab(tab.id)}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-xs font-bold transition-all duration-150 border border-transparent focus:outline-none focus:ring-1 focus:ring-[#38B88A]/50",
                isActive
                  ? "bg-[#E8F5EE] text-[#2F9F77]"
                  : "text-[#6B7280] hover:bg-[#F8FAFC] hover:text-[#111827]"
              )}
            >
              <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-[#38B88A]" : "text-[#9CA3AF]")} />
              <span className="truncate">{tab.label}</span>
              {isActive && (
                <motion.div
                  layoutId="activeIndicator"
                  className="ml-auto h-1.5 w-1.5 rounded-full bg-[#38B88A]"
                  transition={{ type: "spring" as const, stiffness: 380, damping: 30 }}
                />
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
