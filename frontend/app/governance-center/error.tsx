"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-4 p-8">
      <h2 className="text-lg font-semibold text-[#111827]">Something went wrong</h2>
      <button
        onClick={() => reset()}
        className="rounded-[18px] border border-[#38B88A] bg-[#38B88A] px-6 py-3 font-semibold text-white transition-colors hover:border-[#2F9F77] hover:bg-[#2F9F77]"
      >
        Try again
      </button>
    </div>
  );
}