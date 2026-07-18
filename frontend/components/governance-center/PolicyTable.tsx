"use client";

import { useState } from "react";
import { policiesData, PolicyData } from "./dashboardData";
import { Search, ChevronDown, Check, AlertTriangle, Play, HelpCircle, MoreVertical } from "lucide-react";
import StatusBadge from "./StatusBadge";

export default function PolicyTable() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All Categories");
  const [policies, setPolicies] = useState<PolicyData[]>(policiesData);

  const categories = ["All Categories", "Data Privacy", "Safety & Alignment", "Access Control", "Content Moderation", "Operational Trust", "Cost Control", "Compliance", "Security"];

  // Filter policies based on search and category
  const filteredPolicies = policies.filter((policy) => {
    const matchesSearch = policy.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          policy.category.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === "All Categories" || policy.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const handleToggleStatus = (id: string) => {
    setPolicies(prev =>
      prev.map(p => {
        if (p.id === id) {
          const nextStatus: PolicyData["status"] = 
            p.status === "active" ? "disabled" 
            : p.status === "disabled" ? "draft" 
            : "active";
          return { ...p, status: nextStatus };
        }
        return p;
      })
    );
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            Governance Policies
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Review core safety constraints, rate limits, and audit logs applied across active model workflows.
          </p>
        </div>

        {/* Search & Filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative inline-flex items-center rounded-xl border border-[#E5E7EB] bg-white px-3 py-1.5 shadow-sm">
            <Search className="mr-2 h-3.5 w-3.5 text-[#9CA3AF]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search policies..."
              className="text-xs font-medium text-[#111827] outline-none placeholder:text-[#9CA3AF] bg-transparent w-40"
            />
          </div>

          <div className="relative">
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="appearance-none rounded-xl border border-[#E5E7EB] bg-white pl-3.5 pr-8 py-2 text-xs font-semibold text-[#111827] shadow-sm outline-none cursor-pointer hover:bg-[#F9FAFB]"
            >
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-[#6B7280] pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Table container */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[#E5E7EB] pb-3 text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              <th scope="col" className="py-3 pl-4 pr-3">Policy Name</th>
              <th scope="col" className="px-3 py-3">Category</th>
              <th scope="col" className="px-3 py-3">Applies To</th>
              <th scope="col" className="px-3 py-3">Last Updated</th>
              <th scope="col" className="px-3 py-3 text-right">Compliance</th>
              <th scope="col" className="px-3 py-3 text-center">Status</th>
              <th scope="col" className="py-3 pl-3 pr-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB] font-medium text-[#111827]">
            {filteredPolicies.map((policy) => {
              return (
                <tr key={policy.id} className="transition-colors hover:bg-[#F8FAFC]">
                  <td className="whitespace-nowrap py-4 pl-4 pr-3">
                    <div className="flex flex-col">
                      <span className="font-bold text-[#111827]">{policy.name}</span>
                      <span className="text-[10px] text-[#6B7280] mt-0.5">ID: {policy.id}</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-xs font-bold text-[#6B7280]">
                    {policy.category}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-xs text-[#111827]">
                    {policy.appliesTo}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-xs text-[#6B7280]">
                    {policy.lastUpdated}
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <span className={`text-xs font-bold ${policy.compliance === 100 ? "text-[#2F9F77]" : "text-[#B45309]"}`}>
                        {policy.compliance}%
                      </span>
                      <div className="h-1.5 w-16 rounded-full bg-[#F3F4F6] overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${policy.compliance === 100 ? "bg-[#38B88A]" : "bg-[#F59E0B]"}`} 
                          style={{ width: `${policy.compliance}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-4 text-center">
                    <StatusBadge status={policy.status}>{policy.status}</StatusBadge>
                  </td>
                  <td className="whitespace-nowrap py-4 pl-3 pr-4 text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      <button 
                        onClick={() => handleToggleStatus(policy.id)}
                        className="rounded-lg border border-[#E5E7EB] bg-white px-2.5 py-1 text-[10px] font-bold text-[#374151] hover:bg-[#F9FAFB] active:scale-[0.98]"
                        title="Toggle Status"
                      >
                        {policy.status === "active" ? "Deactivate" : "Activate"}
                      </button>
                      <button className="rounded-lg p-1 text-[#6B7280] hover:bg-[#F3F4F6] hover:text-[#111827]">
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}

            {filteredPolicies.length === 0 && (
              <tr>
                <td colSpan={7} className="py-8 text-center text-xs font-semibold text-[#6B7280]">
                  No policies match your search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
