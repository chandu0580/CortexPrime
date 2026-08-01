"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import GovernanceCenter from "@/components/governance/GovernanceCenter";

export default function GovernancePage() {
  return (
    <AuthGuard>
      <GovernanceCenter />
    </AuthGuard>
  );
}