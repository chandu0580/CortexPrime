import { create } from "zustand"

import { apiUrl } from "@/lib/constants"

export interface AuthUser {
    user_id: string
    role: string
    clearance: string
}

interface AuthState {
    isAuthenticated: boolean
    user: AuthUser | null
    tokenExpiresAt: number | null
    loginError: string | null
    isLoading: boolean

    login: (username: string, password: string) => Promise<boolean>
    logout: () => Promise<void>
    refresh: () => Promise<boolean>
    clearError: () => void
    initFromToken: () => Promise<void>
}

const REFRESH_THRESHOLD_MS = 5 * 60 * 1000

function createTimeoutSignal(timeoutMs: number): AbortSignal {
    if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
        return AbortSignal.timeout(timeoutMs)
    }

    const controller = new AbortController()
    setTimeout(() => controller.abort(), timeoutMs)
    return controller.signal
}

function parseJwtExp(token: string): number | null {
    try {
        const [, payload] = token.split(".")
        const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")))
        return decoded.exp ? decoded.exp * 1000 : null
    } catch {
        return null
    }
}

// The backend deliberately never reveals *why* auth failed in the response
// body (see backend/core/exception_handlers.py — every HTTPException is
// flattened to a generic canned message, by design, to avoid leaking
// which specific auth failure occurred). So there's no response field to
// branch on here. `cortex_session_hint` is a non-HttpOnly, non-sensitive
// cookie the backend sets alongside the real (HttpOnly) refresh cookie —
// its mere presence is the only signal available for "a session might
// still be recoverable, worth trying /refresh" vs. "definitely never
// logged in, don't bother."
function hasSessionHint(): boolean {
    if (typeof document === "undefined") return false
    return document.cookie.split("; ").some((c) => c === "cortex_session_hint=1")
}

export const useAuthStore = create<AuthState>()((set, get) => ({
    isAuthenticated: false,
    user: null,
    tokenExpiresAt: null,
    loginError: null,
    isLoading: false,

    login: async (username, password) => {
        set({ isLoading: true, loginError: null })
        try {
            const res = await fetch(apiUrl("/api/auth/login"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
                credentials: "include",
                signal: createTimeoutSignal(10000),
            })

            if (!res.ok) {
                const data = await res.json().catch(() => ({})) as { detail?: string }
                set({
                    loginError: data?.detail || "ACCESS DENIED - IDENTITY UNVERIFIED",
                    isLoading: false,
                })
                return false
            }

            const data = await res.json() as {
                access_token?: string
                user: AuthUser
            }

            set({
                isAuthenticated: true,
                tokenExpiresAt: data.access_token ? parseJwtExp(data.access_token) : null,
                user: {
                    user_id: data.user.user_id,
                    role: data.user.role,
                    clearance: data.user.clearance || "LEVEL-5",
                },
                loginError: null,
                isLoading: false,
            })
            scheduleTokenRefresh()
            return true
        } catch {
            set({ loginError: "Unable to reach authentication server", isLoading: false })
            return false
        }
    },

    refresh: async () => {
        try {
            const res = await fetch(apiUrl("/api/auth/refresh"), {
                method: "POST",
                credentials: "include",
                signal: createTimeoutSignal(8000),
            })

            if (!res.ok) {
                clearRefreshTimer()
                set({ isAuthenticated: false, user: null, tokenExpiresAt: null })
                return false
            }

            const data = await res.json() as { access_token?: string; user: AuthUser }
            set({
                isAuthenticated: true,
                tokenExpiresAt: data.access_token ? parseJwtExp(data.access_token) : null,
                user: {
                    user_id: data.user.user_id,
                    role: data.user.role,
                    clearance: data.user.clearance || "LEVEL-5",
                },
                loginError: null,
            })
            scheduleTokenRefresh()
            return true
        } catch {
            clearRefreshTimer()
            set({ isAuthenticated: false, user: null, tokenExpiresAt: null })
            return false
        }
    },

    logout: async () => {
        await fetch(apiUrl("/api/auth/logout"), {
            method: "POST",
            credentials: "include",
        }).catch(() => {})

        clearRefreshTimer()
        set({ isAuthenticated: false, user: null, tokenExpiresAt: null, loginError: null })
    },

    clearError: () => set({ loginError: null }),

    initFromToken: async () => {
        if (!hasSessionHint()) {
            // No evidence a session ever existed on this browser — skip
            // straight to signed-out instead of firing /me and /refresh
            // requests that are guaranteed to both 401.
            clearRefreshTimer()
            set({ isAuthenticated: false, user: null, tokenExpiresAt: null })
            return
        }

        try {
            const me = await fetch(apiUrl("/api/auth/me"), {
                credentials: "include",
                signal: createTimeoutSignal(5000),
            })

            if (!me.ok) {
                if (me.status === 401) {
                    const ok = await get().refresh()
                    if (ok) return
                }

                clearRefreshTimer()
                set({ isAuthenticated: false, user: null, tokenExpiresAt: null })
                return
            }

            const data = await me.json() as { user_id: string; role: string; clearance: string }
            set({
                isAuthenticated: true,
                user: {
                    user_id: data.user_id,
                    role: data.role,
                    clearance: data.clearance || "LEVEL-5",
                },
                loginError: null,
            })

            const { tokenExpiresAt } = get()
            if (tokenExpiresAt && Date.now() >= tokenExpiresAt - REFRESH_THRESHOLD_MS) {
                await get().refresh()
            }

            scheduleTokenRefresh()
        } catch {
            clearRefreshTimer()
            set({ isAuthenticated: false, user: null, tokenExpiresAt: null })
        }
    },

}))

let _refreshTimer: ReturnType<typeof setTimeout> | null = null

function clearRefreshTimer() {
    if (_refreshTimer) {
        clearTimeout(_refreshTimer)
        _refreshTimer = null
    }
}

function scheduleTokenRefresh() {
    clearRefreshTimer()
    const { tokenExpiresAt } = useAuthStore.getState()
    if (!tokenExpiresAt) return

    const msUntilExpiry = tokenExpiresAt - Date.now()
    const msUntilRefresh = msUntilExpiry - REFRESH_THRESHOLD_MS

    if (msUntilRefresh <= 0) {
        useAuthStore.getState().refresh()
        return
    }

    _refreshTimer = setTimeout(() => {
        useAuthStore.getState().refresh()
    }, msUntilRefresh)
}
