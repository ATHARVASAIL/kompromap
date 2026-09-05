/**
 * DedupPage tests — scan list, candidate cards, and analyst resolution actions.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DedupPage from "../pages/DedupPage";

const ENGAGEMENT = { id: "eng-1", name: "Acme Test", client_name: "Acme", is_active: true, created_at: "", updated_at: "" };

const SCAN_A = {
  id: "scan-1",
  engagement_id: "eng-1",
  similarity_threshold: 0.5,
  signals: ["title", "cwe", "owasp", "location", "endpoint", "params"],
  candidates_found: 2,
  candidates_filtered: 5,
  created_at: "2026-09-05T10:00:00Z",
};

const SCAN_B = {
  id: "scan-2",
  engagement_id: "eng-1",
  similarity_threshold: 0.3,
  signals: ["title", "cwe"],
  candidates_found: 0,
  candidates_filtered: 10,
  created_at: "2026-09-05T09:00:00Z",
};

const CANDIDATE_PENDING = {
  id: "cand-1",
  scan_id: "scan-1",
  finding_a_id: "f-1",
  finding_b_id: "f-2",
  signal_scores: { title: 0.9, cwe: 1.0, location: 0.8 },
  overall_score: 0.88,
  high_impact: true,
  action: "pending",
  kept_id: null,
  analyst_note: null,
  resolved_at: null,
  created_at: "2026-09-05T10:01:00Z",
  finding_a_title: "SQLi in /api/users",
  finding_b_title: "SQL Injection on user endpoint",
};

const CANDIDATE_MERGED = {
  ...CANDIDATE_PENDING,
  id: "cand-2",
  action: "merge",
  kept_id: "f-1",
  analyst_note: "Nuclei first",
  resolved_at: "2026-09-05T10:05:00Z",
  overall_score: 0.75,
};

function mockFetch(handler: (url: string) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async (url: string) => {
      const body = handler(url);
      return { ok: true, status: 200, json: async () => body } as unknown as Response;
    }),
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("DedupPage", () => {
  it("loads and lists scans", async () => {
    mockFetch((url) => {
      if (url.includes("/api/dedup/scans")) return [SCAN_A, SCAN_B];
      return [];
    });
    render(<DedupPage engagement={ENGAGEMENT} />);

    expect(await screen.findByText("Acme Test")).toBeInTheDocument();
    expect(screen.getByText("2 candidates")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("shows empty state when no scans exist", async () => {
    mockFetch((url) => {
      if (url.includes("/api/dedup/scans")) return [];
      return [];
    });
    render(<DedupPage engagement={ENGAGEMENT} />);

    expect(await screen.findByText(/no scans yet/i)).toBeInTheDocument();
  });

  it("shows a new scan button and threshold slider", async () => {
    mockFetch((url) => {
      if (url.includes("/api/dedup/scans")) return [];
      return [];
    });
    render(<DedupPage engagement={ENGAGEMENT} />);

    expect(screen.getByText("+ New Scan")).toBeInTheDocument();
    expect(screen.getByText("threshold")).toBeInTheDocument();
  });

  it("navigates to candidates when a scan is clicked", async () => {
    mockFetch((url) => {
      if (url.includes("/candidates")) return [CANDIDATE_PENDING];
      if (url.includes("/api/dedup/scans")) return [SCAN_A];
      return [];
    });
    render(<DedupPage engagement={ENGAGEMENT} />);

    await screen.findByText("Acme Test");
    const scanRow = screen.getByText("2 candidates");
    await userEvent.click(scanRow.closest("tr")!);

    await waitFor(() => expect(screen.getByText("SQLi in /api/users")).toBeInTheDocument());
    expect(screen.getByText("SQL Injection on user endpoint")).toBeInTheDocument();
  });

  it("shows signal breakdown in candidate cards", async () => {
    mockFetch((url) => {
      if (url.includes("/candidates")) return [CANDIDATE_PENDING];
      if (url.includes("/api/dedup/scans")) return [SCAN_A];
      return [];
    });
    render(<DedupPage engagement={ENGAGEMENT} />);

    await screen.findByText("Acme Test");
    const scanRow = screen.getByText("2 candidates");
    await userEvent.click(scanRow.closest("tr")!);

    await waitFor(() => expect(screen.getByText("Title: 90%")).toBeInTheDocument());
    expect(screen.getByText("CWE: 100%")).toBeInTheDocument();
    expect(screen.getByText("Location: 80%")).toBeInTheDocument();
  });

  it("flags high-impact candidates", async () => {
    mockFetch((url) => {
      if (url.includes("/candidates")) return [CANDIDATE_PENDING];
      if (url.includes("/api/dedup/scans")) return [SCAN_A];
      return [];
    });
    render(<DedupPage engagement={ENGAGEMENT} />);

    await screen.findByText("Acme Test");
    const scanRow = screen.getByText("2 candidates");
    await userEvent.click(scanRow.closest("tr")!);

    await waitFor(() => expect(screen.getByText("high impact")).toBeInTheDocument());
  });

  it("shows action buttons only for pending candidates", async () => {
    mockFetch((url) => {
      if (url.includes("/candidates")) return [CANDIDATE_MERGED];
      if (url.includes("/api/dedup/scans")) return [SCAN_A];
      return [];
    });
    render(<DedupPage engagement={ENGAGEMENT} />);

    await screen.findByText("Acme Test");
    const scanRow = screen.getByText("2 candidates");
    await userEvent.click(scanRow.closest("tr")!);

    await waitFor(() => expect(screen.getByText("Merged")).toBeInTheDocument());
    expect(screen.queryByText("Merge")).not.toBeInTheDocument();
    expect(screen.queryByText("Keep Separate")).not.toBeInTheDocument();
  });

  it("shows analyst note on resolved candidates", async () => {
    mockFetch((url) => {
      if (url.includes("/candidates")) return [CANDIDATE_MERGED];
      if (url.includes("/api/dedup/scans")) return [SCAN_A];
      return [];
    });
    render(<DedupPage engagement={ENGAGEMENT} />);

    await screen.findByText("Acme Test");
    const scanRow = screen.getByText("2 candidates");
    await userEvent.click(scanRow.closest("tr")!);

    await waitFor(() => expect(screen.getByText("Note: Nuclei first")).toBeInTheDocument());
  });

  it("can go back to scans list", async () => {
    mockFetch((url) => {
      if (url.includes("/api/dedup/scans")) return [SCAN_A];
      return [];
    });
    render(<DedupPage engagement={ENGAGEMENT} />);

    await screen.findByText("Acme Test");
    const scanRow = screen.getByText("2 candidates");
    await userEvent.click(scanRow.closest("tr")!);

    await waitFor(() => expect(screen.getByText("← Back to scans")).toBeInTheDocument());
    await userEvent.click(screen.getByText("← Back to scans"));

    await waitFor(() => expect(screen.getByText("+ New Scan")).toBeInTheDocument());
  });

  it("surfaces API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({ detail: "DB down" }),
      } as unknown as Response),
    );
    render(<DedupPage engagement={ENGAGEMENT} />);

    expect(await screen.findByText(/500/)).toBeInTheDocument();
  });
});
