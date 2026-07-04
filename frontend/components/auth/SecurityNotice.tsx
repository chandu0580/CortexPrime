import { LockKeyhole } from "lucide-react";

export default function SecurityNotice() {
  return (
    <div className="flex items-start gap-3 rounded-[18px] border border-[#EAF2EE] bg-[#FCFDFC] px-4 py-3 text-[0.9rem] leading-7 text-[#6B7280]">
      <LockKeyhole className="mt-1 h-4 w-4 shrink-0 text-[#38B88A]" aria-hidden="true" />
      <p>
        Your session is protected using enterprise-grade authentication and encrypted communication.
      </p>
    </div>
  );
}
