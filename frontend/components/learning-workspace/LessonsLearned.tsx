"use client";

import { Bookmark } from "lucide-react";

import { EmptyState } from "@/components/mission-control/shared/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";

export default function LessonsLearned() {
  return (
    <section>
      <SectionHeader
        title="Lessons Learned"
        subtitle="Key takeaways from completed missions"
      />
      <EmptyState
        icon={<Bookmark className="h-10 w-10 text-[#D1D5DB]" />}
        title="No lessons recorded."
        description="Lessons will be captured automatically after mission completion and review."
      />
    </section>
  );
}
