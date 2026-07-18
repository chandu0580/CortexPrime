"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Eye, EyeOff, CheckCircle, XCircle, Loader2, Lock, Check } from "lucide-react";
import { dur } from "@/lib/motion-tokens";
import type { Connector } from "./types";
import { testConnector, connectConnector } from "@/services/connector-api";

interface ConnectorAuthenticationProps {
  connector: Connector;
  onConnected?: () => void;
}

type FieldState = "default" | "valid" | "invalid";

export default function ConnectorAuthentication({
  connector,
  onConnected,
}: ConnectorAuthenticationProps) {
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [fieldStates, setFieldStates] = useState<Record<string, FieldState>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [testing, setTesting] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [connectResult, setConnectResult] = useState<{ ok: boolean; message: string } | null>(null);

  function toggleShow(key: string) {
    setShowPasswords((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function handleChange(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }));
    if (fieldStates[key] && fieldStates[key] !== "default") {
      setFieldStates((prev) => ({ ...prev, [key]: "default" }));
    }
    setTestResult(null);
    setConnectResult(null);
  }

  function validate(): boolean {
    const newStates: Record<string, FieldState> = {};
    let hasError = false;
    connector.authFields.forEach((f) => {
      if (!values[f.key]?.trim()) {
        newStates[f.key] = "invalid";
        hasError = true;
      } else {
        newStates[f.key] = "valid";
      }
    });
    setFieldStates(newStates);
    return !hasError;
  }

  async function handleTestConnection() {
    if (!validate()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testConnector(connector.id, values);
      setTestResult({ ok: result.success, message: result.message });
    } catch {
      setTestResult({ ok: false, message: "Connection test failed — backend unavailable" });
    } finally {
      setTesting(false);
    }
  }

  async function handleConnect() {
    if (!validate()) return;
    setConnecting(true);
    setConnectResult(null);
    try {
      const result = await connectConnector(connector.id, values);
      if (result.success) {
        setConnectResult({ ok: true, message: result.message });
        setTimeout(() => onConnected?.(), 800);
      } else {
        setConnectResult({ ok: false, message: result.message });
      }
    } catch {
      setConnectResult({ ok: false, message: "Connection failed — backend unavailable" });
    } finally {
      setConnecting(false);
    }
  }

  function handleCancel() {
    setValues({});
    setFieldStates({});
    setShowPasswords({});
    setTestResult(null);
    setConnectResult(null);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          paddingBottom: "var(--space-4)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "var(--radius-sm)",
            background: "var(--accent-muted)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--accent-primary)",
          }}
        >
          <Lock size={16} />
        </div>
        <div>
          <p
            style={{
              fontSize: "var(--font-size-sm)",
              fontWeight: 700,
              color: "var(--text-primary)",
              margin: 0,
              letterSpacing: "-0.01em",
            }}
          >
            Authentication
          </p>
          <p
            style={{
              fontSize: "var(--font-size-xs)",
              color: "var(--text-muted)",
              margin: 0,
            }}
          >
            All credentials are encrypted at rest and in transit
          </p>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        {connector.authFields.map((field) => {
          const isPassword = field.type === "password";
          const isVisible = showPasswords[field.key];
          const state = fieldStates[field.key] || "default";

          return (
            <div key={field.key} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label
                htmlFor={`auth-${connector.id}-${field.key}`}
                style={{
                  fontSize: "var(--font-size-label)",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  letterSpacing: "-0.01em",
                }}
              >
                {field.label}
                <span style={{ color: "var(--danger)", marginLeft: 3 }}>*</span>
              </label>

              <div style={{ position: "relative" }}>
                <input
                  id={`auth-${connector.id}-${field.key}`}
                  type={isPassword && !isVisible ? "password" : "text"}
                  value={values[field.key] || ""}
                  onChange={(e) => handleChange(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  aria-label={field.label}
                  aria-invalid={state === "invalid"}
                  aria-describedby={state === "invalid" ? `err-${field.key}` : undefined}
                  autoComplete={isPassword ? "new-password" : "off"}
                  style={{
                    width: "100%",
                    height: 44,
                    paddingLeft: 14,
                    paddingRight: isPassword && state !== "default" ? 72 : isPassword || state !== "default" ? 40 : 14,
                    background: "var(--surface)",
                    border: `1px solid ${
                      state === "invalid" ? "var(--danger)" : state === "valid" ? "var(--success)" : "var(--border)"
                    }`,
                    borderRadius: "var(--radius-sm)",
                    color: "var(--text-primary)",
                    fontSize: "var(--font-size-base)",
                    outline: "none",
                    transition: `border-color ${dur.fast}s ease, box-shadow ${dur.fast}s ease`,
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => {
                    if (state === "default") {
                      e.currentTarget.style.borderColor = "var(--accent-primary)";
                      e.currentTarget.style.boxShadow = "0 0 0 3px var(--accent-muted)";
                    }
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.boxShadow = "none";
                    if (state === "default") {
                      e.currentTarget.style.borderColor = "var(--border)";
                    }
                  }}
                />

                {state !== "default" && (
                  <div
                    style={{
                      position: "absolute",
                      right: isPassword ? 38 : 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      display: "flex",
                      alignItems: "center",
                      color: state === "valid" ? "var(--success)" : "var(--danger)",
                      pointerEvents: "none",
                    }}
                    aria-hidden="true"
                  >
                    {state === "valid" ? <CheckCircle size={16} /> : <XCircle size={16} />}
                  </div>
                )}

                {isPassword && (
                  <button
                    type="button"
                    onClick={() => toggleShow(field.key)}
                    aria-label={isVisible ? "Hide password" : "Show password"}
                    style={{
                      position: "absolute",
                      right: 10,
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: "var(--text-muted)",
                      padding: 4,
                      display: "flex",
                      alignItems: "center",
                      borderRadius: 4,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
                  >
                    {isVisible ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                )}
              </div>

              {state === "invalid" && (
                <p id={`err-${field.key}`} role="alert"
                  style={{ fontSize: "var(--font-size-xs)", color: "var(--danger)", margin: 0, display: "flex", alignItems: "center", gap: 4 }}>
                  <XCircle size={11} />
                  This field is required
                </p>
              )}
            </div>
          );
        })}
      </div>

      {testResult && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: "var(--radius-sm)",
            background: testResult.ok ? "var(--success-muted)" : "var(--danger-muted)",
            border: `1px solid ${testResult.ok ? "var(--success-border)" : "var(--danger-border)"}`,
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: "var(--font-size-xs)",
            fontWeight: 600,
            color: testResult.ok ? "var(--success)" : "var(--danger)",
          }}
        >
          {testResult.ok ? <Check size={14} /> : <XCircle size={14} />}
          {testResult.message}
        </div>
      )}

      {connectResult && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: "var(--radius-sm)",
            background: connectResult.ok ? "var(--success-muted)" : "var(--danger-muted)",
            border: `1px solid ${connectResult.ok ? "var(--success-border)" : "var(--danger-border)"}`,
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: "var(--font-size-xs)",
            fontWeight: 600,
            color: connectResult.ok ? "var(--success)" : "var(--danger)",
          }}
        >
          {connectResult.ok ? <Check size={14} /> : <XCircle size={14} />}
          {connectResult.message}
        </div>
      )}

      <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", paddingTop: "var(--space-2)" }}>
        <motion.button
          whileHover={!testing ? { y: -1 } : undefined}
          whileTap={!testing ? { scale: 0.97 } : undefined}
          onClick={handleTestConnection}
          disabled={testing || connecting}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "10px 18px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            background: "var(--surface)",
            color: "var(--text-secondary)",
            fontSize: "var(--font-size-sm)",
            fontWeight: 600,
            cursor: (testing || connecting) ? "not-allowed" : "pointer",
            opacity: (testing || connecting) ? 0.65 : 1,
            letterSpacing: "-0.01em",
            transition: `opacity ${dur.fast}s ease`,
          }}
          aria-label="Test connection"
          aria-busy={testing}
        >
          {testing ? (
            <>
              <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
              Testing...
            </>
          ) : (
            "Test Connection"
          )}
        </motion.button>

        <motion.button
          whileHover={!connecting ? { y: -1 } : undefined}
          whileTap={!connecting ? { scale: 0.97 } : undefined}
          onClick={handleConnect}
          disabled={connecting || testing}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "10px 24px",
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: "var(--accent-primary)",
            color: "var(--text-inverse)",
            fontSize: "var(--font-size-sm)",
            fontWeight: 700,
            cursor: (connecting || testing) ? "not-allowed" : "pointer",
            opacity: (connecting || testing) ? 0.65 : 1,
            letterSpacing: "-0.01em",
            boxShadow: "var(--shadow-accent)",
          }}
          aria-label="Connect"
        >
          {connecting ? (
            <>
              <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
              Connecting...
            </>
          ) : (
            "Connect"
          )}
        </motion.button>

        <motion.button
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.97 }}
          onClick={handleCancel}
          disabled={connecting || testing}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            padding: "10px 18px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            background: "transparent",
            color: "var(--text-secondary)",
            fontSize: "var(--font-size-sm)",
            fontWeight: 500,
            cursor: (connecting || testing) ? "not-allowed" : "pointer",
            opacity: (connecting || testing) ? 0.65 : 1,
            letterSpacing: "-0.01em",
          }}
          aria-label="Cancel"
        >
          Cancel
        </motion.button>
      </div>
    </div>
  );
}
