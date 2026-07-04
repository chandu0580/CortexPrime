"use client";

import { History } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function ApprovalTimeline() {
  return (
    <section>
      <SectionHeader
        title="Approval Timeline"
        subtitle="Review and approval history"
      />
      <EmptyState
        icon={<History className="h-8 w-8 text-[#D1D5DB]" />}
        title="No review history."
        description="Timeline events will appear after reviews are submitted."
        minHeight="min-h-[160px]"
        verticalPadding="py-10"
      />
    </section>
  );
}
