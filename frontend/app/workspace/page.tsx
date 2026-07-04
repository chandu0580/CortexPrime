"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import ResearchCenter from "@/components/research-center/ResearchCenter";
import { useAuthStore } from "@/store/authStore";

export default function WorkspacePage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fworkspace");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <ResearchCenter />;
}