import type { BrowserActionType, BrowserSecurityPolicy, BrowserNavigationTarget } from "./types"

export const BrowserSecurityEngine = {
  validateNavigation(target: BrowserNavigationTarget, policy: BrowserSecurityPolicy): { valid: boolean; reason: string | null } {
    const url = this.parseUrl(target.url)
    if (!url) {
      return { valid: false, reason: "Invalid URL format" }
    }

    if (policy.blockedDomains.some((d) => url.hostname.endsWith(d))) {
      return { valid: false, reason: `Domain ${url.hostname} is blocked` }
    }

    if (policy.allowedDomains.length > 0 && !policy.allowedDomains.some((d) => url.hostname.endsWith(d))) {
      return { valid: false, reason: `Domain ${url.hostname} is not in allowlist` }
    }

    if (!policy.javascriptEnabled && target.waitCondition === "custom") {
      return { valid: false, reason: "JavaScript execution is disabled" }
    }

    return { valid: true, reason: null }
  },

  validateAction(actionType: BrowserActionType, policy: BrowserSecurityPolicy): { allowed: boolean; reason: string | null } {
    if (policy.blockedActions.includes(actionType)) {
      return { allowed: false, reason: `Action ${actionType} is blocked` }
    }

    if (policy.allowedActions.length > 0 && !policy.allowedActions.includes(actionType)) {
      return { allowed: false, reason: `Action ${actionType} is not in allowed list` }
    }

    return { allowed: true, reason: null }
  },

  sanitizeUrl(url: string): string {
    try {
      const parsed = new URL(url)
      parsed.hash = ""
      return parsed.toString()
    } catch {
      return ""
    }
  },

  createDefaultPolicy(): BrowserSecurityPolicy {
    return {
      allowedDomains: [],
      blockedDomains: [],
      allowedActions: [],
      blockedActions: ["evaluate"],
      maxNavigationDepth: 5,
      maxPageSizeBytes: 10_485_760,
      sandboxEnabled: true,
      javascriptEnabled: true,
      cookiePolicy: "allow_session",
      contentSecurityPolicy: null,
    }
  },

  parseUrl(url: string): URL | null {
    try {
      return new URL(url)
    } catch {
      return null
    }
  },
}
