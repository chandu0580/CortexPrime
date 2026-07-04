// ==========================================
// FORMATTING HELPERS
// ==========================================

export function formatTimestamp(iso: string): string {
    try {
        const d = new Date(iso)
        return d.toLocaleTimeString("en-US", {
            hour:   "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
        })
    } catch {
        return iso
    }
}

export function formatRelativeTime(iso: string): string {
    try {
        const diff = Date.now() - new Date(iso).getTime()
        if (diff < 60_000)  return `${Math.floor(diff / 1000)}s ago`
        if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
        return `${Math.floor(diff / 3_600_000)}h ago`
    } catch {
        return iso
    }
}

export function capitalizeFirst(str: string): string {
    return str.charAt(0).toUpperCase() + str.slice(1)
}

export function agentDisplayName(agentId: string): string {
    return agentId
        .split("_")
        .map(capitalizeFirst)
        .join(" ")
}

export function shortenId(id: string, len = 8): string {
    return id.length > len ? `${id.slice(0, len)}…` : id
}
