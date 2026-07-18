"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Clock, Filter, CheckCircle, XCircle, Loader2, ArrowUpRight } from "lucide-react";
import { dur, ease } from "@/lib/motion-tokens";
import type { Connector } from "./types";
import { getConnectorActivity } from "@/services/connector-api";
import type { ConnectorActivityEvent } from "@/services/connector-api";

interface ConnectorActivityProps {
  connector: Connector;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 60000) return "Just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString();
}

function EmptyState({ connectorName }: { connectorName: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: dur.base, ease: ease.out }}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "52px 24px",
        textAlign: "center",
        gap: "var(--space-4)",
      }}
    >
      <div style={{
        width: 60, height: 60, borderRadius: "var(--radius-xl)",
        background: "var(--surface-raised)", border: "1px solid var(--border)",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "var(--text-muted)",
      }}>
        <Clock size={26} />
      </div>
      <div>
        <p style={{ fontSize: "var(--font-size-md)", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 6px", letterSpacing: "-0.01em" }}>
          No connector activity yet.
        </p>
        <p style={{ fontSize: "var(--font-size-sm)", color: "var(--text-muted)", margin: 0, maxWidth: 300, lineHeight: 1.65 }}>
          Activity events will appear here once API operations are performed through {connectorName}.
        </p>
      </div>
    </motion.div>
  );
}

function ActivityTimelineSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", padding: "var(--space-2) 0" }}>
      {[1, 2, 3].map((i) => (
        <div key={i} style={{ display: "flex", gap: "var(--space-3)", alignItems: "flex-start", opacity: 1 - i * 0.25 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--border-strong)", marginTop: 5, flexShrink: 0 }} />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ height: 12, width: "65%", borderRadius: 4, background: "var(--surface-raised)" }} />
            <div style={{ height: 10, width: "40%", borderRadius: 4, background: "var(--surface-raised)" }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function ConnectorActivity({ connector }: ConnectorActivityProps) {
  const [events, setEvents] = useState<ConnectorActivityEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  useEffect(() => {
    setLoading(true);
    getConnectorActivity(connector.id, page, pageSize)
      .then((data) => {
        setEvents(data.activities);
        setTotal(data.total);
      })
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [connector.id, page]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        paddingBottom: "var(--space-4)", borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <div style={{
            width: 32, height: 32, borderRadius: "var(--radius-sm)",
            background: "var(--accent-muted)", display: "flex", alignItems: "center",
            justifyContent: "center", color: "var(--accent-primary)",
          }}>
            <Clock size={16} />
          </div>
          <div>
            <p style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
              Activity Timeline
            </p>
            <p style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", margin: 0 }}>
              {total > 0 ? `${total} event(s)` : "Operation history & events"}
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <ActivityTimelineSkeleton />
      ) : events.length === 0 ? (
        <EmptyState connectorName={connector.name} />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {events.map((event) => {
            const isSuccess = event.status === "success";
            return (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: dur.fast, ease: ease.out }}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "var(--space-3)",
                  padding: "10px 12px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                }}
              >
                <div style={{ marginTop: 2, flexShrink: 0 }}>
                  {isSuccess ? (
                    <CheckCircle size={14} style={{ color: "var(--success)" }} />
                  ) : (
                    <XCircle size={14} style={{ color: "var(--danger)" }} />
                  )}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <span style={{ fontSize: "var(--font-size-xs)", fontWeight: 700, color: "var(--text-primary)" }}>
                      {event.operation}
                    </span>
                    {event.resource && (
                      <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
                        {event.resource}
                      </span>
                    )}
                    {event.duration_ms != null && (
                      <span style={{
                        fontSize: 10, fontWeight: 600, color: "var(--text-muted)",
                        marginLeft: "auto",
                      }}>
                        {event.duration_ms}ms
                      </span>
                    )}
                  </div>

                  {event.message && (
                    <p style={{ fontSize: 10, color: "var(--text-secondary)", margin: "2px 0 0", lineHeight: 1.4 }}>
                      {event.message}
                    </p>
                  )}

                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
                    <span style={{ fontSize: 9, color: "var(--text-muted)" }}>
                      {formatTime(event.created_at)}
                    </span>
                    {event.initiated_by && (
                      <>
                        <span style={{ fontSize: 9, color: "var(--text-muted)" }}>·</span>
                        <span style={{ fontSize: 9, color: "var(--text-muted)" }}>
                          {event.initiated_by}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {total > pageSize && (
        <div style={{ display: "flex", justifyContent: "center", gap: "var(--space-2)", paddingTop: "var(--space-2)" }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            style={{
              padding: "6px 14px", borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)", background: "var(--surface)",
              fontSize: "var(--font-size-xs)", fontWeight: 600,
              cursor: page <= 1 ? "not-allowed" : "pointer",
              opacity: page <= 1 ? 0.5 : 1,
            }}
          >
            Previous
          </button>
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--text-muted)", alignSelf: "center" }}>
            Page {page}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page * pageSize >= total}
            style={{
              padding: "6px 14px", borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)", background: "var(--surface)",
              fontSize: "var(--font-size-xs)", fontWeight: 600,
              cursor: page * pageSize >= total ? "not-allowed" : "pointer",
              opacity: page * pageSize >= total ? 0.5 : 1,
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
