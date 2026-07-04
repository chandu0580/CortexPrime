"use client";

import { ThumbsUp, MessageCircle, ArrowUpRight } from "lucide-react";

import Button from "@/components/ui/Button";

export default function WorkspaceFooter() {
  return (
    <footer className="mt-8 flex items-center justify-end gap-4 border-t border-[#E5E7EB] pt-6">
      <Button
        variant="secondary"
        disabled
        leftIcon={<MessageCircle className="h-4 w-4" aria-hidden="true" />}
      >
        Request More Information
      </Button>
      <Button
        variant="secondary"
        disabled
        leftIcon={<ArrowUpRight className="h-4 w-4" aria-hidden="true" />}
      >
        Escalate
      </Button>
      <Button
        variant="primary"
        disabled
        leftIcon={<ThumbsUp className="h-4 w-4" aria-hidden="true" />}
      >
        Approve Recommendation
      </Button>
    </footer>
  );
}
