"use client"
import { motion } from "framer-motion"
import { Brain, Network, Database, Terminal, Mic, Eye, Route, Shield } from "lucide-react"

// ==========================================
// CAPABILITIES DATA
// ==========================================

const CAPABILITIES = [
    { icon: Network,  title: "Multi-Agent Orchestration",   description: "Planner, Researcher, Critic, Optimizer, Orchestrator agents collaborate under dynamic mission trees.", color: "#82c0a4", tag: "Core Engine"   },
    { icon: Brain,    title: "Real-Time Cognition Stream",  description: "WebSocket-driven live feed of every agent thought, decision, and execution state.", color: "#4a8c70", tag: "Live Feed"    },
    { icon: Database, title: "Persistent Memory Fabric",    description: "Episodic, semantic, short-term, and vector memory with Chroma. Full reflection cycles.", color: "#4a8c70", tag: "Memory"       },
    { icon: Terminal, title: "Autonomous Computer Use",      description: "Full browser control via Playwright plus desktop automation via PyAutoGUI.", color: "#82c0a4", tag: "Computer Use" },
    { icon: Mic,      title: "Voice Interface",              description: "Wake-word detection, real-time speech-to-text input, and TTS responses.", color: "#4a8c70", tag: "Voice"        },
    { icon: Route,    title: "Multi-LLM Routing",           description: "Dynamically routes tasks to OpenAI, Anthropic, Google Gemini, or Ollama models.", color: "#4a8c70", tag: "LLM Router"  },
    { icon: Eye,      title: "Vision & OCR",                description: "Screenshot capture and OCR processing for visual context understanding.", color: "#82c0a4", tag: "Vision"       },
    { icon: Shield,   title: "Human Approval Gateway",      description: "Mission-critical actions are queued for human approval. Full governance layer.", color: "#4a8c70", tag: "Governance"  },
]

// ==========================================
// CAPABILITIES SECTION — Premium Light
// ==========================================

export default function CapabilitiesSection() {
    return (
        <section id="capabilities" className="relative py-28 px-8" style={{ background: "#f0f7f4" }}>
            {/* Top divider */}
            <div className="absolute top-0 left-0 right-0 h-px" style={{ background: "linear-gradient(90deg, transparent, rgba(130,192,164,0.2), transparent)" }} />

            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <motion.div
                    className="mb-16"
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    viewport={{ once: true }}
                >
                    <div className="text-[10px] glyph-mono tracking-widest text-[#82c0a4] mb-3 font-semibold uppercase">
                        ── System Capabilities ──
                    </div>
                    <h2 className="font-black text-4xl lg:text-5xl leading-tight text-[#1a1a1a]">
                        Cognitive <span className="text-gradient-blue">Architecture</span>
                    </h2>
                    <p className="mt-4 text-base text-[#737373] max-w-xl leading-relaxed">
                        Eight integrated capability layers forming a complete autonomous AI operating system.
                    </p>
                </motion.div>

                {/* Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                    {CAPABILITIES.map(({ icon: Icon, title, description, color, tag }, i) => (
                        <motion.div
                            key={title}
                            className="group relative flex flex-col gap-4 p-6 bg-white rounded-2xl cursor-default"
                            style={{ border: "1px solid #dceee4", boxShadow: "0 2px 8px rgba(15,23,42,0.04)" }}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.5, delay: i * 0.05 }}
                            viewport={{ once: true }}
                            whileHover={{ borderColor: `${color}40`, boxShadow: `0 8px 24px rgba(15,23,42,0.08), 0 0 0 1px ${color}20`, y: -2 }}
                        >
                            {/* Top accent line */}
                            <div className="absolute top-0 left-6 right-6 h-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                                style={{ background: `linear-gradient(90deg, transparent, ${color}, transparent)` }} />

                            {/* Tag */}
                            <div className="text-[9px] glyph-mono tracking-widest font-bold" style={{ color: `${color}80` }}>
                                {tag.toUpperCase()}
                            </div>

                            {/* Icon */}
                            <div
                                className="flex items-center justify-center w-10 h-10 rounded-xl"
                                style={{ background: `${color}10`, border: `1px solid ${color}22` }}
                            >
                                <Icon size={18} style={{ color }} />
                            </div>

                            {/* Content */}
                            <div>
                                <h3 className="font-bold text-base text-[#1a1a1a] mb-2">{title}</h3>
                                <p className="text-sm text-[#737373] leading-relaxed">{description}</p>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    )
}
