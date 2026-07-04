"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import MonitoringCenter from "@/components/monitoring-center/MonitoringCenter";
import { useAuthStore } from "@/store/authStore";

export default function SystemStatusPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fsystem-status");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <MonitoringCenter />;
}
