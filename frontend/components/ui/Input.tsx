import type { InputHTMLAttributes, ReactNode } from "react";
import { forwardRef } from "react";

import { cn } from "@/utils/cn";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  leftAdornment?: ReactNode;
  rightAdornment?: ReactNode;
  wrapperClassName?: string;
};

const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, leftAdornment, rightAdornment, className, wrapperClassName, id, ...props },
  ref,
) {
  const inputId = id ?? label.toLowerCase().replace(/[^a-z0-9]+/g, "-");

  return (
    <div className={cn("space-y-2", wrapperClassName)}>
      <label
        htmlFor={inputId}
        className="block text-[0.92rem] font-semibold tracking-[-0.02em] text-[#111827]"
      >
        {label}
      </label>
      <div className="relative">
        {leftAdornment ? (
          <div className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[#9CA3AF]">
            {leftAdornment}
          </div>
        ) : null}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "h-12 w-full rounded-[16px] border border-[#E5E7EB] bg-white text-[0.98rem] text-[#111827] outline-none transition placeholder:text-[#9CA3AF] focus:border-[#B7E5D3] focus:ring-4 focus:ring-[#EAF8F1]",
            leftAdornment ? "pl-12 pr-4" : "px-4",
            rightAdornment ? "pr-12" : "pr-4",
            className,
          )}
          {...props}
        />
        {rightAdornment ? (
          <div className="absolute right-4 top-1/2 -translate-y-1/2 text-[#9CA3AF]">
            {rightAdornment}
          </div>
        ) : null}
      </div>
    </div>
  );
});

export default Input;
