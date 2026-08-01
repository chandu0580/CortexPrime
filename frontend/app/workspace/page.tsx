"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import ResearchCenter from "@/components/research-center/ResearchCenter";

export default function WorkspacePage() {
  return (
    <AuthGuard>
      <ResearchCenter />
    </AuthGuard>
  );
}