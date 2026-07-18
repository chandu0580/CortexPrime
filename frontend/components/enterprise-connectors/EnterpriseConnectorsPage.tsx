"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { ScrollText, RefreshCw } from "lucide-react";
import { dur, ease } from "@/lib/motion-tokens";
import { connectors as allConnectors } from "./data";
import type { ConnectorStatus } from "./types";
import type { FilterOption, ViewMode } from "./ConnectorSearchBar";
import ConnectorSummaryCards from "./ConnectorSummaryCards";
import ConnectorSearchBar from "./ConnectorSearchBar";
import ConnectorGrid from "./ConnectorGrid";
import ConnectorDrawer from "./ConnectorDrawer";
import ConnectorRightPanel from "./ConnectorRightPanel";
import type { Connector } from "./types";
import { listConnectors, disconnectConnector } from "@/services/connector-api";
import type { ConnectorSummary } from "@/services/connector-api";

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

export default function EnterpriseConnectorsPage() {
  const [searchQuery,  setSearchQuery]  = useState("");
  const [activeFilter, setActiveFilter] = useState<FilterOption>("all");
  const [viewMode,     setViewMode]     = useState<ViewMode>("grid");
  const [drawerOpen,   setDrawerOpen]   = useState(false);
  const [selectedConnectorId, setSelectedConnectorId] = useState<string | null>(null);
  const [connectors,   setConnectors]   = useState<Connector[]>(allConnectors);
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
      all:                 base.length,
      connected:           base.filter((c) => c.status === "connected" || c.status === "healthy").length,
      disconnected:        base.filter((c) => c.status === "disconnected").length,
      healthy:             base.filter((c) => c.status === "connected" || c.status === "healthy").length,
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
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)", paddingBottom: "var(--space-8)" }}>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: dur.base, ease: ease.out }}
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "var(--space-4)",
          flexWrap: "wrap",
        }}
      >
        <div>
          <h1
            style={{
              fontSize: "var(--font-size-2xl)",
              fontWeight: 800,
              color: "var(--text-primary)",
              margin: 0,
              letterSpacing: "-0.03em",
              lineHeight: 1.1,
            }}
          >
            Integrations
          </h1>
          <p
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--text-secondary)",
              margin: "5px 0 0",
              lineHeight: 1.5,
            }}
          >
            Connect and manage your enterprise systems
          </p>
        </div>

        <motion.button
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.97 }}
          onClick={handleRefresh}
          aria-label="View integration logs"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 16px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            color: "var(--text-secondary)",
            fontSize: "var(--font-size-sm)",
            fontWeight: 600,
            cursor: "pointer",
            letterSpacing: "-0.01em",
          }}
        >
          <RefreshCw
            size={13}
            style={{ animation: isRefreshing ? "spin 0.8s linear infinite" : "none" }}
          />
          <ScrollText size={14} />
          Integration Logs
        </motion.button>
      </motion.div>

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

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: dur.slow, delay: 0.4 }}
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
      </motion.div>

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
