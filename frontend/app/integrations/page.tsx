"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import IntegrationCenter from "@/components/integration-hub/IntegrationCenter";

export default function IntegrationHubPage() {
  return (
    <AuthGuard>
      <IntegrationCenter />
    </AuthGuard>
  );
}
