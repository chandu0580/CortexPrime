"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Archive,
  BarChart2,
  Bell,
  Bot,
  Brain,
  ChevronDown,
  ChevronLeft,
  Database,
  Home,
  Mic,
  Monitor,
  Plus,
  Puzzle,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Target,
  Zap,
  Users,
  Clock,
  AlertTriangle,
  FileText,
  CheckCircle,
  Server,
  Filter,
  MoreVertical,
  Plug,
  User,
  Lock,
  Palette,
  HardDrive,
  Key,
  CreditCard,
  Info,
  Sliders,
  Sun,
  Moon,
  ChevronRight,
  Globe,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";

// ─── NAV ─────────────────────────────────────────────────────────────────────
const NAV = [
  { href: "/command",       label: "Dashboard",    icon: Home      },
  { href: "/runtime",       label: "Runtime",      icon: Zap       },
  { href: "/agents",        label: "Agents",       icon: Bot       },
  { href: "/missions",      label: "Missions",     icon: Target    },
  { href: "/voice",         label: "Voice",        icon: Mic       },
  { href: "/memory",        label: "Memory",       icon: Brain     },
  { href: "/workspace",     label: "Research",     icon: Search    },
  { href: "/operator",      label: "Computer Use", icon: Monitor   },
  { href: "/browser",       label: "Browser",      icon: Globe     },
  { href: "/replay",        label: "Replay",       icon: Archive   },
  { href: "/analytics",     label: "Analytics",    icon: BarChart2 },
  { href: "/governance",    label: "Governance",   icon: ShieldCheck },
  { href: "/system-status", label: "Monitoring",   icon: Activity  },
  { href: "/integrations",  label: "Integrations", icon: Puzzle    },
  { href: "/settings",      label: "Settings",     icon: Settings  },
];

