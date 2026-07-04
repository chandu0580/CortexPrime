"use client";

import { CandlestickChart } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function PatternsInsights() {
  return (
    <section>
      <SectionHeader
        title="Patterns & Insights"
        subtitle="Identified trends and recurring patterns"
      />
      <EmptyState
        icon={<CandlestickChart className="h-10 w-10 text-[#D1D5DB]" />}
        title="No patterns identified."
        description="Pattern analysis will run after sufficient mission data is collected."
      />
    </section>
  );
}
