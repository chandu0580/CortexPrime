"use client";

import {
  AlertTriangle,
  TrendingDown,
  ShieldAlert,
  FileWarning,
} from "lucide-react";

import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";
import { cn } from "@/utils/cn";

const riskItems = [
  {
    id: "risk",
    label: "Risk",
    icon: AlertTriangle,
    color: "text-[#EF4444]",
  },
  {
    id: "business-impact",
    label: "Business Impact",
    icon: TrendingDown,
    color: "text-[#F59E0B]",
  },
  {
    id: "confidence",
    label: "Confidence",
    icon: ShieldAlert,
    color: "text-[#6366F1]",
  },
  {
    id: "policy-impact",
    label: "Policy Impact",
    icon: FileWarning,
    color: "text-[#8B5CF6]",
  },
];

export default function RiskImpact() {
  return (
    <section>
      <SectionHeader
        title="Risk & Impact"
        subtitle="Enterprise risk assessment and policy implications"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {riskItems.map((item) => (
          <Card key={item.id} className="p-5">
            <div className="mb-3 flex items-center gap-3">
              <div className={cn("rounded-lg bg-[#F9FAFB] p-2", item.color)}>
                <item.icon className="h-4 w-4" />
              </div>
              <span className="text-sm font-medium text-[#6B7280]">
                {item.label}
              </span>
            </div>
            <p className="text-sm text-[#D1D5DB]">No calculations.</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
