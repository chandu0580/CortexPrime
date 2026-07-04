"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import IntegrationCenter from "@/components/integration-hub/IntegrationCenter";
import { useAuthStore } from "@/store/authStore";

export default function IntegrationHubPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fintegrations");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <IntegrationCenter />;
}
