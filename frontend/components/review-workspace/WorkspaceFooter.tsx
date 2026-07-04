"use client";

import { CheckCircle, RotateCcw, XCircle } from "lucide-react";

import Button from "@/components/ui/Button";

export default function WorkspaceFooter() {
  return (
    <footer className="mt-8 flex items-center justify-end gap-4 border-t border-[#E5E7EB] pt-6">
      <Button
        variant="secondary"
        disabled
        leftIcon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}
      >
        Request Changes
      </Button>
      <Button
        variant="secondary"
        disabled
        leftIcon={<XCircle className="h-4 w-4" aria-hidden="true" />}
      >
        Reject
      </Button>
      <Button
        variant="primary"
        disabled
        leftIcon={<CheckCircle className="h-4 w-4" aria-hidden="true" />}
      >
        Approve
      </Button>
    </footer>
  );
}
