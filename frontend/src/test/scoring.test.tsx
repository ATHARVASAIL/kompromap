/**
 * Scoring UI tests.
 *
 * These two components exist to answer "why is this chain ranked first?",
 * so a wrong number here isn't cosmetic — it misexplains the product's
 * core output. The measured-vs-assumed distinction especially: showing an
 * assumed complexity with the same confidence as a measured one would
 * overstate what the tool actually knows.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ScoreExplainer from "../components/ScoreExplainer";
import ScoringWeightsPanel from "../components/ScoringWeightsPanel";
import { DEFAULT_WEIGHTS } from "../components/scoringDefaults";
import type { ScoreBreakdown } from "../types/graph";

const MEASURED: ScoreBreakdown = {
  ease_score: 0.991,
  normalized_cvss: 1.0,
  exploit_public: 1.0,
  unauthenticated: 1.0,
  complexity: 0.09,
  complexity_measured: true,
  contributions: { cvss: 0.4, exploit_public: 0.3, unauthenticated: 0.2, complexity: 0.091 },
};

const ASSUMED: ScoreBreakdown = {
  ...MEASURED,
  complexity: 0.5,
  complexity_measured: false,
  contributions: { ...MEASURED.contributions, complexity: 0.05 },
};

describe("ScoreExplainer", () => {
  it("shows the step cost it is explaining", () => {
    render(<ScoreExplainer breakdown={MEASURED} cost={0.009} />);
    expect(screen.getByText(/why this step costs 0\.009/i)).toBeInTheDocument();
  });

  it("lists every contributing term", () => {
    render(<ScoreExplainer breakdown={MEASURED} cost={0.009} />);
    expect(screen.getByText("CVSS")).toBeInTheDocument();
    expect(screen.getByText("public exploit")).toBeInTheDocument();
    expect(screen.getByText("no auth")).toBeInTheDocument();
    expect(screen.getByText("low complexity")).toBeInTheDocument();
  });

  it("marks a vector-derived complexity as measured", () => {
    render(<ScoreExplainer breakdown={MEASURED} cost={0.009} />);
    expect(screen.getByText("measured")).toBeInTheDocument();
  });

  it("marks a fallback complexity as assumed — not the same confidence", () => {
    render(<ScoreExplainer breakdown={ASSUMED} cost={0.5} />);
    expect(screen.getByText("assumed")).toBeInTheDocument();
    expect(screen.queryByText("measured")).not.toBeInTheDocument();
  });

  it("shows the resulting ease score", () => {
    render(<ScoreExplainer breakdown={MEASURED} cost={0.009} />);
    expect(screen.getByText("0.991")).toBeInTheDocument();
  });

  it("omits zero-valued terms rather than rendering empty bars", () => {
    const partial: ScoreBreakdown = {
      ...MEASURED,
      contributions: { cvss: 0.4, exploit_public: 0, unauthenticated: 0, complexity: 0.05 },
    };
    render(<ScoreExplainer breakdown={partial} cost={0.55} />);
    expect(screen.getByText("CVSS")).toBeInTheDocument();
    expect(screen.queryByText("public exploit")).not.toBeInTheDocument();
  });
});

describe("ScoringWeightsPanel", () => {
  function setup(overrides = {}) {
    const props = {
      weights: DEFAULT_WEIGHTS,
      onChange: vi.fn(),
      onApply: vi.fn(),
      ...overrides,
    };
    render(<ScoringWeightsPanel {...props} />);
    return props;
  }

  it("starts collapsed to keep the panel uncluttered", () => {
    setup();
    expect(screen.queryByText(/tune how the model ranks/i)).not.toBeInTheDocument();
  });

  it("expands on click", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: /scoring weights/i }));
    expect(await screen.findByText(/tune how the model ranks/i)).toBeInTheDocument();
  });

  it("shows each weight as a percentage share — a bare 0.4 means nothing alone", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: /scoring weights/i }));
    expect(screen.getByText("40%")).toBeInTheDocument(); // cvss 0.4 of 1.0
    expect(screen.getByText("30%")).toBeInTheDocument();
  });

  it("reports a change when a slider moves", async () => {
    const user = userEvent.setup();
    const props = setup();
    await user.click(screen.getByRole("button", { name: /scoring weights/i }));
    // Range inputs don't respond to typing — set the value directly and
    // fire change, which is what a drag produces.
    const slider = screen.getByLabelText(/CVSS severity/i) as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "0.75" } });
    await waitFor(() => expect(props.onChange).toHaveBeenCalled());
    expect(props.onChange.mock.calls[0][0].cvss).toBe(0.75);
  });

  it("flags when weights differ from the defaults", async () => {
    const user = userEvent.setup();
    setup({ weights: { ...DEFAULT_WEIGHTS, cvss: 0.9 } });
    expect(screen.getByText("tuned")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /scoring weights/i }));
    expect(screen.getByRole("button", { name: /reset/i })).toBeEnabled();
  });

  it("disables reset when already at defaults", async () => {
    const user = userEvent.setup();
    setup();
    expect(screen.queryByText("tuned")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /scoring weights/i }));
    expect(screen.getByRole("button", { name: /reset/i })).toBeDisabled();
  });

  it("restores defaults on reset", async () => {
    const user = userEvent.setup();
    const props = setup({ weights: { ...DEFAULT_WEIGHTS, cvss: 0.9 } });
    await user.click(screen.getByRole("button", { name: /scoring weights/i }));
    await user.click(screen.getByRole("button", { name: /reset/i }));
    expect(props.onChange).toHaveBeenCalledWith(DEFAULT_WEIGHTS);
  });

  it("triggers a recompute on apply", async () => {
    const user = userEvent.setup();
    const props = setup();
    await user.click(screen.getByRole("button", { name: /scoring weights/i }));
    await user.click(screen.getByRole("button", { name: /apply/i }));
    expect(props.onApply).toHaveBeenCalled();
  });

  it("shows a busy state while recomputing", async () => {
    const user = userEvent.setup();
    setup({ busy: true });
    await user.click(screen.getByRole("button", { name: /scoring weights/i }));
    expect(screen.getByRole("button", { name: /recomputing/i })).toBeDisabled();
  });

  it("explains that the fallback only applies without a CVSS vector", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: /scoring weights/i }));
    expect(screen.getByText(/only applies where no CVSS vector is available/i)).toBeInTheDocument();
  });
});
