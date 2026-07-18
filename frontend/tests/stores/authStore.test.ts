import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"
import { useAuthStore } from "@/store/authStore"

function resetStore() {
  useAuthStore.setState({
    isAuthenticated: false,
    user: null,
    tokenExpiresAt: null,
    loginError: null,
    isLoading: false,
  })
}

describe("useAuthStore", () => {
  beforeEach(() => {
    resetStore()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it("has correct initial state", () => {
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.user).toBeNull()
    expect(state.loginError).toBeNull()
    expect(state.isLoading).toBe(false)
  })

  it("clearError sets loginError to null", () => {
    useAuthStore.setState({ loginError: "ACCESS DENIED" })
    useAuthStore.getState().clearError()
    expect(useAuthStore.getState().loginError).toBeNull()
  })

  it("logout clears auth state and calls clearRefreshTimer", async () => {
    useAuthStore.setState({
      isAuthenticated: true,
      user: { user_id: "test", role: "admin", clearance: "5" },
      tokenExpiresAt: Date.now() + 600000,
    })

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    }))

    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout")

    await useAuthStore.getState().initFromToken()

    await useAuthStore.getState().logout()

    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().user).toBeNull()
    expect(clearTimeoutSpy).toHaveBeenCalled()
  })

  it("initFromToken handles 401 with Missing authentication token correctly", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: "Missing authentication token" }),
    }))

    const refreshSpy = vi.spyOn(useAuthStore.getState(), "refresh")

    await useAuthStore.getState().initFromToken()

    expect(refreshSpy).not.toHaveBeenCalled()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().user).toBeNull()
  })

  it("initFromToken retries refresh on 401 without Missing authentication token", async () => {
    let callCount = 0
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => {
      callCount++
      if (callCount === 1) {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: "Token expired" }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          access_token: "new.token.here",
          user: { user_id: "test", role: "admin", clearance: "5" },
        }),
      })
    }))

    await useAuthStore.getState().initFromToken()

    expect(callCount).toBeGreaterThanOrEqual(2)
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })

  it("login success sets authenticated state and tokenExpiresAt from JWT", async () => {
    const exp = Math.floor(Date.now() / 1000) + 3600
    const payload = btoa(JSON.stringify({ exp }))
    const fakeToken = `header.${payload}.signature`

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        access_token: fakeToken,
        user: { user_id: "alice", role: "analyst", clearance: "LEVEL-3" },
      }),
    }))

    const result = await useAuthStore.getState().login("alice", "pass")

    expect(result).toBe(true)
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.user).toEqual({ user_id: "alice", role: "analyst", clearance: "LEVEL-3" })
    expect(state.tokenExpiresAt).toBe(exp * 1000)
    expect(state.isLoading).toBe(false)
  })

  it("login failure sets loginError and returns false", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: "Invalid credentials" }),
    }))

    const result = await useAuthStore.getState().login("alice", "wrong")

    expect(result).toBe(false)
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.loginError).toBe("Invalid credentials")
    expect(state.isLoading).toBe(false)
  })

  it("login network error sets fallback error message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Network failure")))

    const result = await useAuthStore.getState().login("alice", "pass")

    expect(result).toBe(false)
    expect(useAuthStore.getState().loginError).toBe("Unable to reach authentication server")
  })

  it("parseJwtExp returns null for access_token with no exp claim", async () => {
    const payload = btoa(JSON.stringify({ sub: "test" }))
    const fakeToken = `header.${payload}.signature`

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        access_token: fakeToken,
        user: { user_id: "test", role: "admin", clearance: "5" },
      }),
    }))

    await useAuthStore.getState().login("test", "pass")

    expect(useAuthStore.getState().tokenExpiresAt).toBeNull()
  })

  it("parseJwtExp returns null for malformed access_token", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        access_token: "invalid..token",
        user: { user_id: "test", role: "admin", clearance: "5" },
      }),
    }))

    await useAuthStore.getState().login("test", "pass")

    expect(useAuthStore.getState().tokenExpiresAt).toBeNull()
  })
})
