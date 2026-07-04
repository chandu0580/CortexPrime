"use client";

import { Clock } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function ResolutionHistory() {
  return (
    <section>
      <SectionHeader
        title="Resolution History"
        subtitle="Past interventions and outcomes"
      />
      <EmptyState
        icon={<Clock className="h-8 w-8 text-[#D1D5DB]" />}
        title="No intervention history."
        description="Historical records will appear after interventions are completed."
        minHeight="min-h-[160px]"
        verticalPadding="py-10"
      />
    </section>
  );
}
