"use client";

import { ListOrdered } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function ActiveInterventionQueue() {
  return (
    <section>
      <SectionHeader
        title="Active Intervention Queue"
        subtitle="Pending interventions requiring attention"
      />
      <EmptyState
        icon={<ListOrdered className="h-10 w-10 text-[#D1D5DB]" />}
        title="No active interventions."
        description="Intervention requests will appear here when the AI requires assistance."
      />
    </section>
  );
}
