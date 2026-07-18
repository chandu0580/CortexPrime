import { describe, it, expect, beforeEach } from "vitest"
import { useChatStore } from "@/store/chatStore"
import type { ChatMessage } from "@/store/chatStore"

function makeMsg(id: string, overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id,
    role: "user",
    content: `message ${id}`,
    timestamp: new Date().toISOString(),
    ...overrides,
  }
}

describe("useChatStore", () => {
  beforeEach(() => {
    useChatStore.setState({ messages: [], isLoading: false, streamingId: null })
  })

  it("has correct initial state", () => {
    const state = useChatStore.getState()
    expect(state.messages).toEqual([])
    expect(state.isLoading).toBe(false)
    expect(state.streamingId).toBeNull()
  })

  it("addMessage appends message", () => {
    useChatStore.getState().addMessage(makeMsg("1"))
    expect(useChatStore.getState().messages).toHaveLength(1)
    expect(useChatStore.getState().messages[0].id).toBe("1")
  })

  it("addMessage truncates to 200 max messages", () => {
    const msgs: ChatMessage[] = []
    for (let i = 0; i < 220; i++) {
      msgs.push(makeMsg(`m${i}`))
    }
    for (const m of msgs) {
      useChatStore.getState().addMessage(m)
    }

    expect(useChatStore.getState().messages).toHaveLength(200)
    expect(useChatStore.getState().messages[0].id).toBe("m20")
    expect(useChatStore.getState().messages[199].id).toBe("m219")
  })

  it("updateMessage patches message by id leaving others unchanged", () => {
    useChatStore.getState().addMessage(makeMsg("1", { role: "user", content: "hello" }))
    useChatStore.getState().addMessage(makeMsg("2", { role: "assistant", content: "world" }))

    useChatStore.getState().updateMessage("1", { content: "hi" })

    const messages = useChatStore.getState().messages
    expect(messages).toHaveLength(2)
    expect(messages[0].content).toBe("hi")
    expect(messages[1].content).toBe("world")
  })

  it("appendChunk concatenates content for matching message id", () => {
    useChatStore.getState().addMessage(makeMsg("1", { role: "assistant", content: "Hel" }))

    useChatStore.getState().appendChunk("1", "lo ")
    useChatStore.getState().appendChunk("1", "world")

    expect(useChatStore.getState().messages[0].content).toBe("Hello world")
  })

  it("appendChunk does not modify non-matching messages", () => {
    useChatStore.getState().addMessage(makeMsg("1", { content: "first" }))
    useChatStore.getState().addMessage(makeMsg("2", { content: "second" }))

    useChatStore.getState().appendChunk("1", "!")

    expect(useChatStore.getState().messages[0].content).toBe("first!")
    expect(useChatStore.getState().messages[1].content).toBe("second")
  })

  it("setLoading updates isLoading", () => {
    useChatStore.getState().setLoading(true)
    expect(useChatStore.getState().isLoading).toBe(true)

    useChatStore.getState().setLoading(false)
    expect(useChatStore.getState().isLoading).toBe(false)
  })

  it("setStreamingId updates streamingId", () => {
    useChatStore.getState().setStreamingId("msg-1")
    expect(useChatStore.getState().streamingId).toBe("msg-1")

    useChatStore.getState().setStreamingId(null)
    expect(useChatStore.getState().streamingId).toBeNull()
  })

  it("clearMessages empties messages array", () => {
    useChatStore.getState().addMessage(makeMsg("1"))
    useChatStore.getState().addMessage(makeMsg("2"))
    useChatStore.getState().clearMessages()

    expect(useChatStore.getState().messages).toEqual([])
  })
})
