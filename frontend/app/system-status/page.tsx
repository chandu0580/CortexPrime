"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import MonitoringCenter from "@/components/monitoring-center/MonitoringCenter";

export default function SystemStatusPage() {
  return (
    <AuthGuard>
      <MonitoringCenter />
    </AuthGuard>
  );
}
