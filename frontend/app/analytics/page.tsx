"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import AnalyticsCenter from "@/components/analytics/AnalyticsCenter";
import { useAuthStore } from "@/store/authStore";

export default function AnalyticsPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fanalytics");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <AnalyticsCenter />;
}
