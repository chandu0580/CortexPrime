"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { connectedIntegrations, ConnectedIntegration } from "./mockData";
import { variants } from "@/lib/motion-tokens";
import { Settings, RefreshCw, FileText, Trash2, Search, SlidersHorizontal } from "lucide-react";
import StatusBadge, { IntegrationStatusType } from "./StatusBadge";

// Custom SVG Logo Renderer for each integration
const ServiceLogo = ({ name }: { name: string }) => {
  const normName = name.toLowerCase();

  if (normName.includes("slack")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#4A154B" />
        <path d="M30 45a6 6 0 11-6-6h6v6zm8 0a6 6 0 016-6h14a6 6 0 110 12H44a6 6 0 01-6-6z" fill="#FFF" />
        <path d="M55 30a6 6 0 116-6v6h-6zm0 8a6 6 0 016 6v14a6 6 0 11-12 0V44a6 6 0 016-6z" fill="#FFF" />
        <path d="M70 55a6 6 0 116 6h-6v-6zm-8 0a6 6 0 01-6 6H48a6 6 0 110-12h14a6 6 0 016 6z" fill="#FFF" />
        <path d="M45 70a6 6 0 11-6 6v-6h6zm0-8a6 6 0 01-6-6V42a6 6 0 1112 0v14a6 6 0 01-6 6z" fill="#FFF" />
      </svg>
    );
  }
  if (normName.includes("microsoft 365") || normName.includes("teams")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#0078D4" />
        <path d="M30 30h18v18H30zm22 0h18v18H52zM30 52h18v18H30zm22 0h18v18H52z" fill="#FFF" />
      </svg>
    );
  }
  if (normName.includes("google")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#EA4335" />
        <path d="M50 30c11 0 20 9 20 20S61 70 50 70 30 61 30 50s9-20 20-20z" fill="#FFF" />
        <path d="M50 42v16h12c-1.5 4-5 6-12 6-8 0-14-6-14-14s6-14 14-14c6 0 10 3 12 7l11-6C68 33 60 30 50 30 33 30 20 43 20 60s13 30 30 30c17 0 29-12 29-30v-8H50z" fill="#4285F4" />
      </svg>
    );
  }
  if (normName.includes("github")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#24292E" />
        <path fillRule="evenodd" clipRule="evenodd" d="M50 20C33.4 20 20 33.4 20 50c0 13.3 8.6 24.6 20.6 28.6 1.5.3 2.1-.6 2.1-1.4 0-.7 0-2.6-.1-5.1-8.3 1.8-10.1-4-10.1-4-1.4-3.5-3.3-4.4-3.3-4.4-2.7-1.9.2-1.8.2-1.8 3 .2 4.6 3.1 4.6 3.1 2.7 4.6 7 3.3 8.7 2.5.3-2 .1-3.3-1-4.1-6.7-.8-13.7-3.3-13.7-14.9 0-3.3 1.2-6 3.1-8.1-.3-.8-1.3-3.8.3-8 0 0 2.5-.8 8.3 3.1a28.8 28.8 0 0115 0c5.7-3.9 8.2-3.1 8.2-3.1 1.6 4.1.6 7.2.3 8 1.9 2.1 3.1 4.8 3.1 8.1 0 11.6-7 14.1-13.7 14.8 1.1.9 2.1 2.8 2.1 5.7 0 4.1 0 7.4-.1 8.4 0 .8.6 1.7 2.1 1.4C71.4 74.6 80 63.3 80 50c0-16.6-13.4-30-30-30z" fill="#FFF" />
      </svg>
    );
  }
  if (normName.includes("gitlab")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#E24329" />
        <path d="M50 78L22 57l9-28 19 49z" fill="#FC6D26" />
        <path d="M50 78l28-21-9-28-19 49z" fill="#FC6D26" />
        <path d="M50 78L31 29h38L50 78z" fill="#E24329" />
        <path d="M31 29l-9 28 9-28z" fill="#FCA326" />
        <path d="M69 29l9 28-9-28z" fill="#FCA326" />
      </svg>
    );
  }
  if (normName.includes("jira") || normName.includes("confluence")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#0052CC" />
        <path d="M50 25L30 45h40L50 25zm0 50L30 55h40L50 75z" fill="#FFF" />
      </svg>
    );
  }
  if (normName.includes("salesforce")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#00A1E0" />
        <path d="M64 45c0-6-5-10-10-10-3 0-5 1-7 3-2-3-6-4-10-4-7 0-13 5-13 12 0 1 .1 2 .2 3-3 1-5 4-5 7 0 5 4 8 9 8h36c6 0 10-4 10-9 0-4-3-7-7-8z" fill="#FFF" />
      </svg>
    );
  }
  if (normName.includes("sap")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#008FD3" />
        <path d="M30 40h15v20H30zM55 40h15v20H55z" fill="#FFF" />
      </svg>
    );
  }
  if (normName.includes("aws")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#FF9900" />
        <path d="M30 45c4-4 10-6 16-6s12 2 16 6l-6 6c-3-3-6-4-10-4s-7 1-10 4l-6-6z" fill="#FFF" />
        <path d="M35 60c8 5 18 5 26 0l4 8c-10 7-24 7-34 0l4-8z" fill="#232F3E" />
      </svg>
    );
  }
  if (normName.includes("azure")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#0078D4" />
        <path d="M50 25L25 65h15l10-20 10 20h15L50 25z" fill="#FFF" />
      </svg>
    );
  }
  if (normName.includes("openai") || normName.includes("deepgram")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#10A37F" />
        <path d="M50 30c-11 0-20 9-20 20s9 20 20 20 20-9 20-20-9-20-20-20zm0 30c-5.5 0-10-4.5-10-10s4.5-10 10-10 10 4.5 10 10-4.5 10-10 10z" fill="#FFF" />
      </svg>
    );
  }
  if (normName.includes("postgres") || normName.includes("redis")) {
    return (
      <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
        <rect width="100" height="100" rx="20" fill="#336791" />
        <path d="M50 25C36 25 25 36 25 50s11 25 25 25 25-11 25-25-11-25-25-25zm0 40c-8.3 0-15-6.7-15-15s6.7-15 15-15 15 6.7 15 15-6.7 15-15 15z" fill="#FFF" />
      </svg>
    );
  }

  // Fallback default logo
  return (
    <svg className="h-7 w-7" viewBox="0 0 100 100" fill="none">
      <rect width="100" height="100" rx="20" fill="#6B7280" />
      <path d="M50 30v40M30 50h40" stroke="#FFF" strokeWidth="10" strokeLinecap="round" />
    </svg>
  );
};

