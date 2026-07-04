"use client";

import {
  Lightbulb,
  ArrowLeftRight,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";

import Card from "@/components/ui/Card";
import SectionHeader from "@/components/ui/SectionHeader";

const supportItems = [
  { id: "ai-recommendation", label: "AI Recommendation", icon: Lightbulb },
  { id: "alternative-options", label: "Alternative Options", icon: ArrowLeftRight },
  { id: "confidence", label: "Confidence", icon: ShieldCheck },
  { id: "expected-impact", label: "Expected Impact", icon: TrendingUp },
];

export default function DecisionSupport() {
  return (
    <section>
      <SectionHeader
        title="Decision Support"
        subtitle="AI-generated recommendations and analysis"
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {supportItems.map((item) => (
          <Card key={item.id} className="p-5">
            <div className="mb-3 flex items-center gap-3">
              <div className="rounded-lg bg-[#F9FAFB] p-2 text-[#6B7280]">
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
