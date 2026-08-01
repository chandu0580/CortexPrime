"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import { MissionControlShell } from "@/components/mission-control/MissionControlShell";

export default function LearningPage() {
  return (
    <AuthGuard>
      <MissionControlShell initialWorkspace="learning" />
    </AuthGuard>
  );
}
