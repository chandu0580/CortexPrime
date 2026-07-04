"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import MemoryCenter from "@/components/memory-center/MemoryCenter";
import { useAuthStore } from "@/store/authStore";

export default function MemoryPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fmemory");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <MemoryCenter />;
}