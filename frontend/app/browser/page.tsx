"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import BrowserCenter from "@/components/browser-center/BrowserCenter";
import { useAuthStore } from "@/store/authStore";

export default function BrowserPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login?next=%2Fbrowser");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <BrowserCenter />;
}
