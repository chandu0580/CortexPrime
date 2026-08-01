"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import ExecutiveDashboard from "@/components/dashboard/ExecutiveDashboard";

export default function CommandPage() {
  return (
    <AuthGuard>
      <ExecutiveDashboard />
    </AuthGuard>
  );
}
