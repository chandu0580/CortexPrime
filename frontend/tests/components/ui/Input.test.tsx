import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import Input from "@/components/ui/Input"

describe("Input", () => {
  it("renders label", () => {
    render(<Input label="Email" />)
    expect(screen.getByText("Email")).toBeInTheDocument()
  })

  it("renders input element", () => {
    render(<Input label="Email" />)
    expect(screen.getByRole("textbox")).toBeInTheDocument()
  })

  it("associates label with input via htmlFor", () => {
    render(<Input label="Username" />)
    const input = screen.getByRole("textbox")
    expect(input).toHaveAttribute("id", "username")
  })

  it("uses custom id when provided", () => {
    render(<Input label="Email" id="custom-email" />)
    const input = screen.getByRole("textbox")
    expect(input).toHaveAttribute("id", "custom-email")
  })

  it("renders left adornment", () => {
    render(<Input label="Search" leftAdornment={<span data-testid="left">L</span>} />)
    expect(screen.getByTestId("left")).toBeInTheDocument()
  })

  it("renders right adornment", () => {
    render(<Input label="Search" rightAdornment={<span data-testid="right">R</span>} />)
    expect(screen.getByTestId("right")).toBeInTheDocument()
  })

  it("applies wrapper className", () => {
    render(<Input label="Email" wrapperClassName="wrapper-class" />)
    const label = screen.getByText("Email")
    expect(label.parentElement?.className).toContain("wrapper-class")
  })

  it("handles value and onChange", async () => {
    const onChange = vi.fn()
    render(<Input label="Name" value="John" onChange={onChange} />)
    const input = screen.getByRole("textbox") as HTMLInputElement
    expect(input.value).toBe("John")
    await userEvent.type(input, "ny")
    expect(onChange).toHaveBeenCalled()
  })

  it("forwards ref", () => {
    const ref = { current: null }
    render(<Input label="Test" ref={ref} />)
    expect(ref.current).toBeInstanceOf(HTMLInputElement)
  })
})
