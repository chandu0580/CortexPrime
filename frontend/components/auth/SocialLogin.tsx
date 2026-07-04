import { Building2 } from "lucide-react";

import Button from "@/components/ui/Button";

function GoogleMark() {
  return (
    <span className="flex h-7 w-7 items-center justify-center rounded-[10px] border border-[#E5E7EB] bg-[#F9FAFB] text-[0.92rem] font-semibold text-[#111827]">
      G
    </span>
  );
}

function MicrosoftMark() {
  return (
    <span className="grid h-7 w-7 grid-cols-2 gap-[2px] rounded-[10px] border border-[#E5E7EB] bg-[#F9FAFB] p-[5px]">
      <span className="rounded-[2px] bg-[#111827]" />
      <span className="rounded-[2px] bg-[#111827]" />
      <span className="rounded-[2px] bg-[#111827]" />
      <span className="rounded-[2px] bg-[#111827]" />
    </span>
  );
}

export default function SocialLogin() {
  return (
    <div className="space-y-3">
      <Button variant="secondary" size="md" leftIcon={<GoogleMark />} aria-label="Continue with Google">
        Continue with Google
      </Button>
      <Button
        variant="secondary"
        size="md"
        leftIcon={<MicrosoftMark />}
        rightIcon={<Building2 className="h-4 w-4 text-[#9CA3AF]" aria-hidden="true" />}
        aria-label="Continue with Microsoft"
      >
        Continue with Microsoft
      </Button>
    </div>
  );
}
