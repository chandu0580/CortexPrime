import { Check } from "lucide-react";
import type { InputHTMLAttributes } from "react";

import { cn } from "@/utils/cn";

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: string;
};

export default function Checkbox({ label, className, id, ...props }: CheckboxProps) {
  const inputId = id ?? label.toLowerCase().replace(/[^a-z0-9]+/g, "-");

  return (
    <label
      htmlFor={inputId}
      className={cn(
        "group inline-flex cursor-pointer items-center gap-3 text-[0.94rem] font-medium text-[#4B5563]",
        className,
      )}
    >
      <span className="relative flex h-5 w-5 items-center justify-center">
        <input
          id={inputId}
          type="checkbox"
          className="peer sr-only"
          {...props}
        />
        <span className="flex h-5 w-5 items-center justify-center rounded-[6px] border border-[#D1D5DB] bg-white shadow-[0_3px_10px_rgba(15,23,42,0.05)] transition peer-focus-visible:ring-2 peer-focus-visible:ring-[#B7E5D3] peer-focus-visible:ring-offset-2 peer-checked:border-[#38B88A] peer-checked:bg-[#38B88A]">
          <Check className="h-3.5 w-3.5 text-white opacity-0 transition peer-checked:opacity-100" strokeWidth={3} />
        </span>
      </span>
      <span>{label}</span>
    </label>
  );
}
