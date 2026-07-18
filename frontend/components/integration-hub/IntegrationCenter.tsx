"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Bell,
  ChevronDown,
  ChevronLeft,
  Home,
  Zap,
  Bot,
  Target,
  Mic,
  Brain,
  Search,
  Monitor,
  Globe,
  Archive,
  BarChart2,
  ShieldCheck,
  Activity,
  Puzzle,
  Settings,
  RefreshCw,
  ScrollText,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { cn } from "@/utils/cn";

// Import subcomponents from enterprise-connectors folder
import { connectors as allConnectors } from "../enterprise-connectors/data";
import type { Connector, ConnectorStatus } from "../enterprise-connectors/types";
import type { FilterOption, ViewMode } from "../enterprise-connectors/ConnectorSearchBar";
import ConnectorSummaryCards from "../enterprise-connectors/ConnectorSummaryCards";
import ConnectorSearchBar from "../enterprise-connectors/ConnectorSearchBar";
import ConnectorGrid from "../enterprise-connectors/ConnectorGrid";
import ConnectorDrawer from "../enterprise-connectors/ConnectorDrawer";
import ConnectorRightPanel from "../enterprise-connectors/ConnectorRightPanel";
import { listConnectors, disconnectConnector } from "@/services/connector-api";
import type { ConnectorSummary } from "@/services/connector-api";

// ─── UTILS ───────────────────────────────────────────────────────────────────

function mapBackendToFrontend(b: ConnectorSummary): Connector {
  const id = b.type as Connector["id"];
  const local = allConnectors.find((c) => c.id === id);
  const isConnected = b.connection_state === "connected";
  return {
    id,
    name: b.name,
    description: b.description,
    status: (isConnected ? "connected" : "disconnected") as ConnectorStatus,
    capabilities: (b.capabilities || []).map((c: string) => ({ label: c })),
    authFields: local?.authFields || [],
    permissions: local?.permissions || [],
    longDescription: local?.longDescription || b.description,
    operations: b.operations || [],
    stats: isConnected
      ? [
          { label: "Operations", value: String(b.operations?.length || "--") },
          { label: "Capabilities", value: String(b.capabilities?.length || "--") },
          { label: "Status", value: b.connection_state === "connected" ? "Live" : "--" },
        ]
      : local?.stats?.map((s) => ({ ...s, value: "--" })) || [],
    latency: b.latency_ms != null ? `${b.latency_ms} ms` : null,
    lastSync: null,
    health: b.health || null,
    connectionState: b.connection_state,
    hasCredentials: b.has_credentials,
    latencyMs: b.latency_ms,
  };
}

