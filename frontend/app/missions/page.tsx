"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import MissionControlPage from "@/components/mission-control/MissionControlPage";
import { useAuthStore } from "@/store/authStore";

export default function MissionsPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fmissions");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <MissionControlPage />;
}