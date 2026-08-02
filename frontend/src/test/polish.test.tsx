/**
 * Tests for the polish-pass components.
 *
 * The threat gauge in particular does real arithmetic (inverting path cost
 * into an exposure score and banding it), which is exactly the kind of
 * thing that can be silently wrong — a mislabelled risk level looks
 * perfectly fine on screen.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ThreatGauge from "../components/ThreatGauge";
import Tooltip from "../components/Tooltip";
import { useCountUp } from "../hooks/useCountUp";

describe("ThreatGauge", () => {
  const base = { pathCount: 1, crownJewelCount: 1, entryPointCount: 1 };

  it("shows critical exposure for a near-zero cost chain", () => {
    render(<ThreatGauge {...base} bestPathCost={0.1} />);
    expect(screen.getByText(/critical exposure/i)).toBeInTheDocument();
  });

  it("shows limited exposure for an expensive chain", () => {
    render(<ThreatGauge {...base} bestPathCost={2.8} />);
    expect(screen.getByText(/limited exposure/i)).toBeInTheDocument();
  });

  it("inverts cost correctly — cheaper attack means higher exposure", () => {
    const { unmount } = render(<ThreatGauge {...base} bestPathCost={0.25} />);
    const cheap = Number(screen.getByTestId("exposure-value").textContent);
    unmount();
    render(<ThreatGauge {...base} bestPathCost={2.5} />);
    const pricey = Number(screen.getByTestId("exposure-value").textContent);
    expect(cheap).toBeGreaterThan(pricey);
  });

  it("explains what to do when nothing is tagged yet", () => {
    render(
      <ThreatGauge bestPathCost={null} pathCount={0} crownJewelCount={0} entryPointCount={0} />,
    );
    expect(screen.getByText(/tag at least one entry point/i)).toBeInTheDocument();
  });

  it("distinguishes 'nothing tagged' from 'tagged but unreachable'", () => {
    render(
      <ThreatGauge bestPathCost={null} pathCount={0} crownJewelCount={2} entryPointCount={3} />,
    );
    expect(screen.getByText(/no chain connects/i)).toBeInTheDocument();
  });

  it("shows a dash rather than a misleading zero when there's no path", () => {
    render(
      <ThreatGauge bestPathCost={null} pathCount={0} crownJewelCount={1} entryPointCount={1} />,
    );
    expect(screen.getByTestId("exposure-value")).toHaveTextContent("—");
  });

  it("surfaces the counts it was given", () => {
    render(
      <ThreatGauge bestPathCost={0.5} pathCount={4} crownJewelCount={2} entryPointCount={6} />,
    );
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("clamps out-of-range costs instead of producing a nonsense score", () => {
    render(<ThreatGauge {...base} bestPathCost={99} />);
    // Cost far above the expected range must floor at limited, not go negative.
    expect(screen.getByText(/limited exposure/i)).toBeInTheDocument();
  });
});

describe("useCountUp", () => {
  it("settles on the target value", async () => {
    const { result } = renderHook(() => useCountUp(42, 50));
    await waitFor(() => expect(result.current).toBe(42));
  });

  it("returns 0 immediately without animating", () => {
    const { result } = renderHook(() => useCountUp(0));
    expect(result.current).toBe(0);
  });

  it("skips the animation when reduced motion is preferred", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({
      matches: q.includes("reduce"),
      media: q,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const { result } = renderHook(() => useCountUp(500));
    expect(result.current).toBe(500); // straight to the target, no tween
    vi.unstubAllGlobals();
  });
});

describe("Tooltip", () => {
  it("stays hidden until asked for", () => {
    render(
      <Tooltip label="Explains the thing">
        <button>hover me</button>
      </Tooltip>,
    );
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("appears on hover", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip label="Explains the thing">
        <button>hover me</button>
      </Tooltip>,
    );
    await user.hover(screen.getByRole("button"));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Explains the thing");
  });

  it("also appears on keyboard focus — hover-only would exclude keyboard users", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip label="Keyboard reachable">
        <button>focus me</button>
      </Tooltip>,
    );
    await user.tab();
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();
  });

  it("hides again on unhover", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip label="Transient">
        <button>hover me</button>
      </Tooltip>,
    );
    await user.hover(screen.getByRole("button"));
    await screen.findByRole("tooltip");
    await user.unhover(screen.getByRole("button"));
    await waitFor(() => expect(screen.queryByRole("tooltip")).not.toBeInTheDocument());
  });
});
