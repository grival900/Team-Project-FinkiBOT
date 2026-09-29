import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { apiGet, type SearchResult } from "@/lib/api";
import { Notice, Page } from "@/components/Page";
import { useI18n, type TKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const TYPE_LABEL_KEYS: Record<string, TKey> = {
  announcement: "type_announcement",
  course: "type_course",
  professor: "type_professor",
  staff: "type_staff",
  material: "type_material",
  schedule: "type_schedule",
  thesis: "type_thesis",
  document: "type_document",
  page: "type_page",
  consultation: "type_consultation",
};

function typeLabel(type: string, t: (k: TKey) => string): string {
  const key = TYPE_LABEL_KEYS[type];
  return key ? t(key) : type;
}

const SOURCE_LABELS: Record<string, string> = {
  official: "finki.ukim.mk",
  finki_hub: "finki-hub.com",
};

function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

// different color than the type chips so the two filters are easy to tell apart
const SOURCE_ACTIVE_CLASSES: Record<string, string> = {
  finki_hub:
    "border-emerald-700/50 bg-emerald-700/15 text-emerald-800 dark:border-emerald-500/50 dark:bg-emerald-500/15 dark:text-emerald-300",
  official:
    "border-sky-400/60 bg-sky-400/15 text-sky-700 dark:border-sky-300/50 dark:bg-sky-300/15 dark:text-sky-200",
};

function sourceChipClasses(source: string, active: boolean): string {
  if (!active) return "border-border bg-card text-muted-foreground hover:bg-accent";
  return SOURCE_ACTIVE_CLASSES[source] ?? "border-primary bg-primary/10 text-primary";
}

type SearchSearch = {
  q?: string | undefined;
  date_from?: string | undefined;
  date_to?: string | undefined;
};

export const Route = createFileRoute("/search")({
  validateSearch: (search: Record<string, unknown>): SearchSearch => ({
    q: typeof search["q"] === "string" ? search["q"] : undefined,
    date_from: typeof search["date_from"] === "string" ? search["date_from"] : undefined,
    date_to: typeof search["date_to"] === "string" ? search["date_to"] : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Пребарување — FinkiBOT" },
      {
        name: "description",
        content:
          "Пребарувај соопштенија, предмети и материјали од finki.ukim.mk и finki-hub.com на едно место.",
      },
      { property: "og:title", content: "Пребарување — FinkiBOT" },
      {
        property: "og:description",
        content: "Семантичко пребарување низ содржината на ФИНКИ и заедницата.",
      },
    ],
  }),
  component: SearchPage,
});

function DateField({
  label,
  value,
  onChange,
  clearLabel,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  clearLabel: string;
}) {
  return (
    <div>
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      <div className="flex items-center gap-1">
        <input
          type="date"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "h-9 rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring",
            "[color-scheme:light] dark:[color-scheme:dark]",
            // gray out the empty mm/dd/yyyy placeholder (no CSS way to do it)
            !value && "text-muted-foreground",
          )}
        />
        {value ? (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label={clearLabel}
            title={clearLabel}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        ) : null}
      </div>
    </div>
  );
}

function fmtDate(d: string | null) {
  if (!d) return null;
  const date = new Date(d);
  return Number.isNaN(date.getTime()) ? d : date.toLocaleDateString("mk-MK");
}

// material chunks are just lists of recording links, so show a short description instead
function resultDescription(r: SearchResult, t: (k: TKey) => string): string {
  if (r.type === "material") return `${t("material_description")} ${r.title}`;
  return r.chunk_text;
}

