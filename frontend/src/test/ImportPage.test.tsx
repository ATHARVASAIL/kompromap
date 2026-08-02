/**
 * ImportPage tests.
 *
 * The file picker here shipped a real bug: the <input type="file"> had no
 * `key`, so React reused the same DOM node when switching tools and never
 * re-applied `accept`. The picker stayed stuck on Nmap's ".xml" and
 * silently refused to show .json/.jsonl/.txt files. Typecheck, build and
 * lint all passed — only rendering it catches this.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ImportPage from "../pages/ImportPage";
import { ToastProvider } from "../components/ToastProvider";

function renderPage(onImported = vi.fn()) {
  return render(
    <ToastProvider>
      <ImportPage engagementId="eng-1" onImported={onImported} />
    </ToastProvider>,
  );
}

function fileInput(): HTMLInputElement {
  // Testing Library has no role-based query for <input type="file"> — it
  // exposes no implicit ARIA role — so a direct DOM query is the correct
  // approach here rather than a workaround.
  const el = document.querySelector('input[type="file"]');
  if (!el) throw new Error("file input not found");
  return el as HTMLInputElement;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("tool selection", () => {
  it("offers all four supported tools", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /nmap/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /nuclei/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /amass/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /burp/i })).toBeInTheDocument();
  });

  it("defaults to Nmap and its .xml filter", () => {
    renderPage();
    expect(fileInput().accept).toContain(".xml");
  });
});

describe("file picker accept filter (regression)", () => {
  it("updates the accept filter when switching to Nuclei", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /nuclei/i }));
    await waitFor(() => {
      expect(fileInput().accept).toContain(".json");
    });
    expect(fileInput().accept).toContain(".jsonl");
  });

  it("updates the accept filter when switching to Amass", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /amass/i }));
    await waitFor(() => {
      expect(fileInput().accept).toContain(".txt");
    });
  });

  it("switches back to .xml for Burp", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /nuclei/i }));
    await user.click(screen.getByRole("button", { name: /burp/i }));
    await waitFor(() => {
      expect(fileInput().accept).toContain(".xml");
    });
  });

  it("always includes a wildcard so odd extensions aren't hard-blocked", async () => {
    const user = userEvent.setup();
    renderPage();
    for (const name of [/nmap/i, /nuclei/i, /amass/i, /burp/i]) {
      await user.click(screen.getByRole("button", { name }));
      await waitFor(() => {
        expect(fileInput().accept).toContain("*");
      });
    }
  });
});

describe("upload flow", () => {
  it("disables submit until a file is chosen", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /^import$/i })).toBeDisabled();
  });

  it("posts to the endpoint matching the selected tool", async () => {
    const spy = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        source_tool: "nuclei", assets_created: 0, assets_reused: 0, services_created: 0,
        endpoints_created: 0, findings_created: 3, edges_created: 3, warnings: [],
      }),
    } as unknown as Response);
    vi.stubGlobal("fetch", spy);

    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: /nuclei/i }));
    await user.upload(fileInput(), new File(['{"a":1}'], "out.jsonl", { type: "application/json" }));
    await user.click(screen.getByRole("button", { name: /^import$/i }));

    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(String(spy.mock.calls[0][0])).toContain("/api/ingest/nuclei");
  });

  it("shows the created-node counts on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          source_tool: "nmap", assets_created: 7, assets_reused: 0, services_created: 12,
          endpoints_created: 0, findings_created: 0, edges_created: 12, warnings: [],
        }),
      } as unknown as Response),
    );
    const user = userEvent.setup();
    renderPage();
    await user.upload(fileInput(), new File(["<nmaprun/>"], "s.xml", { type: "application/xml" }));
    await user.click(screen.getByRole("button", { name: /^import$/i }));

    // Both "Import complete" and the number 12 (services AND edges) appear
    // more than once on screen, so assert with the multi-match-aware
    // queries rather than getByText, which throws on duplicates.
    expect(await screen.findByText("7")).toBeInTheDocument(); // assets_created — unique
    expect(screen.getAllByText(/import complete/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("12").length).toBe(2); // services_created + edges_created
  });

  it("surfaces a server error instead of failing silently", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        statusText: "Unprocessable Entity",
        json: async () => ({ detail: "Failed to parse Nmap XML" }),
      } as unknown as Response),
    );
    const user = userEvent.setup();
    renderPage();
    await user.upload(fileInput(), new File(["bad"], "s.xml", { type: "application/xml" }));
    await user.click(screen.getByRole("button", { name: /^import$/i }));

    expect(await screen.findByText(/422/)).toBeInTheDocument();
  });

  it("notifies the parent so the graph refreshes after import", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          source_tool: "nmap", assets_created: 1, assets_reused: 0, services_created: 0,
          endpoints_created: 0, findings_created: 0, edges_created: 0, warnings: [],
        }),
      } as unknown as Response),
    );
    const onImported = vi.fn();
    const user = userEvent.setup();
    renderPage(onImported);
    await user.upload(fileInput(), new File(["<nmaprun/>"], "s.xml"));
    await user.click(screen.getByRole("button", { name: /^import$/i }));
    await waitFor(() => expect(onImported).toHaveBeenCalled());
  });
});
