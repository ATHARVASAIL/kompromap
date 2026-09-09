import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import FindingGenerator from "../pages/FindingGenerator";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual("../api/client");
  return {
    ...actual,
    generateFindings: vi.fn(),
    getFindingGenHealth: vi.fn(),
  };
});

const { generateFindings, getFindingGenHealth } = await vi.importMock("../api/client");

describe("FindingGenerator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (getFindingGenHealth as ReturnType<typeof vi.fn>).mockResolvedValue({ configured: true, provider: "StubProvider" });
  });

  it("renders the advisory banner", async () => {
    render(<FindingGenerator />);
    expect(screen.getByText(/advisory only/i)).toBeDefined();
  });

  it("renders the node_id input", () => {
    render(<FindingGenerator />);
    expect(screen.getByPlaceholderText(/uuid of the node/i)).toBeDefined();
  });

  it("disables the generate button when node_id is empty", () => {
    render(<FindingGenerator />);
    const btn = screen.getByRole("button", { name: /generate findings/i });
    expect(btn.hasAttribute("disabled")).toBe(true);
  });

  it("enables the generate button when node_id is filled", () => {
    render(<FindingGenerator />);
    const input = screen.getByPlaceholderText(/uuid of the node/i);
    fireEvent.change(input, { target: { value: "1234" } });
    const btn = screen.getByRole("button", { name: /generate findings/i });
    expect(btn.hasAttribute("disabled")).toBe(false);
  });

  it("calls generateFindings with the right payload", async () => {
    (generateFindings as ReturnType<typeof vi.fn>).mockResolvedValue({
      findings: [],
      model: "test",
      generated_at: new Date().toISOString(),
      assumptions: [],
      note: "",
    });

    render(<FindingGenerator />);
    const input = screen.getByPlaceholderText(/uuid of the node/i);
    fireEvent.change(input, { target: { value: "node-123" } });
    fireEvent.click(screen.getByRole("button", { name: /generate findings/i }));

    await waitFor(() => {
      expect(generateFindings).toHaveBeenCalledWith({
        node_id: "node-123",
        target_assets: undefined,
        extra_context: undefined,
      });
    });
  });

  it("displays generated findings", async () => {
    (generateFindings as ReturnType<typeof vi.fn>).mockResolvedValue({
      findings: [
        {
          title: "Test Finding",
          description: "A test description",
          severity: "high",
          cwe: "CWE-89",
          owasp_category: "A03:2021",
          cvss_score: 7.5,
          cvss_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
          exploit_public: true,
          auth_required: false,
          remediation: "Patch it",
          affected_assets: ["app"],
          evidence: null,
          tags: ["injection"],
          assumptions: ["assumption"],
        },
      ],
      model: "test",
      generated_at: new Date().toISOString(),
      assumptions: ["assumption"],
      note: "",
    });

    render(<FindingGenerator />);
    const input = screen.getByPlaceholderText(/uuid of the node/i);
    fireEvent.change(input, { target: { value: "node-123" } });
    fireEvent.click(screen.getByRole("button", { name: /generate findings/i }));

    await waitFor(() => {
      expect(screen.getByText("Test Finding")).toBeDefined();
      expect(screen.getByText(/CWE-89/)).toBeDefined();
      expect(screen.getByText(/Public exploit/)).toBeDefined();
    });
  });

  it("shows error banner on failure", async () => {
    (generateFindings as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("API error"));

    render(<FindingGenerator />);
    const input = screen.getByPlaceholderText(/uuid of the node/i);
    fireEvent.change(input, { target: { value: "node-123" } });
    fireEvent.click(screen.getByRole("button", { name: /generate findings/i }));

    await waitFor(() => {
      expect(screen.getByText(/API error/i)).toBeDefined();
    });
  });
});
