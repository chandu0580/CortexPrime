"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import ExecutiveDashboard from "@/components/dashboard/ExecutiveDashboard";
import { useAuthStore } from "@/store/authStore";

export default function CommandPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fcommand");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <ExecutiveDashboard />;
}
