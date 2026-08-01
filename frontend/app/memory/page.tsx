"use client";

import AuthGuard from "@/components/auth/AuthGuard";
import MemoryCenter from "@/components/memory-center/MemoryCenter";

export default function MemoryPage() {
  return (
    <AuthGuard>
      <MemoryCenter />
    </AuthGuard>
  );
}