"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import ComputerUseCenter from "@/components/computer-use-center/ComputerUseCenter";

export default function OperatorPage() {
  return (
    <AuthGuard>
      <ComputerUseCenter />
    </AuthGuard>
  );
}