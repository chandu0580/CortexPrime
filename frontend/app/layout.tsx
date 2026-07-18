import type { Metadata } from "next"
import { headers } from "next/headers"
import { Geist_Mono, Poppins } from "next/font/google"
import "./globals.css"
import "@/styles/animations.css"
import "@/styles/glassmorphism.css"
import "@/styles/runtime.css"
import "@/styles/cognition.css"
import { ThemeProvider } from "@/components/theme/ThemeProvider"
import { QueryProvider } from "@/lib/query"
import { EnterpriseUXProvider } from "@/components/enterprise-ux/integration"
import { ErrorBoundary } from "@/components/ErrorBoundary"


// ==========================================
// FONTS
// ==========================================

const poppins = Poppins({
    variable: "--font-geist-sans",
    subsets: ["latin"],
    weight: ["400", "500", "600", "700", "800", "900"],
})

const geistMono = Geist_Mono({

    variable: "--font-geist-mono",

    subsets: ["latin"]
})


// ==========================================
// METADATA
// ==========================================

export const metadata: Metadata = {

    title: "CortexPrime — Autonomous AI Operating System",

    description:
        "Autonomous multi-agent AI operating system with real-time cognition, persistent memory, and computer-use capabilities."
}


// ==========================================
// ROOT LAYOUT
// ==========================================

export default async function RootLayout({

    children

}: Readonly<{

    children: React.ReactNode

}>) {

    await headers()

    return (

        <html lang="en" className="cortex-light" suppressHydrationWarning>

            <body
                className={`
                    ${poppins.variable}
                    ${geistMono.variable}
                    antialiased
                    font-sans
                    overflow-hidden
                `}
            >

                <QueryProvider>
                    <ThemeProvider>
                        <EnterpriseUXProvider>
                            {/* RUNTIME CONTAINER */}
                            <main
                                className="
                                    h-screen
                                    overflow-y-auto
                                    scroll-smooth
                                "
                                id="main-content"
                                role="main"
                            >
                                <ErrorBoundary>
                                    {children}
                                </ErrorBoundary>

                            </main>
                        </EnterpriseUXProvider>
                    </ThemeProvider>
                </QueryProvider>

            </body>

        </html>
    )
}