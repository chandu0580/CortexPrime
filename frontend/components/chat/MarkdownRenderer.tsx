"use client"
import ReactMarkdown from "react-markdown"
import { cn } from "@/utils/cn"

interface MarkdownRendererProps {
    content: string
    streaming?: boolean
    className?: string
    variant?: "dark" | "light"
}

export default function MarkdownRenderer({ content, streaming, className, variant = "dark" }: MarkdownRendererProps) {
    const onLight = variant === "light"

    return (
        <div className={cn("prose max-w-none", onLight ? "prose-invert-light" : "prose-invert prose-sm", className)}>
            <ReactMarkdown
                components={{
                    code({ className: cname, children, ...props }) {
                        const isBlock = cname?.startsWith("language-")
                        return isBlock ? (
                            <pre
                                className="rounded-xl p-4 overflow-x-auto"
                                style={{
                                    fontSize: "0.9375rem",
                                    lineHeight: 1.6,
                                    background: onLight ? "rgba(0,0,0,0.12)" : "#0d0d1a",
                                    border: onLight ? "1px solid rgba(255,255,255,0.15)" : "1px solid rgba(255,255,255,0.05)",
                                }}
                            >
                                <code className={cn(cname, onLight ? "text-[#f0f7f4]" : "text-[#96cead]")} {...props}>
                                    {children}
                                </code>
                            </pre>
                        ) : (
                            <code
                                className="rounded px-1.5 py-0.5"
                                style={{
                                    fontSize: "0.9rem",
                                    background: onLight ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.05)",
                                    color: onLight ? "#f0f7f4" : "#96cead",
                                }}
                                {...props}
                            >
                                {children}
                            </code>
                        )
                    },
                    p({ children }) {
                        return (
                            <p
                                className="mb-2.5 last:mb-0 leading-[1.7]"
                                style={{ fontSize: "1rem", color: onLight ? "#ffffff" : "#e2e8f0" }}
                            >
                                {children}
                            </p>
                        )
                    },
                    ul({ children }) {
                        return (
                            <ul
                                className="mb-2.5 ml-4 list-disc space-y-1.5"
                                style={{ fontSize: "1rem", color: onLight ? "#ffffff" : "#e2e8f0" }}
                            >
                                {children}
                            </ul>
                        )
                    },
                    ol({ children }) {
                        return (
                            <ol
                                className="mb-2.5 ml-4 list-decimal space-y-1.5"
                                style={{ fontSize: "1rem", color: onLight ? "#ffffff" : "#e2e8f0" }}
                            >
                                {children}
                            </ol>
                        )
                    },
                    h1({ children }) {
                        return <h1 className="mb-3 font-bold" style={{ fontSize: "1.5rem", lineHeight: 1.2, color: onLight ? "#ffffff" : "#ffffff" }}>{children}</h1>
                    },
                    h2({ children }) {
                        return <h2 className="mb-2.5 font-bold" style={{ fontSize: "1.25rem", lineHeight: 1.25, color: onLight ? "#ffffff" : "#ffffff" }}>{children}</h2>
                    },
                    h3({ children }) {
                        return <h3 className="mb-2 font-semibold" style={{ fontSize: "1.0625rem", lineHeight: 1.3, color: onLight ? "#f0f7f4" : "#f1f5f9" }}>{children}</h3>
                    },
                    blockquote({ children }) {
                        return (
                            <blockquote
                                className="border-l-2 pl-4 italic"
                                style={{
                                    fontSize: "1rem",
                                    borderColor: onLight ? "rgba(255,255,255,0.4)" : "rgba(130,192,164,0.5)",
                                    color: onLight ? "#f0f7f4" : "#cbd5e1",
                                }}
                            >
                                {children}
                            </blockquote>
                        )
                    },
                }}
            >
                {content}
            </ReactMarkdown>
            {streaming && (
                <span
                    className="inline-block w-0.5 h-4 ml-0.5 animate-stream-cursor"
                    style={{ background: onLight ? "#ffffff" : "#82c0a4" }}
                />
            )}
        </div>
    )
}
