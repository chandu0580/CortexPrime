"use client";

import GlassPanel from "@/components/ui/GlassPanel";
import SectionHeader from "@/components/ui/SectionHeader";

export default function ReviewerNotes() {
  return (
    <section>
      <SectionHeader
        title="Reviewer Notes"
        subtitle="Reviewer observations and comments"
      />
      <GlassPanel className="p-6">
        <textarea
          className="h-full min-h-[260px] w-full resize-none border-none bg-transparent text-sm text-[#6B7280] placeholder:text-[#D1D5DB] focus:outline-none"
          placeholder="Add your review notes here..."
          disabled
        />
      </GlassPanel>
    </section>
  );
}
