"use client";

import { FileText, Swords, LayoutTemplate, Compass } from "lucide-react";

import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";

const assetItems = [
  { id: "documents", label: "Documents", icon: FileText },
  { id: "playbooks", label: "Playbooks", icon: Swords },
  { id: "templates", label: "Templates", icon: LayoutTemplate },
  { id: "decision-guides", label: "Decision Guides", icon: Compass },
];

export default function KnowledgeAssets() {
  return (
    <section>
      <SectionHeader
        title="Knowledge Assets"
        subtitle="Reusable organizational artifacts"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {assetItems.map((item) => (
          <Card key={item.id} className="p-5">
            <div className="mb-3 flex items-center gap-3">
              <div className="rounded-lg bg-[#F9FAFB] p-2 text-[#6B7280]">
                <item.icon className="h-4 w-4" />
              </div>
              <span className="text-sm font-medium text-[#6B7280]">
                {item.label}
              </span>
            </div>
            <p className="text-sm text-[#D1D5DB]">No content.</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
