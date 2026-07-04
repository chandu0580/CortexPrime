"use client";

import { BrainCircuit } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function ReasoningOverview() {
  return (
    <section>
      <SectionHeader
        title="Reasoning Overview"
        subtitle="AI reasoning trace and decision logic"
      />
      <EmptyState
        icon={<BrainCircuit className="h-10 w-10 text-[#D1D5DB]" />}
        title="No reasoning available."
        description="Reasoning trace will appear once the AI evaluates the mission."
      />
    </section>
  );
}
