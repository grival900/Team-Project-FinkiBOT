import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { apiGet, type Insights } from "@/lib/api";
import { Notice, Page } from "@/components/Page";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/insights")({
  head: () => ({
    meta: [
      { title: "Insights — статистика на индексот | FinkiBOT" },
      {
        name: "description",
        content:
          "Статистика за индексираните документи на ФИНКИ: по извор и тип, соопштенија по месец, тагови и семестри.",
      },
      { property: "og:title", content: "Insights — статистика на индексот | FinkiBOT" },
      {
        property: "og:description",
        content: "Преглед на податоците што FinkiBOT ги индексира.",
      },
    ],
  }),
  component: InsightsPage,
});

function BarSection({ title, data }: { title: string; data: { label: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <section className="mb-4 break-inside-avoid rounded-lg border border-border bg-card p-4">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {/* Capped + scrollable: some charts (e.g. announcements by month) grow unbounded
          over time and would otherwise dominate the whole layout on their own. */}
      <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
        {data.length === 0 ? <p className="text-xs text-muted-foreground">—</p> : null}
        {data.map((d) => (
          <div key={d.label} className="flex items-center gap-3 text-xs">
            <span className="w-48 shrink-0 truncate text-muted-foreground">{d.label}</span>
            <span className="h-2 flex-1 rounded-full bg-muted">
              <span
                className="block h-2 rounded-full bg-primary"
                style={{ width: `${(d.count / max) * 100}%` }}
              />
            </span>
            <span className="w-10 text-right tabular-nums">{d.count}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function InsightsPage() {
  const { t } = useI18n();
  const [data, setData] = useState<Insights | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiGet<Insights>("/insights")
      .then((d) => !cancelled && setData(d))
      .catch((err: unknown) => !cancelled && setError(err instanceof Error ? err.message : String(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Page title={t("nav_insights")}>
      {loading ? <Notice kind="info">{t("loading")}</Notice> : null}
      {error ? (
        <Notice kind="error">
          {t("error")}: {error}
        </Notice>
      ) : null}
      {data ? (
        <div className="columns-1 gap-4 lg:columns-2">
          <BarSection
            title={t("insights_docs")}
            data={data.documents_by_type.map((d) => ({
              label: `${d.source} / ${d.type}`,
              count: d.count,
            }))}
          />
          <BarSection
            title={t("insights_months")}
            data={data.announcements_by_month.map((d) => ({ label: d.month, count: d.count }))}
          />
          <BarSection
            title={t("insights_tags")}
            data={data.course_tags.map((d) => ({ label: d.tag, count: d.count }))}
          />
          <BarSection
            title={t("insights_sem")}
            data={data.course_semester_distribution.map((d) => ({
              label: d.semester,
              count: d.count,
            }))}
          />
        </div>
      ) : null}
    </Page>
  );
}
