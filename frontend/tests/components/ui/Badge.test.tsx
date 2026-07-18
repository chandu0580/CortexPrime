import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"

import Badge from "@/components/ui/Badge"

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>Active</Badge>)
    expect(screen.getByText("Active")).toBeInTheDocument()
  })

  it("applies custom className", () => {
    render(<Badge className="custom-class">Styled</Badge>)
    const badge = screen.getByText("Styled")
    expect(badge.className).toContain("custom-class")
  })

  it("renders without crashing with empty children", () => {
    const { container } = render(<Badge />)
    expect(container).toBeTruthy()
  })
})