function SearchPage() {
  const { t } = useI18n();
  const { q: urlQ, date_from: urlDateFrom, date_to: urlDateTo } = Route.useSearch();
  const navigate = Route.useNavigate();
  const [q, setQ] = useState(urlQ ?? "");
  const [dateFrom, setDateFrom] = useState(urlDateFrom ?? "");
  const [dateTo, setDateTo] = useState(urlDateTo ?? "");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());
  const [activeSources, setActiveSources] = useState<Set<string>>(new Set());

  function toggleType(type: string) {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  function toggleSource(src: string) {
    setActiveSources((prev) => {
      const next = new Set(prev);
      if (next.has(src)) next.delete(src);
      else next.add(src);
      return next;
    });
  }

  // the query is in the URL so refresh and back/forward keep the search
  useEffect(() => {
    setQ(urlQ ?? "");
    setDateFrom(urlDateFrom ?? "");
    setDateTo(urlDateTo ?? "");
    if (!urlQ) {
      setResults(null);
      setActiveTypes(new Set());
      setActiveSources(new Set());
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    // always search all sources; the chips filter the results afterwards
    const params = new URLSearchParams({ q: urlQ, limit: "10" });
    if (urlDateFrom) params.set("date_from", urlDateFrom);
    if (urlDateTo) params.set("date_to", urlDateTo);
    apiGet<SearchResult[]>(`/search?${params.toString()}`)
      .then((r) => {
        if (!cancelled) {
          setResults(r);
          setActiveTypes(new Set());
          setActiveSources(new Set());
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setResults(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [urlQ, urlDateFrom, urlDateTo]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    navigate({
      search: {
        q: q.trim(),
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      },
    });
  }

  const filtered = results?.filter(
    (r) =>
      (activeTypes.size === 0 || activeTypes.has(r.type)) &&
      (activeSources.size === 0 || activeSources.has(r.source)),
  );

  return (
    <Page title={t("nav_search")}>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <label className="min-w-60 flex-1">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("search_placeholder")}
            className="h-9 w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring"
          />
        </label>
        <DateField label={t("date_from")} value={dateFrom} onChange={setDateFrom} clearLabel={t("clear_date")} />
        <DateField label={t("date_to")} value={dateTo} onChange={setDateTo} clearLabel={t("clear_date")} />
        <button
          type="submit"
          disabled={loading}
          className="h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("submit_search")}
        </button>
      </form>

      {results && results.length > 0
        ? (() => {
            const sources = Array.from(new Set(results.map((r) => r.source))).sort();
            const types = Array.from(new Set(results.map((r) => r.type))).sort();

            // each filter's counts use only the other filter, so picking a source
            // updates the type counts and the other way round
            const sourceCounts = new Map<string, number>();
            for (const r of results) {
              if (activeTypes.size === 0 || activeTypes.has(r.type)) {
                sourceCounts.set(r.source, (sourceCounts.get(r.source) ?? 0) + 1);
              }
            }
            const typeCounts = new Map<string, number>();
            for (const r of results) {
              if (activeSources.size === 0 || activeSources.has(r.source)) {
                typeCounts.set(r.type, (typeCounts.get(r.type) ?? 0) + 1);
              }
            }

            return (
              <div className="mt-4 space-y-2">
                {sources.length >= 2 ? (
                  <div className="flex flex-wrap gap-1.5">
                    <span className="self-center pr-1 text-xs text-muted-foreground">
                      {t("filter_by_source")}:
                    </span>
                    {sources.map((src) => {
                      const count = sourceCounts.get(src) ?? 0;
                      // disable empty sources, but never a selected one
                      const disabled = count === 0 && !activeSources.has(src);
                      return (
                        <button
                          key={src}
                          type="button"
                          disabled={disabled}
                          onClick={() => toggleSource(src)}
                          className={cn(
                            "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                            disabled
                              ? "cursor-not-allowed border-border bg-card text-muted-foreground/50"
                              : sourceChipClasses(src, activeSources.has(src)),
                          )}
                        >
                          {sourceLabel(src)} ({count})
                        </button>
                      );
                    })}
                  </div>
                ) : null}
                {types.length >= 2 ? (
                  <div className="flex flex-wrap gap-1.5">
                    <span className="self-center pr-1 text-xs text-muted-foreground">
                      {t("filter_by_type")}:
                    </span>
                    {types.map((type) => {
                      const count = typeCounts.get(type) ?? 0;
                      const disabled = count === 0 && !activeTypes.has(type);
                      return (
                        <button
                          key={type}
                          type="button"
                          disabled={disabled}
                          onClick={() => toggleType(type)}
                          className={cn(
                            "rounded-full border px-2.5 py-1 text-xs transition-colors",
                            disabled
                              ? "cursor-not-allowed border-border bg-card text-muted-foreground/50"
                              : activeTypes.has(type)
                                ? "border-primary bg-primary/10 text-primary"
                                : "border-border bg-card text-muted-foreground hover:bg-accent",
                          )}
                        >
                          {typeLabel(type, t)} ({count})
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          })()
        : null}

      <div className="mt-6 space-y-3">
        {loading ? <Notice kind="info">{t("loading")}</Notice> : null}
        {error ? (
          <Notice kind="error">
            {t("error")}: {error}
          </Notice>
        ) : null}
        {results && results.length === 0 && !loading ? (
          <Notice kind="info">{t("no_results")}</Notice>
        ) : null}
        {results && (activeTypes.size > 0 || activeSources.size > 0) && filtered?.length === 0 ? (
          <Notice kind="info">{t("no_results")}</Notice>
        ) : null}
        {filtered?.map((r) => {
          const internal =
            (r.source === "finki_hub" && r.type === "course") ||
            (r.source === "finki_hub" && r.type === "material");
          const date = fmtDate(r.published_at);
          return (
            <article
              key={`${r.document_id}-${r.chunk_text.slice(0, 12)}`}
              className="rounded-lg border border-border bg-card p-4"
            >
              {internal ? (
                <Link
                  to="/documents/$id"
                  params={{ id: r.document_id }}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  {r.title}
                </Link>
              ) : (
                <a
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-primary hover:underline"
                >
                  {r.title}
                </a>
              )}
              <p className="mt-1 text-xs text-muted-foreground">
                {r.source} · {r.type}
                {date ? ` · ${date}` : ""}
              </p>
              <p className="mt-2 text-sm text-muted-foreground">{resultDescription(r, t)}</p>
            </article>
          );
        })}
      </div>
    </Page>
  );
}
