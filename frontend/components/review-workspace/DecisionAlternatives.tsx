"use client";

import { GitCompare } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function DecisionAlternatives() {
  return (
    <section>
      <SectionHeader
        title="Decision Alternatives"
        subtitle="Comparison of available options"
      />
      <EmptyState
        icon={<GitCompare className="h-10 w-10 text-[#D1D5DB]" />}
        title="No alternatives available."
        description="Alternative decisions will be compared once analysis is complete."
      />
    </section>
  );
}
