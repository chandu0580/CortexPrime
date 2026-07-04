// ==========================================
// MEMORY TYPES
// ==========================================

export interface MemoryEntry {
    id: string
    content: string
    type: "episodic" | "semantic" | "working"
    agent?: string
    timestamp: string
    tags?: string[]
    score?: number
}

export interface EpisodicMemory {
    id: string
    event: string
    context: string
    timestamp: string
    emotionalValence?: number
    significance?: number
    lastAccessed?: string
}

export interface SemanticMemory {
    id: string
    concept: string
    definition: string
    relatedConcepts?: string[]
    confidence?: number
    lastAccessed?: string
}

export interface ReflectionEntry {
    id: string
    insight: string
    source: string
    timestamp: string
    agentId?: string
    category?: "performance" | "knowledge" | "strategy" | "correction"
}

export interface MemoryStats {
    totalEpisodic: number
    totalSemantic: number
    totalWorking: number
    vectorDimensions: number
    lastUpdated: string
}
