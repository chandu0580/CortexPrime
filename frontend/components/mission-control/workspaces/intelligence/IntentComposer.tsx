"use client"

import { useState } from "react"
import { Send, Trash2 } from "lucide-react"

interface IntentComposerProps {
  onSubmit: (text: string) => void
  isAnalyzing?: boolean
}

export function IntentComposer({ onSubmit, isAnalyzing = false }: IntentComposerProps) {
  const [text, setText] = useState("")

  const handleSubmit = () => {
    if (text.trim().length > 0 && !isAnalyzing) {
      onSubmit(text.trim())
    }
  }

  const handleClear = () => {
    setText("")
  }

  return (
    <section>
      <div className="mb-3">
        <h3 className="text-[0.92rem] font-bold text-[#111827]">Intent Composer</h3>
        <p className="text-[0.78rem] text-[#6B7280]">
          Describe the enterprise objective you want to pursue
        </p>
      </div>
      <div className="overflow-hidden rounded-[12px] border border-[#EAEFF5] bg-white">
        <div className="min-h-[160px] p-5">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="What business objective are you trying to achieve?"
            className="w-full resize-none bg-transparent text-[0.88rem] text-[#111827] leading-relaxed outline-none placeholder:text-[#9CA3AF]"
            rows={4}
          />
        </div>
        <div className="flex items-center justify-between border-t border-[#EAEFF5] px-4 py-2.5">
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleSubmit}
              disabled={isAnalyzing || text.trim().length === 0}
              className="flex h-7 items-center gap-1.5 rounded-[6px] border border-[#EAEFF5] bg-white px-3 text-[0.72rem] font-medium text-[#38B88A] transition-colors hover:bg-[#F0FDF4] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" aria-hidden="true" />
              {isAnalyzing ? "Analyzing..." : "Analyze"}
            </button>
            {text.length > 0 && (
              <button
                onClick={handleClear}
                className="flex h-7 items-center gap-1.5 rounded-[6px] border border-[#EAEFF5] bg-white px-3 text-[0.72rem] font-medium text-[#9CA3AF] transition-colors hover:bg-[#F8FAFC]"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                Clear
              </button>
            )}
          </div>
          <span className="text-[0.7rem] text-[#B0B7C3]">Structured input · Enterprise intent</span>
        </div>
      </div>
    </section>
  )
}
