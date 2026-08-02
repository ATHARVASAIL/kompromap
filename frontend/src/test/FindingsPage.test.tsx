/**
 * FindingsPage + Badge tests.
 *
 * The sort/filter logic here is pure enough to break silently — a bad
 * severity comparator just shows rows in the wrong order, with nothing
 * throwing to signal it.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FindingsPage from "../pages/FindingsPage";
import { NodeTypeBadge, ScopeBadge, SeverityBadge, StatusBadge } from "../components/Badge";

const FINDINGS = [
  { id: "1", node_type: "finding", title: "Log4Shell RCE", cwe: "CWE-502", cvss_score: 10.0, exploit_public: true, auth_required: false, status: "open", is_entry_point: false, is_crown_jewel: false, notes: null, created_at: "", updated_at: "" },
  { id: "2", node_type: "finding", title: "Reflected XSS", cwe: "CWE-79", cvss_score: 6.1, exploit_public: false, auth_required: true, status: "open", is_entry_point: false, is_crown_jewel: false, notes: null, created_at: "", updated_at: "" },
  { id: "3", node_type: "finding", title: "Missing HSTS", cwe: "CWE-319", cvss_score: 3.1, exploit_public: false, auth_required: false, status: "fixed", is_entry_point: false, is_crown_jewel: false, notes: null, created_at: "", updated_at: "" },
  { id: "4", node_type: "finding", title: "Verbose banner", cwe: null, cvss_score: null, exploit_public: false, auth_required: false, status: "accepted-risk", is_entry_point: false, is_crown_jewel: false, notes: null, created_at: "", updated_at: "" },
];

function mockFindings(rows = FINDINGS) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => rows } as unknown as Response),
  );
}

function rowTitles(): string[] {
  const rows = screen.getAllByRole("row").slice(1); // drop header
  return rows.map((r) => within(r).getAllByRole("cell")[1].textContent ?? "");
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("Badge components", () => {
  it("labels each severity", () => {
    const { rerender } = render(<SeverityBadge severity="critical" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
    rerender(<SeverityBadge severity="info" />);
    expect(screen.getByText("Info")).toBeInTheDocument();
  });

  it("labels each finding status", () => {
    const { rerender } = render(<StatusBadge status="open" />);
    expect(screen.getByText("Open")).toBeInTheDocument();
    rerender(<StatusBadge status="accepted-risk" />);
    expect(screen.getByText("Accepted risk")).toBeInTheDocument();
  });

  it("renders in/out of scope as words, not raw booleans", () => {
    const { rerender } = render(<ScopeBadge inScope />);
    expect(screen.getByText("In scope")).toBeInTheDocument();
    rerender(<ScopeBadge inScope={false} />);
    expect(screen.getByText("Out of scope")).toBeInTheDocument();
    expect(screen.queryByText("false")).not.toBeInTheDocument();
  });

  it("uses the human label for node types", () => {
    render(<NodeTypeBadge nodeType="data_store" />);
    expect(screen.getByText("Data Store")).toBeInTheDocument();
  });
});

describe("FindingsPage", () => {
  it("loads and lists every finding", async () => {
    mockFindings();
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    expect(await screen.findByText("Log4Shell RCE")).toBeInTheDocument();
    expect(screen.getByText("Reflected XSS")).toBeInTheDocument();
    expect(screen.getByText("Missing HSTS")).toBeInTheDocument();
  });

  it("derives severity from CVSS rather than requiring a stored field", async () => {
    mockFindings();
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    await screen.findByText("Log4Shell RCE");
    // Scope to the table — the severity <select> also contains these labels.
    const table = screen.getByRole("table");
    expect(within(table).getByText("Critical")).toBeInTheDocument(); // 10.0
    expect(within(table).getByText("Medium")).toBeInTheDocument(); // 6.1
    expect(within(table).getByText("Low")).toBeInTheDocument(); // 3.1
    expect(within(table).getByText("Info")).toBeInTheDocument(); // null
  });

  it("sorts most severe first by default", async () => {
    mockFindings();
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    await screen.findByText("Log4Shell RCE");
    expect(rowTitles()[0]).toBe("Log4Shell RCE");
  });

  it("filters by search term", async () => {
    mockFindings();
    const user = userEvent.setup();
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    await screen.findByText("Log4Shell RCE");
    await user.type(screen.getByPlaceholderText(/search title or CWE/i), "XSS");
    await waitFor(() => expect(screen.queryByText("Log4Shell RCE")).not.toBeInTheDocument());
    expect(screen.getByText("Reflected XSS")).toBeInTheDocument();
  });

  it("searches CWE as well as title", async () => {
    mockFindings();
    const user = userEvent.setup();
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    await screen.findByText("Log4Shell RCE");
    await user.type(screen.getByPlaceholderText(/search title or CWE/i), "CWE-79");
    await waitFor(() => expect(screen.getByText("Reflected XSS")).toBeInTheDocument());
    expect(screen.queryByText("Log4Shell RCE")).not.toBeInTheDocument();
  });

  it("filters by severity band", async () => {
    mockFindings();
    const user = userEvent.setup();
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    await screen.findByText("Log4Shell RCE");
    await user.selectOptions(screen.getByDisplayValue(/all severities/i), "critical");
    await waitFor(() => expect(screen.queryByText("Reflected XSS")).not.toBeInTheDocument());
    expect(screen.getByText("Log4Shell RCE")).toBeInTheDocument();
  });

  it("filters by status", async () => {
    mockFindings();
    const user = userEvent.setup();
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    await screen.findByText("Log4Shell RCE");
    await user.selectOptions(screen.getByDisplayValue(/all statuses/i), "fixed");
    await waitFor(() => expect(screen.queryByText("Log4Shell RCE")).not.toBeInTheDocument());
    expect(screen.getByText("Missing HSTS")).toBeInTheDocument();
  });

  it("shows a removable chip for an active filter", async () => {
    mockFindings();
    const user = userEvent.setup();
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    await screen.findByText("Log4Shell RCE");
    await user.selectOptions(screen.getByDisplayValue(/all severities/i), "critical");
    const chip = await screen.findByRole("button", { name: /severity: critical/i });
    await user.click(chip);
    await waitFor(() => expect(screen.getByText("Reflected XSS")).toBeInTheDocument());
  });

  it("jumps to the graph when a row is clicked", async () => {
    mockFindings();
    const onView = vi.fn();
    const user = userEvent.setup();
    render(<FindingsPage onViewInGraph={onView} />);
    await user.click(await screen.findByText("Log4Shell RCE"));
    expect(onView).toHaveBeenCalledWith("1");
  });

  it("shows an empty state rather than a blank table", async () => {
    mockFindings([]);
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    expect(await screen.findByText(/no findings yet/i)).toBeInTheDocument();
  });

  it("surfaces a load failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false, status: 500, statusText: "Internal Server Error",
        json: async () => ({ detail: "boom" }),
      } as unknown as Response),
    );
    render(<FindingsPage onViewInGraph={vi.fn()} />);
    expect(await screen.findByText(/500/)).toBeInTheDocument();
  });
});
