import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ThemeProvider, useTheme } from "@/components/theme/ThemeProvider"

function TestConsumer() {
  const { theme, setTheme, toggle, isDark } = useTheme()
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="isDark">{String(isDark)}</span>
      <button data-testid="toggle" onClick={toggle}>Toggle</button>
      <button data-testid="set-light" onClick={() => setTheme("cortex-light")}>Light</button>
      <button data-testid="set-dark" onClick={() => setTheme("cortex-dark")}>Dark</button>
    </div>
  )
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove("cortex-dark", "cortex-light")
  })

  it("renders children", () => {
    render(<ThemeProvider><div>child</div></ThemeProvider>)
    expect(screen.getByText("child")).toBeInTheDocument()
  })

  it("provides default theme as cortex-light", () => {
    render(<ThemeProvider><TestConsumer /></ThemeProvider>)
    expect(screen.getByTestId("theme").textContent).toBe("cortex-light")
  })

  it("isDark is false for light theme", () => {
    render(<ThemeProvider><TestConsumer /></ThemeProvider>)
    expect(screen.getByTestId("isDark").textContent).toBe("false")
  })

  it("toggle switches theme", async () => {
    render(<ThemeProvider><TestConsumer /></ThemeProvider>)
    await userEvent.click(screen.getByTestId("toggle"))
    expect(screen.getByTestId("theme").textContent).toBe("cortex-dark")
    expect(screen.getByTestId("isDark").textContent).toBe("true")
  })

  it("toggle switches back to light", async () => {
    render(<ThemeProvider><TestConsumer /></ThemeProvider>)
    await userEvent.click(screen.getByTestId("toggle"))
    expect(screen.getByTestId("theme").textContent).toBe("cortex-dark")
    await userEvent.click(screen.getByTestId("toggle"))
    expect(screen.getByTestId("theme").textContent).toBe("cortex-light")
  })

  it("setTheme sets specific theme", async () => {
    render(<ThemeProvider><TestConsumer /></ThemeProvider>)
    await userEvent.click(screen.getByTestId("set-dark"))
    expect(screen.getByTestId("theme").textContent).toBe("cortex-dark")
  })

  it("persists theme to localStorage", async () => {
    render(<ThemeProvider><TestConsumer /></ThemeProvider>)
    await userEvent.click(screen.getByTestId("set-dark"))
    expect(localStorage.getItem("cortex-theme")).toBe("cortex-dark")
  })

  it("applies theme class to document root", async () => {
    render(<ThemeProvider><TestConsumer /></ThemeProvider>)
    await userEvent.click(screen.getByTestId("set-dark"))
    expect(document.documentElement.classList.contains("cortex-dark")).toBe(true)
  })

  it("reads initial theme from localStorage", () => {
    localStorage.setItem("cortex-theme", "cortex-dark")
    render(<ThemeProvider><TestConsumer /></ThemeProvider>)
    expect(screen.getByTestId("theme").textContent).toBe("cortex-dark")
  })
})
