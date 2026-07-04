"use client"

import { useEffect, useState } from "react"
import { Sun, Moon, Monitor, Palette, Globe, Bell } from "lucide-react"

export default function Settings() {
  const [theme, setTheme] = useState<"dark" | "light">("dark")

  useEffect(() => {
    const html = document.documentElement
    const isDark = html.classList.contains("cortex-dark")
    setTheme(isDark ? "dark" : "light")
  }, [])

  const toggleTheme = () => {
    const html = document.documentElement
    const next = theme === "dark" ? "light" : "dark"
    html.classList.remove(`cortex-${theme}`)
    html.classList.add(`cortex-${next}`)
    setTheme(next)
    localStorage.setItem("theme", next)
  }

  const sections = [
    {
      icon: Palette,
      title: "Appearance",
      items: [
        { label: "Theme", control: (
          <button onClick={toggleTheme} className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-white/60 hover:text-white/80">
            {theme === "dark" ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
            {theme === "dark" ? "Dark" : "Light"}
          </button>
        )},
        { label: "Language", control: <span className="text-xs text-white/40">English</span> },
      ],
    },
    {
      icon: Globe,
      title: "Region",
      items: [
        { label: "Timezone", control: <span className="text-xs text-white/40">UTC</span> },
        { label: "Date Format", control: <span className="text-xs text-white/40">ISO 8601</span> },
      ],
    },
    {
      icon: Bell,
      title: "Notifications",
      items: [
        { label: "Mission Events", control: <span className="text-xs text-emerald-400">Enabled</span> },
        { label: "Approval Requests", control: <span className="text-xs text-emerald-400">Enabled</span> },
        { label: "Security Alerts", control: <span className="text-xs text-emerald-400">Enabled</span> },
      ],
    },
  ]

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <div className="space-y-4">
        {sections.map((section) => (
          <div key={section.title} className="border border-white/5 rounded-xl p-4 bg-white/[0.02]">
            <div className="flex items-center gap-2 mb-3">
              <section.icon className="w-4 h-4 text-white/40" />
              <h2 className="text-sm font-medium text-white/60">{section.title}</h2>
            </div>
            <div className="space-y-2">
              {section.items.map((item) => (
                <div key={item.label} className="flex items-center justify-between py-1.5">
                  <span className="text-sm text-white/70">{item.label}</span>
                  {item.control}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}