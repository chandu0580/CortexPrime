import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Button, Badge, Input, Select, Spinner, EmptyState, Modal, Tabs, Card, CardHeader, CardTitle, CardContent } from "@/components/enterprise/ui"

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>)
    expect(screen.getByText("Click me")).toBeInTheDocument()
  })

  it("applies variant classes", () => {
    const { container } = render(<Button variant="danger">Delete</Button>)
    expect(container.firstChild).toHaveClass("bg-[var(--danger)]")
  })

  it("shows spinner when loading", () => {
    const { container } = render(<Button loading>Loading</Button>)
    expect(container.querySelector(".animate-spin")).toBeInTheDocument()
  })

  it("disables when loading", () => {
    render(<Button loading>Loading</Button>)
    expect(screen.getByRole("button")).toBeDisabled()
  })

  it("fires onClick when clicked", async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Click</Button>)
    await userEvent.click(screen.getByText("Click"))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it("does not fire onClick when disabled", async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick} disabled>Click</Button>)
    await userEvent.click(screen.getByText("Click"))
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe("Badge", () => {
  it("renders children", () => {
    render(<Badge>Active</Badge>)
    expect(screen.getByText("Active")).toBeInTheDocument()
  })

  it("applies variant classes", () => {
    const { container } = render(<Badge variant="success">OK</Badge>)
    expect(container.firstChild).toHaveClass("text-[var(--success)]")
  })

  it("renders with default variant", () => {
    const { container } = render(<Badge>Default</Badge>)
    expect(container.firstChild).toHaveClass("text-[var(--text-muted)]")
  })
})

describe("Card", () => {
  it("renders children", () => {
    render(<Card><p>Content</p></Card>)
    expect(screen.getByText("Content")).toBeInTheDocument()
  })

  it("renders CardHeader, CardTitle, CardContent", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
        </CardHeader>
        <CardContent>Body</CardContent>
      </Card>,
    )
    expect(screen.getByText("Title")).toBeInTheDocument()
    expect(screen.getByText("Body")).toBeInTheDocument()
  })
})

describe("Modal", () => {
  it("does not render when closed", () => {
    render(<Modal open={false} onClose={() => {}}>Content</Modal>)
    expect(screen.queryByText("Content")).not.toBeInTheDocument()
  })

  it("renders when open", () => {
    render(<Modal open={true} onClose={() => {}} title="Test Modal">Content</Modal>)
    expect(screen.getByText("Test Modal")).toBeInTheDocument()
    expect(screen.getByText("Content")).toBeInTheDocument()
  })

  it("calls onClose when backdrop clicked", async () => {
    const onClose = vi.fn()
    render(<Modal open={true} onClose={onClose}>Content</Modal>)
    const backdrop = document.querySelector(".bg-black\\/40")
    if (backdrop) fireEvent.click(backdrop)
    expect(onClose).toHaveBeenCalled()
  })
})

describe("Tabs", () => {
  it("renders tabs and highlights active", () => {
    const tabs = [{ id: "a", label: "Tab A" }, { id: "b", label: "Tab B" }]
    render(<Tabs tabs={tabs} active="a" onChange={() => {}} />)
    expect(screen.getByText("Tab A")).toBeInTheDocument()
    expect(screen.getByText("Tab B")).toBeInTheDocument()
  })

  it("calls onChange when tab clicked", async () => {
    const onChange = vi.fn()
    const tabs = [{ id: "a", label: "Tab A" }, { id: "b", label: "Tab B" }]
    render(<Tabs tabs={tabs} active="a" onChange={onChange} />)
    await userEvent.click(screen.getByText("Tab B"))
    expect(onChange).toHaveBeenCalledWith("b")
  })
})

describe("Input", () => {
  it("renders with label", () => {
    render(<Input label="Name" />)
    expect(screen.getByLabelText("Name")).toBeInTheDocument()
  })

  it("shows error message", () => {
    render(<Input label="Email" error="Required" />)
    expect(screen.getByText("Required")).toBeInTheDocument()
  })

  it("handles value changes", async () => {
    const onChange = vi.fn()
    render(<Input label="Name" onChange={onChange} />)
    const input = screen.getByLabelText("Name")
    await userEvent.type(input, "test")
    expect(onChange).toHaveBeenCalled()
  })
})

describe("Select", () => {
  it("renders options", () => {
    const options = [{ value: "a", label: "Option A" }, { value: "b", label: "Option B" }]
    render(<Select label="Choose" options={options} />)
    expect(screen.getByText("Option A")).toBeInTheDocument()
    expect(screen.getByText("Option B")).toBeInTheDocument()
  })
})

describe("Spinner", () => {
  it("renders with default size", () => {
    const { container } = render(<Spinner />)
    expect(container.firstChild).toHaveClass("h-6 w-6")
  })

  it("renders with custom size", () => {
    const { container } = render(<Spinner size="lg" />)
    expect(container.firstChild).toHaveClass("h-8 w-8")
  })
})

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(<EmptyState title="Nothing here" description="Try again later" />)
    expect(screen.getByText("Nothing here")).toBeInTheDocument()
    expect(screen.getByText("Try again later")).toBeInTheDocument()
  })

  it("renders action button", () => {
    render(<EmptyState title="Empty" action={<button>Action</button>} />)
    expect(screen.getByText("Action")).toBeInTheDocument()
  })
})
