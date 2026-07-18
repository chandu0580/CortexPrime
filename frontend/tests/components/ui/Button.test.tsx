import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

vi.mock("framer-motion", () => ({
  motion: {
    button: "button",
  },
}))

import Button from "@/components/ui/Button"

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>)
    expect(screen.getByText("Click me")).toBeInTheDocument()
  })

  it("applies primary variant by default", () => {
    render(<Button>Primary</Button>)
    const btn = screen.getByRole("button", { name: /primary/i })
    expect(btn.className).toContain("bg-[#38B88A]")
  })

  it("applies secondary variant classes", () => {
    render(<Button variant="secondary">Secondary</Button>)
    const btn = screen.getByRole("button", { name: /secondary/i })
    expect(btn.className).toContain("bg-white")
  })

  it("applies ghost variant classes", () => {
    render(<Button variant="ghost">Ghost</Button>)
    const btn = screen.getByRole("button", { name: /ghost/i })
    expect(btn.className).toContain("bg-transparent")
  })

  it("applies lg size by default", () => {
    render(<Button>Large</Button>)
    const btn = screen.getByRole("button", { name: /large/i })
    expect(btn.className).toContain("h-14")
  })

  it("applies md size classes", () => {
    render(<Button size="md">Medium</Button>)
    const btn = screen.getByRole("button", { name: /medium/i })
    expect(btn.className).toContain("h-11")
  })

  it("shows spinner when loading", () => {
    render(<Button loading>Loading</Button>)
    const spinner = document.querySelector("svg.animate-spin")
    expect(spinner).toBeTruthy()
  })

  it("disables button when loading", () => {
    render(<Button loading>Loading</Button>)
    expect(screen.getByRole("button")).toBeDisabled()
  })

  it("disables button when disabled", () => {
    render(<Button disabled>Disabled</Button>)
    expect(screen.getByRole("button")).toBeDisabled()
  })

  it("does not fire onClick when disabled", async () => {
    const onClick = vi.fn()
    render(<Button disabled onClick={onClick}>Disabled</Button>)
    await userEvent.click(screen.getByRole("button"))
    expect(onClick).not.toHaveBeenCalled()
  })

  it("fires onClick when clicked", async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Click</Button>)
    await userEvent.click(screen.getByRole("button", { name: /click/i }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it("renders left icon", () => {
    render(<Button leftIcon={<span data-testid="left-icon">L</span>}>Icon</Button>)
    expect(screen.getByTestId("left-icon")).toBeInTheDocument()
  })

  it("renders right icon when not loading", () => {
    render(<Button rightIcon={<span data-testid="right-icon">R</span>}>Icon</Button>)
    expect(screen.getByTestId("right-icon")).toBeInTheDocument()
  })

  it("hides right icon when loading", () => {
    render(<Button loading rightIcon={<span data-testid="right-icon">R</span>}>Loading</Button>)
    expect(screen.queryByTestId("right-icon")).not.toBeInTheDocument()
  })

  it("merges custom className", () => {
    render(<Button className="custom-class">Styled</Button>)
    expect(screen.getByRole("button").className).toContain("custom-class")
  })
})
