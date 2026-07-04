import { create } from "zustand"

// ==========================================
// CHAT MESSAGE TYPES
// ==========================================

export interface ChatMessage {
    id:        string
    role:      "user" | "assistant" | "system"
    content:   string
    timestamp: string
    streaming?: boolean
    agentEvents?: string[]
}

// ==========================================
// CHAT STORE
// ==========================================

interface ChatState {
    messages:   ChatMessage[]
    isLoading:  boolean
    streamingId: string | null

    addMessage:     (msg: ChatMessage) => void
    updateMessage:  (id: string, patch: Partial<ChatMessage>) => void
    appendChunk:    (id: string, chunk: string) => void
    setLoading:     (v: boolean) => void
    setStreamingId: (id: string | null) => void
    clearMessages:  () => void
}

export const useChatStore = create<ChatState>((set) => ({
    messages:    [],
    isLoading:   false,
    streamingId: null,

    addMessage: (msg) =>
        set((s) => ({ messages: [...s.messages, msg].slice(-200) })),

    updateMessage: (id, patch) =>
        set((s) => ({
            messages: s.messages.map((m) => m.id === id ? { ...m, ...patch } : m),
        })),

    appendChunk: (id, chunk) =>
        set((s) => ({
            messages: s.messages.map((m) =>
                m.id === id ? { ...m, content: m.content + chunk } : m
            ),
        })),

    setLoading:     (v)  => set({ isLoading: v }),
    setStreamingId: (id) => set({ streamingId: id }),
    clearMessages:  ()   => set({ messages: [] }),
}))
