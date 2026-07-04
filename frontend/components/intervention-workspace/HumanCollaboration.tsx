"use client";

import { Users } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function HumanCollaboration() {
  return (
    <section>
      <SectionHeader
        title="Human Collaboration"
        subtitle="Discussion and coordination workspace"
      />
      <EmptyState
        icon={<Users className="h-10 w-10 text-[#D1D5DB]" />}
        title="No active collaboration."
        description="Discussion threads and coordination notes will appear here during active interventions."
        minHeight="min-h-[300px]"
        verticalPadding="py-16"
      />
    </section>
  );
}
