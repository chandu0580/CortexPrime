"use client";

import { ClipboardList } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function ContinuousImprovement() {
  return (
    <section>
      <SectionHeader
        title="Continuous Improvement"
        subtitle="Tracked improvement actions and progress"
      />
      <EmptyState
        icon={<ClipboardList className="h-10 w-10 text-[#D1D5DB]" />}
        title="No improvement actions."
        description="Improvement items will be generated from lessons learned and recommendations."
      />
    </section>
  );
}
