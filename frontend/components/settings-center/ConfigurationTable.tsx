"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { initialApiKeys, APIKeyRow } from "./dashboardData";
import { Key, RefreshCw, AlertTriangle, ShieldCheck, Clipboard, Plus, Trash2 } from "lucide-react";
import StatusBadge, { SettingsStatusType } from "./StatusBadge";

export default function ConfigurationTable() {
  const [keys, setKeys] = useState<APIKeyRow[]>(initialApiKeys);
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);

  const handleGenerateKey = () => {
    const newKey: APIKeyRow = {
      id: `key-${Date.now()}`,
      name: `Agent Key ${keys.length + 1}`,
      type: "Developer Access",
      created: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
      expires: "Never",
      status: "Active",
    };
    setKeys(prev => [...prev, newKey]);
  };

  const handleRotate = (id: string) => {
    setKeys(prev =>
      prev.map(k => {
        if (k.id === id) {
          const freshExpiry = new Date();
          freshExpiry.setMonth(freshExpiry.getMonth() + 6);
          return {
            ...k,
            created: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
            expires: freshExpiry.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
            status: "Active",
          };
        }
        return k;
      })
    );
  };

  const handleRevoke = (id: string) => {
    setKeys(prev =>
      prev.map(k => (k.id === id ? { ...k, status: "Revoked" as const } : k))
    );
  };

  const handleCopy = (id: string) => {
    setCopiedKeyId(id);
    navigator.clipboard.writeText(`cx_live_token_key_${id.replace("key-", "")}`);
    setTimeout(() => setCopiedKeyId(null), 1500);
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      {/* Header and Generate Key Trigger */}
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            API Keys & Access Tokens
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Generate and manage security tokens used to connect CLI tools, agents, and external scripts.
          </p>
        </div>

        <button
          onClick={handleGenerateKey}
          className="inline-flex items-center rounded-xl bg-[#38B88A] px-3.5 py-2 text-xs font-bold text-white shadow-[0_4px_14px_rgba(56,184,138,0.25)] transition-all hover:bg-[#2F9F77] hover:shadow-[0_6px_16px_rgba(56,184,138,0.3)] active:scale-[0.98] focus:outline-none"
        >
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          Generate Key
        </button>
      </div>

      {/* Keys list table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[#E5E7EB] pb-3 text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              <th scope="col" className="py-3.5 pl-4 pr-3">Key Name</th>
              <th scope="col" className="px-3 py-3.5">Access Type</th>
              <th scope="col" className="px-3 py-3.5 text-right">Created</th>
              <th scope="col" className="px-3 py-3.5 text-right">Expires</th>
              <th scope="col" className="px-3 py-3.5 text-center">Status</th>
              <th scope="col" className="py-3.5 pl-3 pr-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB] font-medium text-[#111827]">
            <AnimatePresence initial={false}>
              {keys.map((k) => {
                const isActive = k.status === "Active";

                return (
                  <motion.tr
                    key={k.id}
                    layoutId={k.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, x: -10 }}
                    className="transition-colors hover:bg-[#F8FAFC]"
                  >
                    {/* Name */}
                    <td className="whitespace-nowrap py-4 pl-4 pr-3">
                      <div className="flex items-center gap-2.5 text-xs font-bold text-[#111827]">
                        <Key className="h-3.5 w-3.5 text-[#6B7280]" />
                        <span>{k.name}</span>
                      </div>
                    </td>

                    {/* Type */}
                    <td className="whitespace-nowrap px-3 py-4 text-xs text-[#6B7280]">
                      {k.type}
                    </td>

                    {/* Created */}
                    <td className="whitespace-nowrap px-3 py-4 text-right text-xs text-[#6B7280]">
                      {k.created}
                    </td>

                    {/* Expires */}
                    <td className="whitespace-nowrap px-3 py-4 text-right text-xs text-[#6B7280]">
                      {k.expires}
                    </td>

                    {/* Status */}
                    <td className="whitespace-nowrap px-3 py-4 text-center">
                      <StatusBadge status={k.status as SettingsStatusType}>{k.status}</StatusBadge>
                    </td>

                    {/* Actions */}
                    <td className="whitespace-nowrap py-4 pl-3 pr-4 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        {/* Copy */}
                        <button
                          onClick={() => handleCopy(k.id)}
                          disabled={!isActive}
                          className="rounded-lg p-1.5 text-[#6B7280] hover:bg-[#F3F4F6] disabled:opacity-40"
                          title="Copy API secret value"
                        >
                          <Clipboard className={`h-3.5 w-3.5 ${copiedKeyId === k.id ? "text-[#38B88A]" : ""}`} />
                        </button>

                        {/* Rotate */}
                        <button
                          onClick={() => handleRotate(k.id)}
                          disabled={!isActive}
                          className="rounded-lg p-1.5 text-[#6B7280] hover:bg-[#F3F4F6] disabled:opacity-40"
                          title="Rotate key expiration"
                        >
                          <RefreshCw className="h-3.5 w-3.5" />
                        </button>

                        {/* Revoke */}
                        <button
                          onClick={() => handleRevoke(k.id)}
                          disabled={!isActive}
                          className="rounded-lg px-2 py-1 text-[10px] font-extrabold border border-red-100 bg-red-50 text-[#B91C1C] hover:bg-red-100 disabled:opacity-40"
                          title="Revoke key access"
                        >
                          Revoke
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </div>
  );
}
