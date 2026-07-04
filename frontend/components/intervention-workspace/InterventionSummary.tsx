"use client";

import {
  AlertCircle,
  AlertTriangle,
  HelpCircle,
  CheckCircle,
  Activity,
} from "lucide-react";

import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";
import { cn } from "@/utils/cn";

const summaryItems = [
  {
    id: "open-interventions",
    label: "Open Interventions",
    icon: AlertCircle,
    placeholder: "\u2014",
    color: "text-[#F59E0B]",
  },
  {
    id: "critical-escalations",
    label: "Critical Escalations",
    icon: AlertTriangle,
    placeholder: "\u2014",
    color: "text-[#EF4444]",
  },
  {
    id: "awaiting-human",
    label: "Awaiting Human Input",
    icon: HelpCircle,
    placeholder: "\u2014",
    color: "text-[#6366F1]",
  },
  {
    id: "resolved-today",
    label: "Resolved Today",
    icon: CheckCircle,
    placeholder: "\u2014",
    color: "text-[#38B88A]",
  },
  {
    id: "intervention-health",
    label: "Intervention Health",
    icon: Activity,
    placeholder: "\u2014",
    color: "text-[#8B5CF6]",
  },
];

export default function InterventionSummary() {
  return (
    <section>
      <SectionHeader
        title="Intervention Summary"
        subtitle="Overview of active intervention status"
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
