"use client";

import { FileText, BookOpen, BarChart3, Eye } from "lucide-react";

import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";

const evidenceItems = [
  { id: "documents", label: "Documents", icon: FileText },
  { id: "knowledge", label: "Knowledge", icon: BookOpen },
  { id: "metrics", label: "Metrics", icon: BarChart3 },
  { id: "observations", label: "Observations", icon: Eye },
];

export default function EvidencePanel() {
  return (
    <section>
      <SectionHeader
        title="Evidence Panel"
        subtitle="Supporting data and sources"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {evidenceItems.map((item) => (
          <Card key={item.id} className="p-5">
            <div className="mb-3 flex items-center gap-3">
              <div className="rounded-lg bg-[#F9FAFB] p-2 text-[#6B7280]">
                <item.icon className="h-4 w-4" />
              </div>
              <span className="text-sm font-medium text-[#6B7280]">
                {item.label}
              </span>
            </div>
            <p className="text-sm text-[#D1D5DB]">No evidence loaded.</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
