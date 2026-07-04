"use client";

import { Route } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function EscalationPath() {
  return (
    <section>
      <SectionHeader
        title="Escalation Path"
        subtitle="Visual escalation routing and dependency chain"
      />
      <EmptyState
        icon={<Route className="h-10 w-10 text-[#D1D5DB]" />}
        title="No escalation path."
        description="Escalation routes will be visualized once an intervention is active."
      />
    </section>
  );
}
