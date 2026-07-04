"use client";

import { MessageSquare, Target, Crosshair, Flag, Lightbulb } from "lucide-react";

import GlassPanel from "@/components/ui/GlassPanel";
import SectionHeader from "@/components/ui/SectionHeader";

const detailFields = [
  { id: "reason", label: "Reason", icon: MessageSquare },
  { id: "requested-action", label: "Requested Action", icon: Target },
  { id: "affected-mission", label: "Affected Mission", icon: Crosshair },
  { id: "priority", label: "Priority", icon: Flag },
  { id: "suggested-resolution", label: "Suggested Resolution", icon: Lightbulb },
];

export default function InterventionDetails() {
  return (
    <section>
      <SectionHeader
        title="Intervention Details"
        subtitle="Full context for the active intervention request"
      />
      <GlassPanel className="divide-y divide-[#F3F4F6]">
        {detailFields.map((field) => (
          <div
            key={field.id}
            className="flex items-start gap-4 px-6 py-4"
          >
            <div className="rounded-lg bg-[#F9FAFB] p-2 text-[#6B7280]">
              <field.icon className="h-4 w-4" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-[#6B7280]">
                {field.label}
              </p>
              <p className="mt-0.5 text-sm text-[#D1D5DB]">
                No intervention selected.
              </p>
            </div>
          </div>
        ))}
      </GlassPanel>
    </section>
  );
}
