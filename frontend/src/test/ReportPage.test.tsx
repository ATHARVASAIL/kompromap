/**
 * Report page tests.
 *
 * The preview deliberately surfaces the summary *and the caveats* — the
 * two things worth checking before handing a report to a client. A page
 * that quietly dropped the caveats would let someone ship a document
 * implying more rigour than was performed, so that's pinned down here.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReportPage from "../pages/ReportPage";
import { ToastProvider } from "../components/ToastProvider";

const REPORT = {
  summary: {
    total_findings: 44,
    severity_counts: { Critical: 4, High: 17, Medium: 11, Low: 7, Informational: 5 },
    chain_count: 2,
    easiest_chain_cost: 0.009,
    findings_on_a_chain: 2,
    entry_point_count: 3,
    crown_jewel_count: 1,
    total_nodes: 142,
    findings_with_measured_complexity: 18,
  },
  caveats: [
    "26 of 44 findings have no CVSS vector, so their attack complexity is an assumed default.",
    "19 Critical/High findings do not appear on any computed chain.",
  ],
  remediation: [
    { rank: 1, title: "Log4Shell", severity: "Critical", breaks_chain: true, rationale: ["on attack chain #1"] },
    { rank: 2, title: "Stored XSS", severity: "High", breaks_chain: true, rationale: ["on attack chain #2"] },
    { rank: 3, title: "Orphan critical", severity: "Critical", breaks_chain: false, rationale: ["severity only"] },
  ],
  chains: [{ rank: 1, entry_point: "api.test", crown_jewel: "pii_db", total_cost: 0.009 }],
};

function mockReport(body: unknown = { format: "json", data: REPORT }) {
  const spy = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => body,
  } as unknown as Response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderPage() {
  render(
    <ToastProvider>
      <ReportPage engagementId="eng-1" engagementName="Acme Fin" />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("before generating", () => {
  it("explains what the report contains", () => {
    mockReport();
    renderPage();
    expect(screen.getByText(/executive summary, every/i)).toBeInTheDocument();
  });

  it("prompts you to generate rather than showing an empty shell", () => {
    mockReport();
    renderPage();
    expect(screen.getByText(/generate a report to preview/i)).toBeInTheDocument();
  });

  it("offers no export buttons until there is something to export", () => {
    mockReport();
    renderPage();
    expect(screen.queryByRole("button", { name: /\.html/ })).not.toBeInTheDocument();
  });
});

describe("after generating", () => {
  async function generate() {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /generate report/i }));
    await screen.findByText("44");
    return user;
  }

  it("shows the headline counts", async () => {
    mockReport();
    await generate();
    expect(screen.getByText("44")).toBeInTheDocument(); // findings
    expect(screen.getByText("142")).toBeInTheDocument(); // nodes
  });

  it("breaks findings down by severity", async () => {
    mockReport();
    await generate();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("17")).toBeInTheDocument(); // High count
  });

  it("shows the caveats — a report must state what it doesn't know", async () => {
    mockReport();
    await generate();
    expect(screen.getByText(/what this report does not know/i)).toBeInTheDocument();
    expect(screen.getByText(/no CVSS vector/i)).toBeInTheDocument();
  });

  it("lists remediation priorities", async () => {
    mockReport();
    await generate();
    expect(screen.getByText("Log4Shell")).toBeInTheDocument();
  });

  it("marks which fixes break an attack chain", async () => {
    mockReport();
    await generate();
    expect(screen.getAllByText(/breaks a chain/i).length).toBeGreaterThan(0);
  });

  it("explains that ranking is chain-aware, not severity-aware", async () => {
    mockReport();
    await generate();
    expect(screen.getByText(/ranked by chain impact, not raw severity/i)).toBeInTheDocument();
  });

  it("offers all three export formats", async () => {
    mockReport();
    await generate();
    for (const ext of [".html", ".md", ".json"]) {
      expect(screen.getByRole("button", { name: ext })).toBeInTheDocument();
    }
  });

  it("lets you regenerate", async () => {
    mockReport();
    await generate();
    expect(screen.getByRole("button", { name: /regenerate/i })).toBeInTheDocument();
  });
});

describe("options and errors", () => {
  it("passes the narrative flag through to the API", async () => {
    const spy = mockReport();
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByLabelText(/include written narratives/i));
    await user.click(screen.getByRole("button", { name: /generate report/i }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    const body = JSON.parse(String(spy.mock.calls[0][1].body));
    expect(body.include_narratives).toBe(true);
  });

  it("requests the JSON format for the preview", async () => {
    const spy = mockReport();
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /generate report/i }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(JSON.parse(String(spy.mock.calls[0][1].body)).format).toBe("json");
  });

  it("surfaces a failure instead of silently showing nothing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({ detail: "boom" }),
      } as unknown as Response),
    );
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /generate report/i }));
    expect(await screen.findByText(/500/)).toBeInTheDocument();
  });
});
