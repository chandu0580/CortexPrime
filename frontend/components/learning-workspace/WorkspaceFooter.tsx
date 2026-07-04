"use client";

import { Upload, FilePlus, Share2 } from "lucide-react";

import Button from "@/components/ui/Button";

export default function WorkspaceFooter() {
  return (
    <footer className="mt-8 flex items-center justify-end gap-4 border-t border-[#E5E7EB] pt-6">
      <Button
        variant="secondary"
        disabled
        leftIcon={<FilePlus className="h-4 w-4" aria-hidden="true" />}
      >
        Create Template
      </Button>
      <Button
        variant="secondary"
        disabled
        leftIcon={<Share2 className="h-4 w-4" aria-hidden="true" />}
      >
        Share Knowledge
      </Button>
      <Button
        variant="primary"
        disabled
        leftIcon={<Upload className="h-4 w-4" aria-hidden="true" />}
      >
        Publish Learning
      </Button>
    </footer>
  );
}
