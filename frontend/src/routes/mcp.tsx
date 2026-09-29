import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { apiGet, apiPost, type McpTool } from "@/lib/api";
import { Notice, Page } from "@/components/Page";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/mcp")({
  head: () => ({
    meta: [
      { title: "MCP алатки — FinkiBOT" },
      {
        name: "description",
        content: "Пробај ги MCP алатките на FinkiBOT врз finki.ukim.mk и finki-hub.com.",
      },
      { property: "og:title", content: "MCP алатки — FinkiBOT" },
      {
        property: "og:description",
        content: "Playground за MCP алатките на FinkiBOT врз finki.ukim.mk и finki-hub.com.",
      },
    ],
  }),
  component: McpPage,
});

const SERVER_LABELS: Record<string, string> = {
  official: "finki-official — finki.ukim.mk",
  finki_hub: "finki-hub — finki-hub.com",
  official_live: "finki-official-live — live search, not the local index",
};

function ToolCard({ tool }: { tool: McpTool }) {
  const { t } = useI18n();
  const limitParam = tool.params.find((p) => p.name === "limit");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState<number>(
    typeof limitParam?.default === "number" ? limitParam.default : 5,
  );
  const [result, setResult] = useState<unknown[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasQuery = tool.params.some((p) => p.name === "query");

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiPost<unknown[]>("/mcp/call", {
        server: tool.server,
        tool: tool.name,
        ...(hasQuery ? { query } : {}),
        ...(limitParam ? { limit } : {}),
      });
      setResult(Array.isArray(res) ? res : [res]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="font-mono text-sm font-semibold">{tool.name}</h3>
      <p className="mt-1 text-xs whitespace-pre-wrap text-muted-foreground">{tool.description}</p>
      <form onSubmit={run} className="mt-3 flex flex-wrap items-end gap-2">
        {hasQuery ? (
          <label className="min-w-52 flex-1">
            <span className="mb-1 block text-xs text-muted-foreground">query</span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm outline-none focus:border-ring"
            />
          </label>
        ) : null}
        {limitParam ? (
          <label className="w-28">
            <span className="mb-1 block text-xs text-muted-foreground">limit</span>
            <input
              type="number"
              min={1}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm outline-none focus:border-ring"
            />
          </label>
        ) : null}
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("run")}
        </button>
      </form>

      {loading ? (
        <p className="mt-3 text-xs text-muted-foreground">{t("loading")}</p>
      ) : null}
      {error ? (
        <div className="mt-3">
          <Notice kind="error">
            {t("error")}: {error}
          </Notice>
        </div>
      ) : null}
      {result ? (
        <div className="mt-3">
          <p className="mb-1 text-xs text-muted-foreground">
            {t("results_count")}: {result.length}
          </p>
          <pre className="max-h-80 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      ) : null}
    </div>
  );
}

function McpPage() {
  const { t } = useI18n();
  const [tools, setTools] = useState<McpTool[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiGet<McpTool[]>("/mcp/tools")
      .then((d) => !cancelled && setTools(d))
      .catch((err: unknown) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const servers = Array.from(new Set((tools ?? []).map((x) => x.server)));

  return (
    <Page title={t("nav_mcp")} description={t("mcp_intro")}>
      {loading ? <Notice kind="info">{t("loading")}</Notice> : null}
      {error ? (
        <Notice kind="error">
          {t("error")}: {error}
        </Notice>
      ) : null}
      <div className="space-y-8">
        {servers.map((s) => (
          <section key={s}>
            <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted-foreground uppercase">
              {SERVER_LABELS[s] ?? s}
            </h2>
            <div className="space-y-3">
              {(tools ?? [])
                .filter((x) => x.server === s)
                .map((tool) => (
                  <ToolCard key={`${s}-${tool.name}`} tool={tool} />
                ))}
            </div>
          </section>
        ))}
      </div>
    </Page>
  );
}
