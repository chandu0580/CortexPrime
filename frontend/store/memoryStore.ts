import { create } from "zustand"
import type { MemoryEntry, EpisodicMemory, SemanticMemory, ReflectionEntry } from "@/types/memory"

// ==========================================
// MEMORY STORE
// ==========================================

interface MemoryState {
    entries:     MemoryEntry[]
    episodic:    EpisodicMemory[]
    semantic:    SemanticMemory[]
    reflections: ReflectionEntry[]
    isLoading:   boolean

    setEntries:      (entries: MemoryEntry[]) => void
    setEpisodic:     (items: EpisodicMemory[]) => void
    setSemantic:     (items: SemanticMemory[]) => void
    addReflection:   (r: ReflectionEntry) => void
    setLoading:      (v: boolean) => void
}

export const useMemoryStore = create<MemoryState>((set) => ({
    entries:     [],
    episodic:    [],
    semantic:    [],
    reflections: [],
    isLoading:   false,

    setEntries:    (entries)  => set({ entries }),
    setEpisodic:   (items)    => set({ episodic: items }),
    setSemantic:   (items)    => set({ semantic: items }),
    addReflection: (r)        => set((s) => ({ reflections: [r, ...s.reflections].slice(0, 50) })),
    setLoading:    (v)        => set({ isLoading: v }),
}))
