"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import ComputerUseCenter from "@/components/computer-use-center/ComputerUseCenter";
import { useAuthStore } from "@/store/authStore";

export default function OperatorPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Foperator");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <ComputerUseCenter />;
}