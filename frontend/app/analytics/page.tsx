"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import AnalyticsCenter from "@/components/analytics/AnalyticsCenter";

export default function AnalyticsPage() {
  return (
    <AuthGuard>
      <AnalyticsCenter />
    </AuthGuard>
  );
}
