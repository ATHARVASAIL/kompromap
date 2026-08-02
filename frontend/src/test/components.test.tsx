/**
 * Shared UI component tests — toasts, error/empty states, and the command
 * palette's keyboard navigation (which is pure logic and easy to break
 * without noticing, since nothing throws when arrow keys stop working).
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import CommandPalette, { type Command } from "../components/CommandPalette";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import ShortcutsHelp from "../components/ShortcutsHelp";
import Spinner from "../components/Spinner";
import { ToastProvider } from "../components/ToastProvider";
import { useToast } from "../components/toastContext";

describe("ErrorBanner", () => {
  it("shows the message", () => {
    render(<ErrorBanner message="Something broke" />);
    expect(screen.getByText("Something broke")).toBeInTheDocument();
  });

  it("accepts extra layout classes without dropping its own", () => {
    const { container } = render(<ErrorBanner message="x" className="mt-4" />);
    const el = container.firstElementChild!;
    expect(el.className).toContain("mt-4");
    expect(el.className).toContain("severity-critical");
  });
});

describe("EmptyState", () => {
  it("shows the message", () => {
    render(<EmptyState message="No snapshots yet." />);
    expect(screen.getByText("No snapshots yet.")).toBeInTheDocument();
  });
});

describe("Spinner", () => {
  it("is hidden from screen readers — it conveys no information on its own", () => {
    const { container } = render(<Spinner />);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});

function ToastTrigger({ kind }: { kind?: "success" | "error" | "info" }) {
  const { toast } = useToast();
  return (
    <button onClick={() => toast("Saved it", kind)}>fire</button>
  );
}

describe("ToastProvider", () => {
  it("shows a toast when fired", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );
    await user.click(screen.getByRole("button", { name: "fire" }));
    expect(await screen.findByText("Saved it")).toBeInTheDocument();
  });

  it("auto-dismisses after its timeout", async () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <ToastTrigger />
        </ToastProvider>,
      );
      // userEvent doesn't play well with fake timers; click directly.
      act(() => {
        screen.getByRole("button", { name: "fire" }).click();
      });
      expect(screen.getByText("Saved it")).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(4000);
      });
      expect(screen.queryByText("Saved it")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("throws a clear error if used outside the provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<ToastTrigger />)).toThrow(/ToastProvider/);
    spy.mockRestore();
  });
});

describe("ShortcutsHelp", () => {
  it("documents the shortcuts the app actually binds", () => {
    render(<ShortcutsHelp onClose={vi.fn()} />);
    expect(screen.getByText(/Ctrl\/Cmd \+ K/)).toBeInTheDocument();
    expect(screen.getByText("/")).toBeInTheDocument();
    expect(screen.getByText("f")).toBeInTheDocument();
    expect(screen.getByText("Esc")).toBeInTheDocument();
  });

  it("closes on the close button", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ShortcutsHelp onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: /close/i }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe("CommandPalette", () => {
  const commands: Command[] = [
    { id: "a", label: "Go to Graph", action: vi.fn() },
    { id: "b", label: "Go to Findings", action: vi.fn() },
    { id: "c", label: "Create node", keywords: "add asset", action: vi.fn() },
  ];

  it("lists every command initially", () => {
    render(<CommandPalette commands={commands} onClose={vi.fn()} />);
    expect(screen.getByText("Go to Graph")).toBeInTheDocument();
    expect(screen.getByText("Create node")).toBeInTheDocument();
  });

  it("filters as you type", async () => {
    const user = userEvent.setup();
    render(<CommandPalette commands={commands} onClose={vi.fn()} />);
    await user.type(screen.getByPlaceholderText(/type a command/i), "findings");
    expect(screen.getByText("Go to Findings")).toBeInTheDocument();
    expect(screen.queryByText("Go to Graph")).not.toBeInTheDocument();
  });

  it("matches on keywords, not just the visible label", async () => {
    const user = userEvent.setup();
    render(<CommandPalette commands={commands} onClose={vi.fn()} />);
    await user.type(screen.getByPlaceholderText(/type a command/i), "asset");
    expect(screen.getByText("Create node")).toBeInTheDocument();
  });

  it("runs the highlighted command on Enter", async () => {
    const action = vi.fn();
    const user = userEvent.setup();
    render(
      <CommandPalette commands={[{ id: "x", label: "Only one", action }]} onClose={vi.fn()} />,
    );
    await user.keyboard("{Enter}");
    expect(action).toHaveBeenCalled();
  });

  it("moves the selection with arrow keys", async () => {
    const second = vi.fn();
    const user = userEvent.setup();
    render(
      <CommandPalette
        commands={[
          { id: "1", label: "First", action: vi.fn() },
          { id: "2", label: "Second", action: second },
        ]}
        onClose={vi.fn()}
      />,
    );
    await user.keyboard("{ArrowDown}{Enter}");
    expect(second).toHaveBeenCalled();
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<CommandPalette commands={commands} onClose={onClose} />);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("says so when nothing matches, rather than showing a blank list", async () => {
    const user = userEvent.setup();
    render(<CommandPalette commands={commands} onClose={vi.fn()} />);
    await user.type(screen.getByPlaceholderText(/type a command/i), "zzzzz");
    await waitFor(() => expect(screen.getByText(/no matching commands/i)).toBeInTheDocument());
  });
});
