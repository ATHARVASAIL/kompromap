/**
 * AI assessment panel tests.
 *
 * Most of these assert *framing* rather than mechanics, which is unusual
 * for component tests but is the point here. An AI assessment that reads
 * as a verdict is worse than no assessment: an analyst rubber-stamps it,
 * and either a fabricated finding or a missed real one ends up in a client
 * report. The wording is the safety feature, so the wording is tested.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AiAssessment from "../components/AiAssessment";
import { ToastProvider } from "../components/ToastProvider";

const ASSESSMENT = {
  assessment: "insufficient_evidence" as const,
  confidence: 0.4,
  severity: "medium" as const,
  reasoning_summary: "The parameter is reflected but the rendering context is unknown.",
  evidence_supporting: ["Parameter value appears in the response body"],
  evidence_missing: ["Whether output encoding is applied"],
  assumptions: ["The response is rendered as HTML"],
  recommended_validation: ["Inspect the rendering context in a browser"],
  potential_impact: ["Session theft if executable"],
  related_vulnerability_types: ["DOM XSS"],
};

/** Routes the two endpoints the component calls. */
function mockApi({
  available = true,
  stored = null as typeof ASSESSMENT | null,
  onAnalyze = null as unknown,
  reason = null as string | null,
}) {
  const spy = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes("/triage/status")) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ available, provider: available ? "anthropic" : "none", reason }),
      } as unknown as Response;
    }
    if (u.includes("/analyze")) {
      return {
        ok: true,
        status: 200,
        json: async () =>
          onAnalyze ?? { finding_id: "f1", available: true, assessment: ASSESSMENT, advisory_only: true },
      } as unknown as Response;
    }
    return {
      ok: true,
      status: 200,
      json: async () =>
        stored
          ? { finding_id: "f1", available: true, assessment: stored, advisory_only: true }
          : { finding_id: "f1", available: false, error: "not analyzed", advisory_only: true },
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderPanel() {
  render(
    <ToastProvider>
      <AiAssessment findingId="f1" />
    </ToastProvider>,
  );
}

beforeEach(() => vi.unstubAllGlobals());

describe("when no provider is configured", () => {
  it("explains why rather than showing a button that always fails", async () => {
    mockApi({ available: false, reason: "No AI provider configured. Set ANTHROPIC_API_KEY." });
    renderPanel();
    expect(await screen.findByText(/no ai provider configured/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /analyze/i })).not.toBeInTheDocument();
  });
});

describe("before analysis", () => {
  it("states up front that it is advisory and changes nothing", async () => {
    mockApi({});
    renderPanel();
    expect(await screen.findByText(/advisory only/i)).toBeInTheDocument();
    expect(screen.getByText(/never changes the finding/i)).toBeInTheDocument();
  });

  it("offers an analyze button", async () => {
    mockApi({});
    renderPanel();
    expect(await screen.findByRole("button", { name: /analyze/i })).toBeInTheDocument();
  });
});

describe("rendering an assessment", () => {
  async function show() {
    mockApi({ stored: ASSESSMENT });
    renderPanel();
    await screen.findByText(/insufficient evidence/i);
  }

  it("keeps evidence, assumptions and missing evidence in separate sections", async () => {
    await show();
    // Collapsing these is how a hedged answer starts reading confident.
    expect(screen.getByText(/evidence supporting/i)).toBeInTheDocument();
    expect(screen.getByText(/evidence missing/i)).toBeInTheDocument();
    expect(screen.getByText(/^assumptions$/i)).toBeInTheDocument();
  });

  it("labels recommended validation as not yet performed", async () => {
    await show();
    expect(screen.getByText(/not yet performed/i)).toBeInTheDocument();
  });

  it("states the model never touched the target", async () => {
    await show();
    expect(screen.getByText(/no network access and did not interact with the target/i)).toBeInTheDocument();
  });

  it("calls the severity a suggestion, not a value", async () => {
    await show();
    expect(screen.getByText(/suggests medium/i)).toBeInTheDocument();
  });

  it("shows impact as conditional on confirmation", async () => {
    await show();
    expect(screen.getByText(/potential impact if confirmed/i)).toBeInTheDocument();
  });

  it("shows the confidence figure", async () => {
    await show();
    expect(screen.getByText(/40% confidence/i)).toBeInTheDocument();
  });

  it("foregrounds the caveats when confidence is low", async () => {
    await show();
    expect(screen.getByText(/treat the missing-evidence list/i)).toBeInTheDocument();
  });

  it("does not warn about confidence when it is high", async () => {
    mockApi({ stored: { ...ASSESSMENT, confidence: 0.9 } });
    renderPanel();
    await screen.findByText(/90% confidence/i);
    expect(screen.queryByText(/treat the missing-evidence list/i)).not.toBeInTheDocument();
  });

  it("offers no control that changes the finding", async () => {
    await show();
    // Confirming/dismissing lives in the verification control, where a
    // human does it. An AI panel with a "mark false positive" button is
    // how rubber-stamping starts.
    const buttons = screen.getAllByRole("button").map((b) => b.textContent?.toLowerCase() ?? "");
    for (const forbidden of ["confirm", "false positive", "dismiss", "accept"]) {
      expect(buttons.some((t) => t.includes(forbidden))).toBe(false);
    }
  });
});

describe("running analysis", () => {
  it("requests analysis and renders the result", async () => {
    const spy = mockApi({});
    const user = userEvent.setup();
    renderPanel();
    await user.click(await screen.findByRole("button", { name: /analyze/i }));
    await waitFor(() => expect(screen.getByText(/insufficient evidence/i)).toBeInTheDocument());
    expect(spy.mock.calls.some(([u]) => String(u).includes("/analyze"))).toBe(true);
  });

  it("surfaces a provider failure inline rather than silently doing nothing", async () => {
    mockApi({
      onAnalyze: {
        finding_id: "f1",
        available: false,
        error: "The AI provider timed out. Try again.",
        advisory_only: true,
      },
    });
    const user = userEvent.setup();
    renderPanel();
    await user.click(await screen.findByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/timed out/i)).toBeInTheDocument();
  });

  it("lets you re-analyze once an assessment exists", async () => {
    mockApi({ stored: ASSESSMENT });
    renderPanel();
    expect(await screen.findByRole("button", { name: /re-analyze/i })).toBeInTheDocument();
  });
});