export default function IntegrationCard() {
  const [integrationsList, setIntegrationsList] = useState<ConnectedIntegration[]>(connectedIntegrations);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");

  const categories = ["All", "Productivity", "Communication", "Development", "Project Management", "Knowledge", "CRM", "ERP", "Cloud", "AI Providers", "Databases"];

  const handleDisconnect = (id: string) => {
    // Soft deletion with motion exit transition
    setIntegrationsList(prev => prev.filter(item => item.id !== id));
  };

  const handleReconnect = (id: string) => {
    // Find original element and reset its status
    const original = connectedIntegrations.find(item => item.id === id);
    if (original) {
      setIntegrationsList(prev => {
        if (prev.some(item => item.id === id)) return prev;
        return [...prev, { ...original, connectionStatus: "healthy", authStatus: "verified" }];
      });
    }
  };

  // Filter logic
  const filtered = integrationsList.filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          item.category.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === "All" || item.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="space-y-6">
      {/* Search & Category Filter Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-[20px] border border-[#E5E7EB] bg-white p-4 shadow-[0_2px_10px_rgba(0,0,0,0.01)]">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6B7280]" />
          <input
            type="text"
            placeholder="Search active integrations by name or category..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-[#E5E7EB] bg-[#F8FAFC] py-2 pl-10 pr-4 text-xs font-semibold text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#38B88A]/80 focus:bg-white"
          />
        </div>

        {/* Category filters */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          <SlidersHorizontal className="h-3.5 w-3.5 text-[#6B7280] hidden md:block" />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="rounded-xl border border-[#E5E7EB] bg-[#F8FAFC] px-3.5 py-2 text-xs font-bold text-[#111827] outline-none cursor-pointer focus:border-[#38B88A]/80"
          >
            {categories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Grid of integrations */}
      <motion.div
        layout
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
      >
        <AnimatePresence mode="popLayout">
          {filtered.map((integration, index) => {
            const isCritical = integration.connectionStatus === "critical";
            const isWarning = integration.connectionStatus === "warning";

            const cardBorder = isCritical
              ? "border-red-200 hover:border-red-400/40"
              : isWarning
              ? "border-amber-200 hover:border-amber-400/40"
              : "border-[#E5E7EB] hover:border-[#38B88A]/40";

            return (
              <motion.div
                key={integration.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9, y: 15 }}
                transition={{ duration: 0.25 }}
                whileHover={variants.cardHover}
                className={`flex flex-col justify-between rounded-[24px] border bg-white p-5 shadow-[0_8px_30px_rgb(0,0,0,0.01)] transition-all duration-200 ${cardBorder}`}
              >
                {/* Header: Logo, Name, Category */}
                <div>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <ServiceLogo name={integration.name} />
                      <div>
                        <h4 className="text-sm font-extrabold text-[#111827] leading-tight">
                          {integration.name}
                        </h4>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">
                          {integration.category}
                        </span>
                      </div>
                    </div>
                    <StatusBadge status={integration.connectionStatus as IntegrationStatusType}>
                      {integration.connectionStatus}
                    </StatusBadge>
                  </div>

                  {/* Auth Status & Sync Info */}
                  <div className="mt-4 flex flex-col gap-2 border-t border-[#F3F4F6] pt-3 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[#6B7280]">Auth Status</span>
                      <StatusBadge status={integration.authStatus as IntegrationStatusType} className="py-0 px-2 text-[10px]">
                        {integration.authStatus}
                      </StatusBadge>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[#6B7280]">Last Synchronized</span>
                      <span className="font-bold text-[#111827]">{integration.lastSync}</span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[#6B7280]">Version</span>
                      <span className="font-mono text-[10px] text-[#6B7280]">{integration.version}</span>
                    </div>
                  </div>
                </div>

                {/* Grid Action Controls */}
                <div className="mt-5 grid grid-cols-2 gap-2 border-t border-[#F3F4F6] pt-3">
                  <button
                    className="inline-flex items-center justify-center gap-1 rounded-xl border border-[#E5E7EB] bg-white py-2 text-[10px] font-bold text-[#6B7280] hover:bg-[#F9FAFB] hover:text-[#111827] transition-colors"
                    title="Configure details"
                  >
                    <Settings className="h-3 w-3" />
                    Configure
                  </button>

                  <button
                    onClick={() => handleReconnect(integration.id)}
                    className="inline-flex items-center justify-center gap-1 rounded-xl border border-[#E5E7EB] bg-white py-2 text-[10px] font-bold text-[#6B7280] hover:bg-[#F9FAFB] hover:text-[#111827] transition-colors"
                    title="Reconnect interface"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Reconnect
                  </button>

                  <button
                    className="inline-flex items-center justify-center gap-1 rounded-xl border border-[#E5E7EB] bg-white py-2 text-[10px] font-bold text-[#6B7280] hover:bg-[#F9FAFB] hover:text-[#111827] transition-colors"
                    title="View access logs"
                  >
                    <FileText className="h-3 w-3" />
                    Logs
                  </button>

                  <button
                    onClick={() => handleDisconnect(integration.id)}
                    className="inline-flex items-center justify-center gap-1 rounded-xl border border-red-100 bg-red-50 py-2 text-[10px] font-bold text-[#B91C1C] hover:bg-red-100 hover:text-red-700 transition-colors"
                    title="Disconnect integration link"
                  >
                    <Trash2 className="h-3 w-3" />
                    Disconnect
                  </button>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </motion.div>

      {/* Empty State when no integrations match filter */}
      {filtered.length === 0 && (
        <div className="text-center py-12 rounded-[24px] border border-[#E5E7EB] bg-white">
          <p className="text-sm font-semibold text-[#6B7280]">No integrations found matching your filters.</p>
          <button
            onClick={() => { setSearchQuery(""); setSelectedCategory("All"); setIntegrationsList(connectedIntegrations); }}
            className="mt-3 text-xs font-bold text-[#38B88A] hover:underline"
          >
            Clear Search & Filters
          </button>
        </div>
      )}
    </div>
  );
}
