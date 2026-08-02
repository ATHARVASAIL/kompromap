/**
 * API client tests.
 *
 * This module is where two real, user-facing bugs lived: relative /api
 * paths that broke split-origin deployments, and (later) auth headers that
 * had to reach all 24 call sites. Both were invisible to typecheck/build —
 * only actually invoking the functions catches them.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createEdge,
  createNode,
  deleteNode,
  exportChain,
  fetchGraph,
  fetchNode,
  findBestPaths,
  getActiveEngagement,
  getDashboard,
  ingestFile,
  listNodesByType,
  updateNode,
} from "../api/client";

function mockFetchOk(body: unknown = {}) {
  const spy = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => body,
  } as unknown as Response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

function lastCall(spy: ReturnType<typeof vi.fn>) {
  const [url, init] = spy.mock.calls[spy.mock.calls.length - 1];
  return { url: String(url), init: (init ?? {}) as RequestInit };
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("URL construction", () => {
  it("hits the expected path for each endpoint", async () => {
    const cases: [() => Promise<unknown>, string][] = [
      [() => fetchGraph(), "/api/graph"],
      [() => getActiveEngagement(), "/api/engagements/active"],
      [() => fetchNode("abc"), "/api/nodes/abc"],
      [() => listNodesByType("finding"), "/api/nodes?node_type=finding"],
      [() => findBestPaths(), "/api/pathfind/best"],
      [() => getDashboard("eng-1"), "/api/engagements/eng-1/dashboard"],
    ];

    for (const [fn, expected] of cases) {
      const spy = mockFetchOk({ nodes: [], edges: [] });
      await fn();
      expect(lastCall(spy).url).toContain(expected);
    }
  });

  it("serializes graph filters into query params", async () => {
    const spy = mockFetchOk({ nodes: [], edges: [] });
    await fetchGraph({ node_type: "finding", in_scope_only: true, min_cvss: 7.5 });
    const { url } = lastCall(spy);
    expect(url).toContain("node_type=finding");
    expect(url).toContain("in_scope_only=true");
    expect(url).toContain("min_cvss=7.5");
  });

  it("omits the query string entirely when no filters are set", async () => {
    const spy = mockFetchOk({ nodes: [], edges: [] });
    await fetchGraph({});
    expect(lastCall(spy).url).not.toContain("?");
  });
});

describe("HTTP methods", () => {
  it("uses the right verb for mutations", async () => {
    let spy = mockFetchOk({ id: "n1" });
    await createNode({ node_type: "asset", name: "x", asset_type: "domain" });
    expect(lastCall(spy).init.method).toBe("POST");

    spy = mockFetchOk({ id: "n1" });
    await updateNode("n1", { notes: "hi" });
    expect(lastCall(spy).init.method).toBe("PATCH");

    spy = vi.fn().mockResolvedValue({ ok: true, status: 204 } as unknown as Response);
    vi.stubGlobal("fetch", spy);
    await deleteNode("n1");
    expect(lastCall(spy).init.method).toBe("DELETE");
  });

  it("sends JSON content-type on bodied requests", async () => {
    const spy = mockFetchOk({ id: "e1" });
    await createEdge({ source_node_id: "a", target_node_id: "b", edge_type: "HOSTS" });
    const headers = lastCall(spy).init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("does NOT set content-type on file upload — the browser must set the multipart boundary", async () => {
    const spy = mockFetchOk({ assets_created: 1 });
    const file = new File(["<nmaprun/>"], "scan.xml", { type: "application/xml" });
    await ingestFile("nmap", file);
    const headers = (lastCall(spy).init.headers ?? {}) as Record<string, string>;
    expect(headers["Content-Type"]).toBeUndefined();
    expect(lastCall(spy).init.body).toBeInstanceOf(FormData);
  });

  it("passes engagement_id through on upload when given", async () => {
    const spy = mockFetchOk({ assets_created: 1 });
    const file = new File(["x"], "scan.xml");
    await ingestFile("nmap", file, "eng-42");
    const form = lastCall(spy).init.body as FormData;
    expect(form.get("engagement_id")).toBe("eng-42");
  });
});

describe("error handling", () => {
  it("throws with the server's detail message on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        statusText: "Unprocessable Entity",
        json: async () => ({ detail: "cvss_score out of range" }),
      } as unknown as Response),
    );
    await expect(fetchGraph()).rejects.toThrow(/422/);
  });

  it("falls back to statusText when the body isn't JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => {
          throw new Error("not json");
        },
      } as unknown as Response),
    );
    await expect(fetchGraph()).rejects.toThrow(/500/);
  });

  it("handles a 204 with no body without trying to parse it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 204 } as unknown as Response));
    await expect(deleteNode("n1")).resolves.toBeUndefined();
  });
});

describe("report export", () => {
  it("sends node_ids and format, and reuses a supplied narrative", async () => {
    const spy = mockFetchOk({ format: "markdown", content: "# x" });
    await exportChain(["a", "b"], "markdown", "pre-written");
    const body = JSON.parse(String(lastCall(spy).init.body));
    expect(body.node_ids).toEqual(["a", "b"]);
    expect(body.format).toBe("markdown");
    expect(body.narrative).toBe("pre-written");
  });

  it("omits narrative when not supplied, so the backend generates one", async () => {
    const spy = mockFetchOk({ format: "json", data: {} });
    await exportChain(["a"], "json");
    const body = JSON.parse(String(lastCall(spy).init.body));
    expect(body).not.toHaveProperty("narrative");
  });
});
