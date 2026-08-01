"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import { MissionControlShell } from "@/components/mission-control/MissionControlShell";

export default function InterventionPage() {
  return (
    <AuthGuard>
      <MissionControlShell initialWorkspace="intervention" />
    </AuthGuard>
  );
}