// ─── SIDEBAR ─────────────────────────────────────────────────────────────────
function Sidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  return (
    <aside className={cn(
      "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[#E8EDF3] bg-white transition-all duration-300",
      collapsed ? "w-[60px]" : "w-[152px]"
    )}>
      <div className={cn("flex items-center gap-2 px-4 py-[18px]", collapsed && "justify-center px-2")}>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#38B88A]">
          <svg viewBox="0 0 48 48" className="h-4 w-4 text-white" fill="none">
            <path d="M24 4.5 39 13v22L24 43.5 9 35V13Z" stroke="currentColor" strokeWidth="3.5" strokeLinejoin="round"/>
            <path d="M24 13 31 17v14l-7 4-7-4V17Z" fill="currentColor" fillOpacity=".3" stroke="currentColor" strokeWidth="2.8" strokeLinejoin="round"/>
          </svg>
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-[0.82rem] font-bold leading-tight text-[#111827]">CortexPrime</p>
            <p className="text-[0.62rem] font-medium text-[#9CA3AF]">AI Operating System</p>
          </div>
        )}
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-[2px]">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = label === "Settings";
          return (
            <Link key={label} href={href} className={cn(
              "flex items-center gap-2.5 rounded-[12px] px-2.5 py-2 text-[0.82rem] font-semibold transition-all",
              active ? "bg-[#ECFBF4] text-[#2F9F77]" : "text-[#6B7280] hover:bg-[#F5F7FA] hover:text-[#111827]",
              collapsed && "justify-center px-0"
            )}>
              <Icon className="h-[16px] w-[16px] shrink-0" />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>
      <div className="px-2 pb-4 space-y-2">
        {!collapsed && (
          <div className="rounded-[12px] relative border border-[#E8EDF3] bg-[#F8FAF9] px-2.5 py-2">
            <div className="absolute right-2 top-2 text-[0.65rem] font-bold text-[#38B88A] bg-[#ECFBF4] h-4 w-4 rounded-full flex items-center justify-center">8</div>
            <p className="text-[0.66rem] font-bold uppercase tracking-wider text-[#6B7280]">System Status</p>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#38B88A]" />
              <span className="text-[0.72rem] font-bold text-[#38B88A]">Healthy</span>
            </div>
            <p className="text-[0.62rem] text-[#9CA3AF] mt-0.5">All systems operational</p>
          </div>
        )}
        <div className="flex gap-1.5">
          <button onClick={onCollapse} className={cn(
            "flex-1 flex items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-white px-2.5 py-1.5 text-[0.72rem] font-semibold text-[#6B7280] hover:bg-[#F5F7FA]",
            collapsed && "justify-center"
          )}>
            <ChevronLeft className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")} />
            {!collapsed && <span>Collapse</span>}
          </button>
          {!collapsed && (
            <button className="flex h-8 w-8 items-center justify-center rounded-[12px] border border-[#E8EDF3] bg-white text-[#6B7280] hover:bg-[#F5F7FA]">
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}

// ─── TOPBAR ───────────────────────────────────────────────────────────────────
function TopBar({ sidebarWidth }: { sidebarWidth: number }) {
  const avatar = useMemo(() => `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`
  )}`, []);
  return (
    <header className="fixed top-0 right-0 z-30 flex items-center gap-3 border-b border-[#E8EDF3] bg-white/96 px-5 py-2.5 backdrop-blur transition-all duration-300"
      style={{ left: sidebarWidth }}>
      <label className="relative flex h-9 w-[200px] items-center">
        <Search className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-[#9CA3AF]" />
        <input type="search" placeholder="Search anything..." className="h-full w-full rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] pl-9 pr-12 text-[0.8rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3]" />
        <span className="absolute right-2.5 rounded-[6px] border border-[#E5E7EB] bg-white px-1 py-0.5 text-[0.6rem] font-semibold text-[#9CA3AF]">⌘ K</span>
      </label>
      <div className="hidden items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] px-3 py-1.5 xl:flex">
        <div className="flex h-6 w-6 items-center justify-center rounded-[8px] bg-[#ECFBF4] text-[#38B88A]"><Target className="h-3 w-3" /></div>
        <div>
          <p className="text-[0.6rem] font-medium text-[#9CA3AF]">Current Mission</p>
          <div className="flex items-center gap-1.5">
            <p className="text-[0.76rem] font-semibold text-[#111827]">Q2 Market Intelligence</p>
            <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-1.5 py-0.5 text-[0.58rem] font-bold text-[#2F9F77]">
              <span className="h-1 w-1 rounded-full bg-[#38B88A]" />Running
            </span>
          </div>
        </div>
        <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
      </div>
      <div className="hidden items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] px-3 py-1.5 lg:flex">
        <div className="flex h-6 w-6 items-center justify-center rounded-[8px] bg-[#ECFBF4] text-[#38B88A]"><Mic className="h-3 w-3" /></div>
        <div>
          <p className="text-[0.6rem] font-medium text-[#9CA3AF]">Voice Status</p>
          <p className="text-[0.76rem] font-semibold text-[#111827]">Listening...</p>
        </div>
        <div className="ml-1 flex items-end gap-[2px]">
          {[3, 5, 4, 6, 3, 5, 4].map((h, i) => (
            <span key={i} className="w-[2px] rounded-full bg-[#38B88A]" style={{ height: `${h * 2}px` }} />
          ))}
        </div>
      </div>
      <div className="ml-auto flex items-center gap-2.5">
        <button className="relative flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#E8EDF3] bg-white text-[#374151] hover:bg-[#F5F7FA]">
          <Bell className="h-4 w-4" />
          <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-[#EF4444] text-[0.56rem] font-bold text-white ring-2 ring-white">3</span>
        </button>
        <div className="flex cursor-pointer items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-white p-1 pr-2.5 hover:bg-[#F5F7FA]">
          <Image src={avatar} alt="Alex Morgan" width={28} height={28} className="rounded-[8px]" />
          <div className="hidden leading-tight sm:block">
            <p className="text-[0.76rem] font-semibold text-[#111827]">Alex Morgan</p>
            <p className="text-[0.62rem] text-[#9CA3AF]">Enterprise Admin</p>
          </div>
          <ChevronDown className="hidden h-3 w-3 text-[#9CA3AF] sm:block" />
        </div>
      </div>
    </header>
  );
}

// ─── TOGGLE SWITCH COMPONENT ──────────────────────────────────────────────────
function ToggleSwitch({ active, onToggle }: { active: boolean; onToggle?: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out outline-none",
        active ? "bg-[#38B88A]" : "bg-[#E5E7EB]"
      )}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out",
          active ? "translate-x-4" : "translate-x-0"
        )}
      />
    </button>
  );
}

// ─── VERTICAL SETTINGS MENU TABS ──────────────────────────────────────────────
const SETTINGS_TABS = [
  { id: "general",       label: "General",        icon: Sliders       },
  { id: "account",       label: "Account",        icon: User          },
  { id: "security",      label: "Security",       icon: Lock          },
  { id: "notifications",  label: "Notifications",  icon: Bell          },
  { id: "appearance",    label: "Appearance",     icon: Palette       },
  { id: "ai",            label: "AI Preferences", icon: Bot           },
  { id: "voice",         label: "Voice & Audio",  icon: Mic           },
  { id: "privacy",       label: "Data & Privacy", icon: Database      },
  { id: "storage",       label: "Storage",        icon: HardDrive     },
  { id: "api",           label: "API & Access",   icon: Key           },
  { id: "billing",       label: "Billing",        icon: CreditCard    },
  { id: "audit",         label: "Audit Logs",     icon: FileText      },
  { id: "about",         label: "About",          icon: Info          },
];

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function SettingsCenter() {
  const [collapsed, setCollapsed] = useState(false);
  const sidebarWidth = collapsed ? 60 : 152;
  const [activeTab, setActiveTab] = useState("general");

  // Config States
  const [tipsSuggestions, setTipsSuggestions] = useState(true);
  const [autoSave, setAutoSave] = useState(true);
  const [codeExecution, setCodeExecution] = useState(true);
  const [dataCollection, setDataCollection] = useState(true);
  const [compactMode, setCompactMode] = useState(false);

  // Profile Avatar placeholder
  const morganAvatar = useMemo(() => `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`
  )}`, []);

  return (
    <div className="min-h-screen bg-[#F4F7FA] text-[#111827]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed(!collapsed)} />

      <div className="flex flex-col min-h-screen transition-all duration-300" style={{ marginLeft: sidebarWidth }}>
        <TopBar sidebarWidth={sidebarWidth} />

        {/* Content container */}
        <main className="flex-1 px-6 pt-20 pb-12">
          {/* Page Heading */}
          <div className="mb-6">
            <h1 className="text-[1.5rem] font-extrabold tracking-tight text-[#111827]">Settings</h1>
            <p className="text-[0.82rem] font-medium text-[#6B7280] mt-0.5">
              Manage your system preferences, account settings, and configurations.
            </p>
          </div>

          <motion.div
            initial="hidden"
            animate="visible"
            variants={stagger(0.04, 0.01)}
            className="grid grid-cols-1 gap-5 lg:grid-cols-12 items-start"
          >
            {/* Left Categories Menu Tabs */}
            <motion.div variants={variants.fadeUp} className="lg:col-span-3 rounded-[16px] border border-[#E8EDF3] bg-white p-3.5 shadow-sm space-y-0.5">
              {SETTINGS_TABS.map((tab) => {
                const isActive = activeTab === tab.id;
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      "w-full flex items-center gap-2.5 rounded-[12px] px-3.5 py-2 text-[0.8rem] font-bold transition-all text-left",
                      isActive
                        ? "bg-[#ECFBF4] text-[#2F9F77]"
                        : "text-[#6B7280] hover:bg-[#F5F7FA] hover:text-[#111827]"
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </motion.div>

            {/* General Settings Form Panel */}
            <motion.div variants={variants.fadeUp} className="lg:col-span-5 rounded-[16px] border border-[#E8EDF3] bg-white p-5 shadow-sm flex flex-col justify-between h-full">
              <div className="space-y-4">
                <div>
                  <p className="text-[0.9rem] font-bold text-[#111827]">General Settings</p>
                  <p className="text-[0.74rem] text-[#6B7280] mt-0.5 font-medium leading-relaxed">
                    Configure general system preferences and defaults.
                  </p>
                </div>

                <div className="space-y-4.5 pt-2">
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.78rem] font-bold text-[#374151]">System Language</label>
                    <p className="text-[0.66rem] text-[#9CA3AF] font-medium mb-1">Choose your preferred language.</p>
                    <div className="relative">
                      <select className="w-full rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3.5 py-2 text-[0.78rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer focus:border-[#B7E5D3]">
                        <option>English (US)</option>
                        <option>English (UK)</option>
                        <option>Español</option>
                        <option>Deutsch</option>
                      </select>
                      <ChevronDown className="absolute right-3.5 top-3.5 h-3.5 w-3.5 text-[#9CA3AF] pointer-events-none" />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.78rem] font-bold text-[#374151]">Time Zone</label>
                    <p className="text-[0.66rem] text-[#9CA3AF] font-medium mb-1">Set your local time zone.</p>
                    <div className="relative">
                      <select className="w-full rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3.5 py-2 text-[0.78rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer focus:border-[#B7E5D3]">
                        <option>(UTC+05:30) Asia/Kolkata</option>
                        <option>(UTC+00:00) UTC / London</option>
                        <option>(UTC-05:00) US Eastern / New York</option>
                        <option>(UTC-08:00) US Pacific / Los Angeles</option>
                      </select>
                      <ChevronDown className="absolute right-3.5 top-3.5 h-3.5 w-3.5 text-[#9CA3AF] pointer-events-none" />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.78rem] font-bold text-[#374151]">Date Format</label>
                    <p className="text-[0.66rem] text-[#9CA3AF] font-medium mb-1">Choose your preferred date format.</p>
                    <div className="relative">
                      <select className="w-full rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3.5 py-2 text-[0.78rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer focus:border-[#B7E5D3]">
                        <option>May 12, 2024 (MMM DD, YYYY)</option>
                        <option>2024-05-12 (YYYY-MM-DD)</option>
                        <option>12/05/2024 (DD/MM/YYYY)</option>
                      </select>
                      <ChevronDown className="absolute right-3.5 top-3.5 h-3.5 w-3.5 text-[#9CA3AF] pointer-events-none" />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.78rem] font-bold text-[#374151]">Time Format</label>
                    <p className="text-[0.66rem] text-[#9CA3AF] font-medium mb-1">Choose your preferred time format.</p>
                    <div className="relative">
                      <select className="w-full rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3.5 py-2 text-[0.78rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer focus:border-[#B7E5D3]">
                        <option>12 Hour (02:30 PM)</option>
                        <option>24 Hour (14:30)</option>
                      </select>
                      <ChevronDown className="absolute right-3.5 top-3.5 h-3.5 w-3.5 text-[#9CA3AF] pointer-events-none" />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.78rem] font-bold text-[#374151]">Default Dashboard</label>
                    <p className="text-[0.66rem] text-[#9CA3AF] font-medium mb-1">Choose the default module to load on login.</p>
                    <div className="relative">
                      <select className="w-full rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3.5 py-2 text-[0.78rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer focus:border-[#B7E5D3]">
                        <option>Dashboard</option>
                        <option>Runtime</option>
                        <option>Agents</option>
                        <option>Missions</option>
                      </select>
                      <ChevronDown className="absolute right-3.5 top-3.5 h-3.5 w-3.5 text-[#9CA3AF] pointer-events-none" />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.78rem] font-bold text-[#374151]">Items per Page</label>
                    <p className="text-[0.66rem] text-[#9CA3AF] font-medium mb-1">Set default number of items in tables.</p>
                    <div className="relative">
                      <select className="w-full rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3.5 py-2 text-[0.78rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer focus:border-[#B7E5D3]">
                        <option>10</option>
                        <option>20</option>
                        <option>50</option>
                        <option>100</option>
                      </select>
                      <ChevronDown className="absolute right-3.5 top-3.5 h-3.5 w-3.5 text-[#9CA3AF] pointer-events-none" />
                    </div>
                  </div>

                  {/* Enable Tips toggle */}
                  <div className="flex items-center justify-between py-1 border-t border-[#F1F5F9] pt-3">
                    <div>
                      <p className="text-[0.78rem] font-bold text-[#374151]">Enable Tips & Suggestions</p>
                      <p className="text-[0.66rem] text-[#9CA3AF] font-medium mt-0.5">Show helpful tips and suggestions across the system.</p>
                    </div>
                    <ToggleSwitch active={tipsSuggestions} onToggle={() => setTipsSuggestions(!tipsSuggestions)} />
                  </div>

                  {/* Auto Save toggle */}
                  <div className="flex items-center justify-between py-1 border-t border-[#F1F5F9] pt-3">
                    <div>
                      <p className="text-[0.78rem] font-bold text-[#374151]">Auto Save</p>
                      <p className="text-[0.66rem] text-[#9CA3AF] font-medium mt-0.5">Automatically save your changes.</p>
                    </div>
                    <ToggleSwitch active={autoSave} onToggle={() => setAutoSave(!autoSave)} />
                  </div>
                </div>
              </div>

              <div className="pt-5 mt-4 border-t border-[#F1F5F9]">
                <button className="w-full rounded-[10px] bg-[#38B88A] hover:bg-[#2F9F77] py-2 text-[0.78rem] font-bold text-white transition-colors">
                  Save Changes
                </button>
              </div>
            </motion.div>

            {/* Right Column: Account + Security Settings Panels */}
            <motion.div variants={variants.fadeUp} className="lg:col-span-4 space-y-5">
              {/* Account Settings */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-5 shadow-sm">
                <div>
                  <p className="text-[0.9rem] font-bold text-[#111827]">Account Settings</p>
                  <p className="text-[0.74rem] text-[#6B7280] mt-0.5 font-medium leading-relaxed mb-4">
                    Manage your account information and profile.
                  </p>
                </div>

                <div className="flex items-center gap-4.5 mb-4">
                  <div className="relative h-16 w-16 overflow-hidden rounded-full border border-[#E8EDF3]">
                    <Image src={morganAvatar} alt="Alex Morgan" fill />
                  </div>
                  <button className="rounded-[10px] border border-[#E8EDF3] bg-white px-3 py-1.5 text-[0.7rem] font-bold text-[#374151] hover:bg-[#F8FAFC]">
                    Change Photo
                  </button>
                </div>

                <div className="space-y-3.5">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[0.7rem] font-bold text-[#6B7280]">Full Name</label>
                    <input type="text" defaultValue="Alex Morgan" className="rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3 py-2 text-[0.76rem] font-bold text-[#111827] outline-none" />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-[0.7rem] font-bold text-[#6B7280]">Email Address</label>
                    <input type="email" defaultValue="alex.morgan@cortexprime.ai" className="rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3 py-2 text-[0.76rem] font-bold text-[#111827] outline-none" />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-[0.7rem] font-bold text-[#6B7280]">Role</label>
                    <div className="relative">
                      <select className="w-full rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3 py-2 text-[0.76rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer">
                        <option>Enterprise Admin</option>
                        <option>Workspace Developer</option>
                        <option>Compliance Manager</option>
                      </select>
                      <ChevronDown className="absolute right-3 top-3 h-3.5 w-3.5 text-[#9CA3AF] pointer-events-none" />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="text-[0.7rem] font-bold text-[#6B7280]">Department</label>
                    <div className="relative">
                      <select className="w-full rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-3 py-2 text-[0.76rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer">
                        <option>Operations</option>
                        <option>Engineering</option>
                        <option>Risk Management</option>
                      </select>
                      <ChevronDown className="absolute right-3 top-3 h-3.5 w-3.5 text-[#9CA3AF] pointer-events-none" />
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-[#F1F5F9] mt-4 flex justify-end">
                  <button className="rounded-[10px] bg-[#38B88A] hover:bg-[#2F9F77] px-4 py-2 text-[0.74rem] font-bold text-white transition-colors">
                    Update Profile
                  </button>
                </div>
              </div>

              {/* Security Settings */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-5 shadow-sm space-y-4">
                <div>
                  <p className="text-[0.9rem] font-bold text-[#111827]">Security Settings</p>
                  <p className="text-[0.74rem] text-[#6B7280] mt-0.5 font-medium leading-relaxed">
                    Manage your password and authentication settings.
                  </p>
                </div>

                <div className="space-y-3.5 pt-1">
                  <div className="flex items-center justify-between text-[0.74rem] font-semibold border-b border-[#F1F5F9] pb-3.5">
                    <div>
                      <p className="text-[#374151] font-bold">Password</p>
                      <p className="text-[0.66rem] text-[#9CA3AF] mt-0.5">Last changed 30 days ago</p>
                    </div>
                    <button className="rounded-[10px] border border-[#E8EDF3] bg-white px-3 py-1.5 text-[0.7rem] font-bold text-[#374151] hover:bg-[#F8FAFC]">
                      Change Password
                    </button>
                  </div>

                  <div className="flex items-center justify-between text-[0.74rem] font-semibold border-b border-[#F1F5F9] pb-3.5 cursor-pointer group">
                    <div>
                      <p className="text-[#374151] font-bold">Two-Factor Authentication</p>
                      <p className="text-[0.66rem] text-[#9CA3AF] mt-0.5">Add an extra layer of security.</p>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0 select-none">
                      <span className="inline-flex items-center rounded-full bg-[#ECFBF4] px-2 py-0.5 text-[0.62rem] font-bold text-[#2F9F77] ring-1 ring-[#D6F0E5]">
                        Enabled
                      </span>
                      <ChevronRight className="h-4 w-4 text-[#9CA3AF] group-hover:text-[#374151] transition-colors" />
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[0.74rem] font-semibold border-b border-[#F1F5F9] pb-3.5">
                    <div>
                      <p className="text-[#374151] font-bold">Active Sessions</p>
                      <p className="text-[0.66rem] text-[#9CA3AF] mt-0.5">Manage your active sessions.</p>
                    </div>
                    <button className="rounded-[10px] border border-[#E8EDF3] bg-white px-3 py-1.5 text-[0.7rem] font-bold text-[#374151] hover:bg-[#F8FAFC]">
                      View Sessions
                    </button>
                  </div>

                  <div className="flex items-center justify-between text-[0.74rem] font-semibold">
                    <div>
                      <p className="text-[#374151] font-bold">API Keys</p>
                      <p className="text-[0.66rem] text-[#9CA3AF] mt-0.5">Manage API keys and access tokens.</p>
                    </div>
                    <button className="rounded-[10px] border border-[#E8EDF3] bg-white px-3 py-1.5 text-[0.7rem] font-bold text-[#374151] hover:bg-[#F8FAFC]">
                      Manage Keys
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          </motion.div>

          {/* Bottom Row Grid (3 panels side-by-side) */}
          <motion.div
            initial="hidden"
            animate="visible"
            variants={stagger(0.04, 0.01)}
            className="grid grid-cols-1 gap-5 md:grid-cols-3 mt-6 items-start"
          >
            {/* Appearance */}
            <motion.div variants={variants.fadeUp} className="rounded-[16px] border border-[#E8EDF3] bg-white p-5 shadow-sm space-y-4.5">
              <div>
                <p className="text-[0.9rem] font-bold text-[#111827]">Appearance</p>
                <p className="text-[0.74rem] text-[#6B7280] mt-0.5 font-medium leading-relaxed">
                  Customize the look and feel of the system.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <p className="text-[0.76rem] font-bold text-[#374151] mb-2">Theme</p>
                  <p className="text-[0.66rem] text-[#9CA3AF] font-medium mb-2.5">Choose your preferred theme.</p>
                  <div className="grid grid-cols-3 gap-2">
                    <button className="flex flex-col items-center gap-1.5 rounded-[10px] border-2 border-[#38B88A] bg-[#ECFBF4] text-[#2F9F77] py-2 text-[0.72rem] font-bold shadow-sm">
                      <Sun className="h-4 w-4" />
                      <span>Light</span>
                    </button>
                    <button className="flex flex-col items-center gap-1.5 rounded-[10px] border border-[#E8EDF3] bg-white text-[#6B7280] py-2 text-[0.72rem] font-bold hover:bg-[#F8FAFC]">
                      <Moon className="h-4 w-4" />
                      <span>Dark</span>
                    </button>
                    <button className="flex flex-col items-center gap-1.5 rounded-[10px] border border-[#E8EDF3] bg-white text-[#6B7280] py-2 text-[0.72rem] font-bold hover:bg-[#F8FAFC]">
                      <Monitor className="h-4 w-4" />
                      <span>System</span>
                    </button>
                  </div>
                </div>

                <div>
                  <p className="text-[0.76rem] font-bold text-[#374151] mb-2">Primary Color</p>
                  <p className="text-[0.66rem] text-[#9CA3AF] font-medium mb-3">Choose your primary color theme.</p>
                  <div className="flex items-center gap-3">
                    <button className="h-6.5 w-6.5 rounded-full bg-[#38B88A] ring-2 ring-offset-2 ring-[#38B88A] shrink-0" />
                    <button className="h-5 w-5 rounded-full bg-[#3B82F6] shrink-0" />
                    <button className="h-5 w-5 rounded-full bg-[#8B5CF6] shrink-0" />
                    <button className="h-5 w-5 rounded-full bg-[#F59E0B] shrink-0" />
                    <button className="h-5 w-5 rounded-full bg-[#EF4444] shrink-0" />
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-[#F1F5F9] pt-3">
                  <div>
                    <p className="text-[0.76rem] font-bold text-[#374151]">Compact Mode</p>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium mt-0.5">Reduce spacing for a more compact view.</p>
                  </div>
                  <ToggleSwitch active={compactMode} onToggle={() => setCompactMode(!compactMode)} />
                </div>
              </div>
            </motion.div>

            {/* AI Preferences */}
            <motion.div variants={variants.fadeUp} className="rounded-[16px] border border-[#E8EDF3] bg-white p-5 shadow-sm space-y-4.5">
              <div>
                <p className="text-[0.9rem] font-bold text-[#111827]">AI Preferences</p>
                <p className="text-[0.74rem] text-[#6B7280] mt-0.5 font-medium leading-relaxed">
                  Configure AI behavior and response preferences.
                </p>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[0.76rem] font-bold text-[#374151]">Response Length</p>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium mt-0.5 truncate">Choose default response length.</p>
                  </div>
                  <div className="relative shrink-0 w-32">
                    <select className="w-full rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] px-2.5 py-1.5 text-[0.72rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer">
                      <option>Balanced</option>
                      <option>Concise</option>
                      <option>Detailed</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-2.5 h-3 w-3 text-[#9CA3AF] pointer-events-none" />
                  </div>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[0.76rem] font-bold text-[#374151]">Creativity Level</p>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium mt-0.5 truncate">Set the creativity level for AI responses.</p>
                  </div>
                  <div className="relative shrink-0 w-32">
                    <select className="w-full rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] px-2.5 py-1.5 text-[0.72rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer">
                      <option>Medium</option>
                      <option>Low</option>
                      <option>High</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-2.5 h-3 w-3 text-[#9CA3AF] pointer-events-none" />
                  </div>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[0.76rem] font-bold text-[#374151]">Data Source Priority</p>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium mt-0.5 truncate">Choose preferred data source order.</p>
                  </div>
                  <div className="relative shrink-0 w-32">
                    <select className="w-full rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] px-2.5 py-1.5 text-[0.72rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer">
                      <option>System Default</option>
                      <option>Vector DB Only</option>
                      <option>Live Web Sync</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-2.5 h-3 w-3 text-[#9CA3AF] pointer-events-none" />
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-[#F1F5F9] pt-3">
                  <div>
                    <p className="text-[0.76rem] font-bold text-[#374151]">Code Execution</p>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium mt-0.5">Allow AI to write and execute code.</p>
                  </div>
                  <ToggleSwitch active={codeExecution} onToggle={() => setCodeExecution(!codeExecution)} />
                </div>
              </div>
            </motion.div>

            {/* Data & Privacy */}
            <motion.div variants={variants.fadeUp} className="rounded-[16px] border border-[#E8EDF3] bg-white p-5 shadow-sm space-y-4.5">
              <div>
                <p className="text-[0.9rem] font-bold text-[#111827]">Data & Privacy</p>
                <p className="text-[0.74rem] text-[#6B7280] mt-0.5 font-medium leading-relaxed">
                  Manage your data and privacy preferences.
                </p>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-3">
                  <div>
                    <p className="text-[0.76rem] font-bold text-[#374151]">Data Collection</p>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium mt-0.5">Allow anonymous usage data collection.</p>
                  </div>
                  <ToggleSwitch active={dataCollection} onToggle={() => setDataCollection(!dataCollection)} />
                </div>

                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[0.76rem] font-bold text-[#374151]">Memory Retention</p>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium mt-0.5 truncate">Set how long your data is retained.</p>
                  </div>
                  <div className="relative shrink-0 w-28">
                    <select className="w-full rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] px-2.5 py-1.5 text-[0.72rem] font-bold text-[#111827] outline-none appearance-none cursor-pointer">
                      <option>30 Days</option>
                      <option>60 Days</option>
                      <option>90 Days</option>
                      <option>Indefinitely</option>
                    </select>
                    <ChevronDown className="absolute right-2.5 top-2.5 h-3 w-3 text-[#9CA3AF] pointer-events-none" />
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-b border-[#F1F5F9] py-3">
                  <div>
                    <p className="text-[0.76rem] font-bold text-[#374151]">Export My Data</p>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium mt-0.5">Download a copy of your data.</p>
                  </div>
                  <button className="rounded-[10px] border border-[#E8EDF3] bg-white px-3.5 py-1.5 text-[0.7rem] font-bold text-[#374151] hover:bg-[#F8FAFC]">
                    Export
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[0.76rem] font-bold text-[#374151]">Delete My Data</p>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium mt-0.5">Permanently delete your data.</p>
                  </div>
                  <button className="rounded-[10px] bg-[#EF4444] hover:bg-[#DC2626] px-3.5 py-1.5 text-[0.7rem] font-bold text-white transition-colors">
                    Delete
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        </main>

        {/* Footer */}
        <footer className="mt-auto border-t border-[#E8EDF3] bg-white px-6 py-4 flex flex-col sm:flex-row justify-between items-center gap-2 text-[0.7rem] font-semibold text-[#9CA3AF] w-full text-center">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4 text-[#38B88A]" />
            <span>Enterprise-Grade Encryption & Audit Logging Active</span>
          </div>
          <p>© {new Date().getFullYear()} CortexPrime OS. All rights reserved.</p>
        </footer>
      </div>
    </div>
  );
}
