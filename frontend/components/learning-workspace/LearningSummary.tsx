"use client";

import {
  CheckCircle,
  BookOpen,
  Sparkles,
  Lightbulb,
  Activity,
} from "lucide-react";

import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";
import { cn } from "@/utils/cn";

const summaryItems = [
  {
    id: "completed-missions",
    label: "Completed Missions",
    icon: CheckCircle,
    placeholder: "\u2014",
    color: "text-[#38B88A]",
  },
  {
    id: "knowledge-assets",
    label: "Knowledge Assets",
    icon: BookOpen,
    placeholder: "\u2014",
    color: "text-[#6366F1]",
  },
  {
    id: "patterns-identified",
    label: "Patterns Identified",
    icon: Sparkles,
    placeholder: "\u2014",
    color: "text-[#F59E0B]",
  },
  {
    id: "recommendations",
    label: "Recommendations",
    icon: Lightbulb,
    placeholder: "\u2014",
    color: "text-[#8B5CF6]",
  },
  {
    id: "learning-health",
    label: "Learning Health",
    icon: Activity,
    placeholder: "\u2014",
    color: "text-[#38B88A]",
  },
];

export default function LearningSummary() {
  return (
    <section>
      <SectionHeader
        title="Learning Summary"
        subtitle="Organizational knowledge capture overview"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {summaryItems.map((item) => (
          <Card key={item.id} className="p-5">
            <div className="mb-3 flex items-center gap-3">
              <div className={cn("rounded-lg bg-[#F9FAFB] p-2", item.color)}>
                <item.icon className="h-4 w-4" />
              </div>
              <span className="text-sm font-medium text-[#6B7280]">
                {item.label}
              </span>
            </div>
            <p className="text-2xl font-semibold text-[#111827]">
              {item.placeholder}
            </p>
          </Card>
        ))}
      </div>
    </section>
  );
}
