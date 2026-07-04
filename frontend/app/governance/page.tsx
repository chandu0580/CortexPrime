"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import GovernanceCenter from "@/components/governance/GovernanceCenter";
import { useAuthStore } from "@/store/authStore";

export default function GovernancePage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fgovernance");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <GovernanceCenter />;
}