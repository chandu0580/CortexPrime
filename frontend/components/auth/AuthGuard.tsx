"use client"
import { useEffect, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { useAuthStore } from "@/store/authStore"

// ==========================================
// AUTH GUARD  — wraps protected pages
// ==========================================

export default function AuthGuard({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, initFromToken } = useAuthStore()
    const router              = useRouter()
    const pathname            = usePathname()
    const [isReady, setIsReady] = useState(false)

    useEffect(() => {
        let isMounted = true

        void initFromToken().finally(() => {
            if (isMounted) setIsReady(true)
        })

        return () => {
            isMounted = false
        }
    }, [initFromToken])

    useEffect(() => {
        if (isReady && !isAuthenticated) {
            const next = pathname ? `?next=${encodeURIComponent(pathname)}` : ""
            router.replace(`/login${next}`)
        }
    }, [isAuthenticated, isReady, pathname, router])

    if (!isReady || !isAuthenticated) return null

    return <>{children}</>
}
