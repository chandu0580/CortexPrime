"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Settings, Bell, Shield, Eye, Palette, Database } from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/enterprise/ui"

const settingSections = [
  { icon: Palette, label: "Appearance", desc: "Theme, layout, and display preferences" },
  { icon: Bell, label: "Notifications", desc: "Alert and notification preferences" },
  { icon: Eye, label: "Privacy", desc: "Data visibility and sharing controls" },
  { icon: Shield, label: "Security", desc: "API keys, authentication, access control" },
  { icon: Database, label: "Storage", desc: "Data retention, backups, and cleanup" },
]

export default function SettingsPage() {
  const [theme, setTheme] = useState("dark")

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="type-heading-xl text-[var(--text-primary)]">Settings</h1>
        <p className="type-body text-[var(--text-muted)] mt-1">Configure platform preferences</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-3 rounded-xl bg-[var(--surface-raised)]">
            <div>
              <p className="type-body-sm text-[var(--text-primary)]">Theme</p>
              <p className="type-caption text-[var(--text-muted)]">Choose dark or light mode</p>
            </div>
            <div className="flex gap-2">
              {["dark", "light"].map((t) => (
                <button
                  key={t}
                  onClick={() => setTheme(t)}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    theme === t
                      ? "bg-[var(--accent)] text-[var(--text-inverse)]"
                      : "bg-[var(--surface)] text-[var(--text-muted)] border border-[var(--border)]"
                  }`}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {settingSections.map((section, i) => (
          <motion.div
            key={section.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <Card>
              <CardContent>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-raised)] flex items-center justify-center">
                    <section.icon className="w-5 h-5 text-[var(--accent)]" />
                  </div>
                  <div>
                    <h3 className="type-body-sm text-[var(--text-primary)] font-semibold">{section.label}</h3>
                    <p className="type-caption text-[var(--text-muted)]">{section.desc}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
