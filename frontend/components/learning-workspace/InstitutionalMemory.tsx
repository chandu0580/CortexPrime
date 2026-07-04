"use client";

import { Database } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function InstitutionalMemory() {
  return (
    <section>
      <SectionHeader
        title="Institutional Memory"
        subtitle="Searchable organizational knowledge base"
      />
      <EmptyState
        icon={<Database className="h-10 w-10 text-[#D1D5DB]" />}
        title="No institutional memory available."
        description="Organizational knowledge will be indexed and searchable after missions are completed and published."
        minHeight="min-h-[300px]"
        verticalPadding="py-16"
      />
    </section>
  );
}
