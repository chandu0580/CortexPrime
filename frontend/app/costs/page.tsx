"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import CortexShell from "@/components/layout/CortexShell";
import { apiUrl } from "@/lib/constants";

// ── Types ─────────────────────────────────────────────────────────────────────

interface DailyEntry  { date: string; total_cost: number; calls: number; total_tokens: number }
interface Provider    { provider: string; total_cost: number; calls: number }
interface TopMission  { mission_id: string; cost: number; calls: number }

interface CostSummary {
  today_spend:  number;
  month_spend:  number;
  top_missions: TopMission[];
  by_provider:  Provider[];
  daily_trend:  DailyEntry[];
  error?:       string;
}

// ── Palette ───────────────────────────────────────────────────────────────────

const PIE_COLORS = ["#82c0a4", "#4a8c70", "#96cead", "#f9a825", "#82c0a4", "#737373"];

const fmt = (v: number) =>
  v >= 1 ? `$${v.toFixed(2)}` : v >= 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(6)}`;

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({
  label, value, sub, accent = false,
}: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div style={{
      background:   accent ? "rgba(130,192,164,0.10)" : "var(--surface-raised, #121f30)",
      border:       `1px solid ${accent ? "rgba(130,192,164,0.25)" : "var(--border)"}`,
      borderRadius: 10,
      padding:      "18px 20px",
    }}>
      <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: accent ? "#82c0a4" : "var(--text-primary)", fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background:   "var(--surface-raised, #121f30)",
      border:       "1px solid var(--border)",
      borderRadius: 10,
      overflow:     "hidden",
    }}>
      <div style={{
        padding:      "10px 16px",
        borderBottom: "1px solid var(--border-subtle)",
        fontSize:     11,
        fontWeight:   700,
        color:        "var(--text-muted)",
        textTransform:"uppercase",
        letterSpacing:"0.07em",
      }}>
        {title}
      </div>
      <div style={{ padding: "16px" }}>
        {children}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CostDashboardPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);

  const fetchSummary = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/costs/summary"), { cache: "no-store", credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSummary(await res.json());
    } catch {
      // leave stale data on error
    } finally {
      setLoading(false);
      setLastFetch(new Date());
    }
  }, []);

  useEffect(() => {
    fetchSummary();
    const id = setInterval(fetchSummary, 60_000);
    return () => clearInterval(id);
  }, [fetchSummary]);

  const totalProviderCost = (summary?.by_provider ?? []).reduce((a, p) => a + p.total_cost, 0);

  return (
    <CortexShell title="Cost Intelligence">
      <div style={{ padding: "20px 24px", maxWidth: 1400, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: "var(--text-primary)" }}>
              Cost Intelligence
            </h1>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--text-muted)" }}>
              LLM and API spend across missions, users, and providers
            </p>
          </div>
          {lastFetch && (
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
              Updated {lastFetch.toLocaleTimeString()}
            </span>
          )}
        </div>

        {loading && (
          <div style={{ textAlign: "center", padding: 60, color: "var(--text-muted)" }}>
            Loading cost data…
          </div>
        )}

        {summary && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ display: "flex", flexDirection: "column", gap: 20 }}
          >
            {/* KPI row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
              <StatCard label="Today's Spend"  value={fmt(summary.today_spend)} accent />
              <StatCard label="Monthly Spend"  value={fmt(summary.month_spend)} />
              <StatCard
                label="Avg Cost / Mission"
                value={summary.top_missions.length
                  ? fmt(summary.top_missions.reduce((a, m) => a + m.cost, 0) / summary.top_missions.length)
                  : "$0.00"}
                sub="top 5 missions"
              />
              <StatCard
                label="Total Providers"
                value={String(summary.by_provider.length)}
                sub="active this month"
              />
            </div>

            {/* Charts row 1 */}
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
              {/* Daily trend */}
              <Panel title="Daily Spend — Last 30 Days">
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={summary.daily_trend} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#737373" }}
                           tickFormatter={(v) => v.slice(5)} />
                    <YAxis tick={{ fontSize: 10, fill: "#737373" }}
                           tickFormatter={(v) => `$${v.toFixed(3)}`} />
                    <Tooltip
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      formatter={((v: number) => [fmt(v), "Spend"]) as any}
                      contentStyle={{ background: "#121f30", border: "1px solid rgba(255,255,255,0.09)", borderRadius: 8, fontSize: 12 }}
                    />
                    <Bar dataKey="total_cost" fill="#82c0a4" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Panel>

              {/* Provider pie */}
              <Panel title="Provider Breakdown (30d)">
                {summary.by_provider.length === 0 ? (
                  <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "40px 0", fontSize: 13 }}>
                    No cost data yet.<br/>
                    <span style={{ fontSize: 11 }}>Cost records are written on each LLM call.</span>
                  </div>
                ) : (
                  <>
                    <ResponsiveContainer width="100%" height={160}>
                      <PieChart>
                        <Pie data={summary.by_provider} dataKey="total_cost" nameKey="provider"
                             cx="50%" cy="50%" outerRadius={70} innerRadius={40}>
                          {summary.by_provider.map((_, i) => (
                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                          ))}
                        </Pie>
                        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                        <Tooltip formatter={((v: number) => fmt(v)) as any}
                                 contentStyle={{ background: "#121f30", border: "1px solid rgba(255,255,255,0.09)", borderRadius: 8, fontSize: 12 }} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8 }}>
                      {summary.by_provider.map((p, i) => (
                        <div key={p.provider} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                          <span style={{ width: 10, height: 10, borderRadius: 2, background: PIE_COLORS[i % PIE_COLORS.length], flexShrink: 0 }} />
                          <span style={{ flex: 1, color: "var(--text-secondary)", textTransform: "capitalize" }}>{p.provider}</span>
                          <span style={{ color: "var(--text-primary)", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                            {fmt(p.total_cost)}
                          </span>
                          <span style={{ color: "var(--text-muted)", minWidth: 50, textAlign: "right" }}>
                            {totalProviderCost > 0 ? `${((p.total_cost / totalProviderCost) * 100).toFixed(1)}%` : "—"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </Panel>
            </div>

            {/* Charts row 2 */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {/* Most expensive missions */}
              <Panel title="Most Expensive Missions">
                {summary.top_missions.length === 0 ? (
                  <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "30px 0", fontSize: 13 }}>
                    No mission cost data yet.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {summary.top_missions.map((m, i) => (
                      <div key={m.mission_id} style={{
                        display:     "flex",
                        alignItems:  "center",
                        gap:         10,
                        padding:     "8px 12px",
                        background:  "var(--surface, #0d1829)",
                        borderRadius: 8,
                        border:      "1px solid var(--border-subtle)",
                      }}>
                        <span style={{ fontSize: 18, width: 24, textAlign: "center" }}>
                          {["🥇","🥈","🥉","4️⃣","5️⃣"][i] ?? `${i+1}.`}
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 600,
                                       overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {m.mission_id.slice(0, 8)}…
                          </div>
                          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                            {m.calls} call{m.calls !== 1 ? "s" : ""}
                          </div>
                        </div>
                        <span style={{ fontSize: 14, fontWeight: 700, color: "#82c0a4", fontVariantNumeric: "tabular-nums" }}>
                          {fmt(m.cost)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </Panel>

              {/* Monthly trend */}
              <Panel title="Monthly Spend Trend">
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={summary.daily_trend} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#737373" }}
                           tickFormatter={(v) => v.slice(5)} />
                    <YAxis tick={{ fontSize: 10, fill: "#737373" }}
                           tickFormatter={(v) => `$${v.toFixed(3)}`} />
                    <Tooltip
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      formatter={((v: number) => [fmt(v), "Spend"]) as any}
                      contentStyle={{ background: "#121f30", border: "1px solid rgba(255,255,255,0.09)", borderRadius: 8, fontSize: 12 }}
                    />
                    <Line type="monotone" dataKey="total_cost" stroke="#82c0a4" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Panel>
            </div>

            {/* Error notice */}
            {summary.error && (
              <div style={{ fontSize: 12, color: "#f59e0b", padding: "8px 12px", background: "rgba(245,158,11,0.08)",
                            borderRadius: 8, border: "1px solid rgba(245,158,11,0.2)" }}>
                ⚠ Cost data partially unavailable: {summary.error}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  );
}
