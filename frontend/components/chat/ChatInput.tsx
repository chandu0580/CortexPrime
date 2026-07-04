"use client"
import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowUp, X, Mic, Paperclip } from "lucide-react"
import { cn } from "@/utils/cn"
import { useRuntimeStore } from "@/store/runtimeStore"

interface ChatInputProps {
    onSend:      (text: string) => void
    disabled?:   boolean
    placeholder?: string
}

export default function ChatInput({
    onSend,
    disabled,
    placeholder = "Message your AI companion...",
}: ChatInputProps) {
    const [value,   setValue]   = useState("")
    const [focused, setFocused] = useState(false)
    const ref = useRef<HTMLTextAreaElement>(null)
    const { activeAgents } = useRuntimeStore()

    useEffect(() => {
        if (ref.current) {
            ref.current.style.height = "auto"
            ref.current.style.height = `${Math.min(ref.current.scrollHeight, 150)}px`
        }
    }, [value])

    function submit() {
        const trimmed = value.trim()
        if (!trimmed || disabled) return
        onSend(trimmed)
        setValue("")
        if (ref.current) ref.current.style.height = "auto"
    }

    function handleKey(e: React.KeyboardEvent) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            submit()
        }
    }

    const canSend = !!value.trim() && !disabled

    return (
        <div
            className={cn(
                "relative rounded-2xl border transition-all duration-300 bg-white",
                focused
                    ? "border-[rgba(130,192,164,0.45)] shadow-[0_4px_20px_rgba(130,192,164,0.15)]"
                    : "border-[#dceee4] shadow-[0_2px_8px_rgba(26,26,26,0.04)]"
            )}
        >
            <div className="flex items-end gap-1 px-3 py-2.5">
                <button
                    type="button"
                    className="rounded-lg p-2 text-[#737373] hover:text-[#4a8c70] transition-colors"
                    tabIndex={-1}
                >
                    <Paperclip size={16} />
                </button>

                <textarea
                    ref={ref}
                    rows={1}
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    onKeyDown={handleKey}
                    onFocus={() => setFocused(true)}
                    onBlur={() => setFocused(false)}
                    disabled={disabled}
                    placeholder={placeholder}
                    className="flex-1 resize-none bg-transparent text-base text-[#1a1a1a] placeholder:text-[#a3a3a3] outline-none leading-relaxed min-h-[24px] py-1.5"
                />

                <div className="mb-0.5 flex items-center gap-1">
                    <AnimatePresence>
                        {value && (
                            <motion.button
                                initial={{ opacity: 0, scale: 0.7 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.7 }}
                                onClick={() => setValue("")}
                                className="rounded-md p-1 text-[#a3a3a3] hover:text-[#737373] transition-colors"
                                tabIndex={-1}
                            >
                                <X size={12} />
                            </motion.button>
                        )}
                    </AnimatePresence>

                    <button
                        type="button"
                        className="rounded-lg p-2 text-[#737373] hover:text-[#4a8c70] transition-colors"
                        tabIndex={-1}
                        title="Voice input"
                    >
                        <Mic size={16} />
                    </button>

                    <motion.button
                        whileTap={{ scale: 0.92 }}
                        onClick={submit}
                        disabled={!canSend}
                        className={cn(
                            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white transition-all duration-200",
                            !canSend && "opacity-40 cursor-not-allowed"
                        )}
                        style={{
                            background: canSend
                                ? "linear-gradient(135deg, #82c0a4, #4a8c70)"
                                : "#d1d1d1",
                            boxShadow: canSend ? "0 4px 14px rgba(130,192,164,0.35)" : "none",
                        }}
                    >
                        <ArrowUp size={16} />
                    </motion.button>
                </div>
            </div>

            <div className="flex items-center justify-between border-t border-[#e8f5ee] px-4 py-1.5">
                <div className="flex items-center gap-3 text-[10px] text-[#a3a3a3]">
                    <span>Enter to send</span>
                    <span className="h-3 w-px bg-[#dceee4]" />
                    <span className="flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-[#82c0a4]" />
                        {activeAgents} agents ready
                    </span>
                </div>
                <span className="text-[10px] text-[#a3a3a3]">Shift+Enter for newline</span>
            </div>
        </div>
    )
}