// ─── NAV ─────────────────────────────────────────────────────────────────────
const NAV = [
  { href: "/command",       label: "Dashboard",    icon: Home      },
  { href: "/runtime",       label: "Runtime",      icon: Zap       },
  { href: "/agents",        label: "Agents",       icon: Bot       },
  { href: "/missions",      label: "Missions",     icon: Target    },
  { href: "/chat",          label: "Chat",         icon: Settings  }, // replaced Settings with custom or general icon
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
      collapsed ? "w-[60px]" : "w-[185px]"
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
          const active = label === "Integrations";
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
          <p className="text-[0.76rem] font-semibold text-[#111827]">Not Active</p>
        </div>
      </div>
      <div className="ml-auto flex items-center gap-2.5">
        <button className="relative flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#E8EDF3] bg-white text-[#374151] hover:bg-[#F5F7FA]">
          <Bell className="h-4 w-4" />
          <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-[#EF4444] text-[0.56rem] font-bold text-white ring-2 ring-white">1</span>
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

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function IntegrationCenter() {
  const [collapsed, setCollapsed] = useState(false);
  const sidebarWidth = collapsed ? 60 : 185;

  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<FilterOption>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedConnectorId, setSelectedConnectorId] = useState<string | null>(null);
  const [connectors, setConnectors] = useState<Connector[]>(allConnectors);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const selectedConnector = useMemo(
    () => connectors.find((c) => c.id === selectedConnectorId) ?? null,
    [connectors, selectedConnectorId]
  );

  const fetchConnectors = useCallback(async () => {
    try {
      const data = await listConnectors();
      const mapped = data.connectors.map(mapBackendToFrontend);
      setConnectors((prev) => {
        const merged = allConnectors.map((local) => {
          const backend = mapped.find((m) => m.id === local.id);
          if (!backend) return local;
          return {
            ...local,
            ...backend,
            permissions: local.permissions,
            authFields: local.authFields,
            longDescription: local.longDescription,
          };
        });
        return merged;
      });
    } catch {
      // Fall back to static data if backend is unavailable
    }
  }, []);

  useEffect(() => {
    fetchConnectors();
    const interval = setInterval(fetchConnectors, 30000);
    return () => clearInterval(interval);
  }, [fetchConnectors]);

  const filteredConnectors = useMemo(() => {
    let result = connectors;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.description.toLowerCase().includes(q) ||
          c.capabilities.some((cap) => cap.label.toLowerCase().includes(q))
      );
    }
    if (activeFilter !== "all") {
      if (activeFilter === "needs_configuration") {
        result = result.filter((c) => c.status === "needs_configuration" || c.status === "connection_error");
      } else {
        result = result.filter((c) => c.status === activeFilter);
      }
    }
    return result;
  }, [connectors, searchQuery, activeFilter]);

  const filterCounts = useMemo((): Partial<Record<FilterOption, number>> => {
    const base = searchQuery.trim()
      ? connectors.filter((c) => c.name.toLowerCase().includes(searchQuery.toLowerCase()))
      : connectors;
    return {
      all: base.length,
      connected: base.filter((c) => c.status === "connected" || c.status === "healthy").length,
      disconnected: base.filter((c) => c.status === "disconnected").length,
      healthy: base.filter((c) => c.status === "connected" || c.status === "healthy").length,
      needs_configuration: base.filter((c) => c.status === "needs_configuration" || c.status === "connection_error").length,
    };
  }, [connectors, searchQuery]);

  const handleOpenDrawer = useCallback((id: string) => {
    setSelectedConnectorId(id);
    setDrawerOpen(true);
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setTimeout(() => setSelectedConnectorId(null), 250);
  }, []);

  const handleConnect = useCallback((_id: string) => {
    // Connection is handled via the Auth tab API call
  }, []);

  const handleDisconnect = useCallback(async (id: string) => {
    try {
      await disconnectConnector(id);
    } catch {
      // Continue with local state update even if API fails
    }
    setConnectors((prev) =>
      prev.map((c) =>
        c.id === id
          ? {
              ...c,
              status: "disconnected" as ConnectorStatus,
              stats: c.stats?.map((s) => ({ ...s, value: "--" })),
              latency: null,
              lastSync: null,
              health: null,
              connectionState: "disconnected",
              latencyMs: null,
            }
          : c
      )
    );
    handleCloseDrawer();
  }, [handleCloseDrawer]);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    fetchConnectors().finally(() => setIsRefreshing(false));
  }, [fetchConnectors]);

  return (
    <div className="min-h-screen bg-[#F4F7FA] text-[#111827]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed(!collapsed)} />

      <div className="flex flex-col min-h-screen transition-all duration-300" style={{ marginLeft: sidebarWidth }}>
        <TopBar sidebarWidth={sidebarWidth} />

        {/* Content container */}
        <main className="flex-1 px-6 pt-20 pb-12 flex flex-col gap-5">
          {/* Page Heading */}
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center mb-1">
            <div>
              <h1 className="text-[1.5rem] font-extrabold tracking-tight text-[#111827] m-0">Integrations</h1>
              <p className="text-[0.82rem] font-medium text-[#6B7280] mt-0.5 m-0">
                Connect and manage your enterprise systems
              </p>
            </div>
            <div>
              <button
                onClick={handleRefresh}
                className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3.5 py-2 text-[0.76rem] font-bold text-[#6B7280] hover:bg-[#F8FAFC]"
              >
                <RefreshCw
                  className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin")}
                />
                <ScrollText className="h-3.5 w-3.5" />
                <span>Integration Logs</span>
              </button>
            </div>
          </div>

          <div style={{ display: "flex", gap: "var(--space-5)", alignItems: "flex-start" }}>
            <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
              <ConnectorSummaryCards
                data={{
                  connected: connectors.filter((c) => c.status === "connected" || c.status === "healthy").length,
                  healthy:   connectors.filter((c) => c.status === "connected" || c.status === "healthy").length,
                  pending:   connectors.filter((c) => c.status === "disconnected").length,
                  total:     connectors.length,
                  lastSync:  null,
                  apiCallsToday: 18293,
                  avgLatency:    "183 ms",
                  errorsToday:   0,
                }}
              />
              <ConnectorSearchBar
                query={searchQuery}
                onQueryChange={setSearchQuery}
                activeFilter={activeFilter}
                onFilterChange={setActiveFilter}
                counts={filterCounts}
                viewMode={viewMode}
                onViewModeChange={setViewMode}
              />
              <ConnectorGrid
                connectors={filteredConnectors}
                onConnect={handleOpenDrawer}
                onViewDetails={handleOpenDrawer}
              />
            </div>

            <ConnectorRightPanel
              connectors={connectors}
              onViewConnector={handleOpenDrawer}
            />
          </div>

          {/* Footer Security Badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "var(--space-4)",
              padding: "var(--space-3) var(--space-5)",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              flexWrap: "wrap",
              marginTop: "var(--space-2)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <div
                style={{
                  width: 28, height: 28, borderRadius: "var(--radius-sm)",
                  background: "var(--success-muted)", border: "1px solid var(--success-border)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "var(--success)", flexShrink: 0,
                }}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </div>
              <div>
                <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-primary)", margin: 0 }}>
                  <span style={{ fontWeight: 700 }}>Your data is secure</span>{" "}
                  <span style={{ color: "var(--text-muted)", fontSize: 11, marginLeft: 6 }}>
                    All integrations are encrypted and securely stored. We never store your passwords or tokens.
                  </span>
                </p>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
              {[
                { icon: "✓", label: "SOC 2 Type II",  sub: "Compliant" },
                { icon: "✓", label: "GDPR",            sub: "Compliant" },
                { icon: "🔒", label: "Encryption",     sub: "AES-256" },
              ].map((badge) => (
                <div key={badge.label} style={{ display: "flex", alignItems: "center", gap: 5, textAlign: "center" }}>
                  <span style={{ fontSize: "var(--font-size-sm)", color: "var(--success)" }}>{badge.icon}</span>
                  <div>
                    <p style={{ fontSize: "var(--font-size-xs)", fontWeight: 600, color: "var(--text-primary)", margin: 0 }}>
                      {badge.label}
                    </p>
                    <p style={{ fontSize: 10, color: "var(--text-muted)", margin: 0 }}>{badge.sub}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>

      <ConnectorDrawer
        connector={selectedConnector}
        open={drawerOpen}
        onClose={handleCloseDrawer}
        onConnect={handleConnect}
        onDisconnect={handleDisconnect}
        onRefresh={fetchConnectors}
      />
    </div>
  );
}
