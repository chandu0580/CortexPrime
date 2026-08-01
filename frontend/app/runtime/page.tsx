"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import RuntimeCenter from "@/components/runtime-center/RuntimeCenter";

export default function RuntimePage() {
  return (
    <AuthGuard>
      <RuntimeCenter />
    </AuthGuard>
  );
}