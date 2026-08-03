/**
 * Graph interaction UI tests — layout switcher and node context menu.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import LayoutSwitcher from "../components/LayoutSwitcher";
import NodeContextMenu, { type ContextMenuAction } from "../components/NodeContextMenu";
import { LAYOUTS } from "../graph/layouts";

describe("LayoutSwitcher", () => {
  it("shows every available layout — a dropdown would hide the alternatives", () => {
    render(<LayoutSwitcher value="cose" onChange={vi.fn()} />);
    for (const l of LAYOUTS) {
      expect(screen.getByRole("button", { name: l.label })).toBeInTheDocument();
    }
  });

  it("marks the active layout for assistive tech, not just visually", () => {
    render(<LayoutSwitcher value="breadthfirst" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Hierarchy" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Force" })).toHaveAttribute("aria-pressed", "false");
  });

  it("reports the chosen layout", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<LayoutSwitcher value="cose" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "Hierarchy" }));
    expect(onChange).toHaveBeenCalledWith("breadthfirst");
  });

  it("is exposed as a labelled group", () => {
    render(<LayoutSwitcher value="cose" onChange={vi.fn()} />);
    expect(screen.getByRole("group", { name: /graph layout/i })).toBeInTheDocument();
  });

  it("explains each layout on hover", async () => {
    const user = userEvent.setup();
    render(<LayoutSwitcher value="cose" onChange={vi.fn()} />);
    await user.hover(screen.getByRole("button", { name: "Hierarchy" }));
    expect(await screen.findByRole("tooltip")).toHaveTextContent(/attack chains/i);
  });
});

describe("NodeContextMenu", () => {
  const actions: ContextMenuAction[] = [
    { id: "open", label: "Open details", onSelect: vi.fn() },
    { id: "delete", label: "Delete node", destructive: true, onSelect: vi.fn() },
  ];

  function setup(overrides = {}) {
    const props = { x: 100, y: 100, title: "api.example.com", actions, onClose: vi.fn(), ...overrides };
    render(<NodeContextMenu {...props} />);
    return props;
  }

  it("names the node it acts on", () => {
    setup();
    expect(screen.getByText("api.example.com")).toBeInTheDocument();
  });

  it("renders each action as a menu item", () => {
    setup();
    expect(screen.getAllByRole("menuitem")).toHaveLength(2);
  });

  it("runs the chosen action and closes", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    const props = setup({ actions: [{ id: "x", label: "Do it", onSelect }] });
    await user.click(screen.getByRole("menuitem", { name: "Do it" }));
    expect(onSelect).toHaveBeenCalled();
    expect(props.onClose).toHaveBeenCalled();
  });

  it("closes on Escape", async () => {
    const props = setup();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(props.onClose).toHaveBeenCalled());
  });

  it("closes on an outside click", async () => {
    const props = setup();
    fireEvent.mouseDown(document.body);
    await waitFor(() => expect(props.onClose).toHaveBeenCalled());
  });

  it("closes on scroll — a viewport-anchored menu goes stale when the canvas pans", async () => {
    const props = setup();
    fireEvent.wheel(window);
    await waitFor(() => expect(props.onClose).toHaveBeenCalled());
  });

  it("stays open when clicking inside itself", async () => {
    const props = setup();
    fireEvent.mouseDown(screen.getByText("api.example.com"));
    expect(props.onClose).not.toHaveBeenCalled();
  });

  it("flips position near the right edge so it stays on screen", () => {
    setup({ x: window.innerWidth - 10 });
    expect(screen.getByRole("menu")).toHaveStyle({ transform: "translate(-100%, 0)" });
  });

  it("renders at the given coordinates otherwise", () => {
    setup({ x: 50, y: 60 });
    const menu = screen.getByRole("menu");
    expect(menu).toHaveStyle({ left: "50px", top: "60px" });
  });
});
