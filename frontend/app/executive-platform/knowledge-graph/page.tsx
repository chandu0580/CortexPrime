"use client"

import { useState } from "react"
import { Search, Share2, Filter } from "lucide-react"

const SAMPLE_NODES = [
  { id: "1", label: "CortexPrime", type: "system", color: "text-emerald-400" },
  { id: "2", label: "Mission Runtime", type: "service", color: "text-blue-400" },
  { id: "3", label: "Memory System", type: "service", color: "text-violet-400" },
  { id: "4", label: "Knowledge Graph", type: "service", color: "text-amber-400" },
  { id: "5", label: "Browser Worker", type: "worker", color: "text-cyan-400" },
  { id: "6", label: "Voice Worker", type: "worker", color: "text-pink-400" },
  { id: "7", label: "Governance Engine", type: "service", color: "text-red-400" },
  { id: "8", label: "Security Center", type: "service", color: "text-orange-400" },
]

const SAMPLE_EDGES = [
  { from: "1", to: "2", label: "orchestrates" },
  { from: "1", to: "3", label: "persists to" },
  { from: "2", to: "5", label: "invokes" },
  { from: "2", to: "6", label: "invokes" },
  { from: "1", to: "7", label: "governed by" },
  { from: "3", to: "4", label: "feeds" },
  { from: "7", to: "8", label: "integrates" },
]

export default function KnowledgeGraph() {
  const [search, setSearch] = useState("")
  const [selectedNode, setSelectedNode] = useState<string | null>(null)

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge Graph</h1>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/10 bg-white/[0.02]">
            <Search className="w-4 h-4 text-white/30" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search entities..." className="bg-transparent border-none outline-none text-sm text-white/80 placeholder:text-white/20 w-40" />
          </div>
          <button className="p-2 rounded-lg border border-white/10 hover:bg-white/5 text-white/40">
            <Filter className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 border border-white/5 rounded-xl p-4 bg-white/[0.02] min-h-[400px]">
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-4 p-8">
              <Share2 className="w-12 h-12 text-white/10 mx-auto" />
              <p className="text-sm text-white/30">Interactive graph visualization loads here</p>
              <p className="text-xs text-white/20">Connect to Neo4j backend and redis for live data</p>
            </div>
          </div>
        </div>

        <div className="border border-white/5 rounded-xl p-4 bg-white/[0.02]">
          <h2 className="text-sm font-medium text-white/60 mb-3">Entities</h2>
          <div className="space-y-1">
            {SAMPLE_NODES.filter((n) => !search || n.label.toLowerCase().includes(search.toLowerCase())).map((node) => (
              <button
                key={node.id}
                onClick={() => setSelectedNode(node.id)}
                className={`w-full text-left flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
                  selectedNode === node.id ? "bg-white/5" : "hover:bg-white/[0.02]"
                }`}
              >
                <div className={`w-2 h-2 rounded-full ${node.color.replace("text-", "bg-")}`} />
                <span className="text-white/70">{node.label}</span>
                <span className="text-[10px] text-white/20 ml-auto">{node.type}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-white/5">
            <h3 className="text-xs font-medium text-white/40 mb-2">Relationships</h3>
            <div className="space-y-1">
              {SAMPLE_EDGES.map((edge, i) => (
                <div key={i} className="text-xs text-white/30 flex items-center gap-2">
                  <span className="text-white/50">{edge.from} → {edge.to}</span>
                  <span className="text-white/20">({edge.label})</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}