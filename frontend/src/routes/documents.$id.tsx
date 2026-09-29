import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { apiGet, type Accreditation, type DocumentDetail } from "@/lib/api";
import { Markdown } from "@/components/Markdown";
import { Notice, Page } from "@/components/Page";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/documents/$id")({
  head: () => ({
    meta: [
      { title: "Документ — FinkiBOT" },
      {
        name: "description",
        content: "Детали за предмет или документ индексиран од FinkiBOT: акредитации, професори, предуслови.",
      },
      { property: "og:title", content: "Документ — FinkiBOT" },
      {
        property: "og:description",
        content: "Детали за предмет или документ индексиран од FinkiBOT.",
      },
    ],
  }),
  component: DocumentPage,
});

const SKIP_KEYS = new Set(["year", "official_url", "prerequisite_links", "programs"]);

function Chips({ label, items }: { label: string; items?: string[] | undefined }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mb-3">
      <span className="mb-1.5 block text-xs tracking-wide text-muted-foreground uppercase">
        {label}
      </span>
      <div className="flex flex-wrap gap-1.5">
        {items.map((x) => (
          <span
            key={x}
            className="rounded-full border border-border bg-accent px-2.5 py-0.5 text-xs text-accent-foreground"
          >
            {x}
          </span>
        ))}
      </div>
    </div>
  );
}

function Programs({ programs }: { programs?: Record<string, string> | undefined }) {
  if (!programs || Object.keys(programs).length === 0) return null;
  const mandatory = Object.entries(programs)
    .filter(([, status]) => status === "задолжителен")
    .map(([program]) => program);
  const elective = Object.entries(programs)
    .filter(([, status]) => status !== "задолжителен")
    .map(([program]) => program);
  return (
    <>
      {mandatory.length > 0 ? (
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-xs text-muted-foreground">Задолжителен за</dt>
          <dd className="flex-1">{mandatory.join(", ")}</dd>
        </div>
      ) : null}
      {elective.length > 0 ? (
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-xs text-muted-foreground">Изборен за</dt>
          <dd className="flex-1">{elective.join(", ")}</dd>
        </div>
      ) : null}
    </>
  );
}

function Prerequisite({ acc }: { acc: Accreditation }) {
  const links = acc.prerequisite_links;
  if (links && links.length > 0) {
    return (
      <span>
        {links.map((l, i) => (
          <span key={`${l.text}-${i}`}>
            {i > 0 ? " / " : ""}
            {l.document_id ? (
              <Link
                to="/documents/$id"
                params={{ id: l.document_id }}
                className="text-primary hover:underline"
              >
                {l.text}
              </Link>
            ) : (
              l.text
            )}
          </span>
        ))}
      </span>
    );
  }
  const raw = acc["Предуслов"];
  return <span>{typeof raw === "string" ? raw : "—"}</span>;
}

function BackLink() {
  const router = useRouter();
  const { t } = useI18n();
  return (
    <button
      type="button"
      onClick={() => router.history.back()}
      className="mb-4 text-sm text-muted-foreground hover:text-foreground hover:underline"
    >
      {t("back")}
    </button>
  );
}

function DocumentPage() {
  const { id } = Route.useParams();
  const { t } = useI18n();
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiGet<DocumentDetail>(`/documents/${id}`)
      .then((d) => {
        if (!cancelled) setDoc(d);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <Page title="…" beforeHeader={<BackLink />}>
        <Notice kind="info">{t("loading")}</Notice>
      </Page>
    );
  }
  if (error || !doc) {
    return (
      <Page title={t("error")} beforeHeader={<BackLink />}>
        <Notice kind="error">{error ?? "404"}</Notice>
      </Page>
    );
  }

  const md = doc.doc_metadata ?? {};
  const accs = md.accreditations;
  // finki-hub courses have no page of their own (doc.url is just the course list)
  const isUnroutableFinkiHubCourse = doc.source === "finki_hub" && doc.type === "course" && !md.official_subject_url;
  const sourceUrl = md.official_subject_url ?? (isUnroutableFinkiHubCourse ? null : doc.url);

  return (
    <Page
      title={doc.title}
      beforeHeader={<BackLink />}
      description={[doc.source, doc.type, doc.published_at?.slice(0, 10)]
        .filter(Boolean)
        .join(" · ")}
    >
      <Chips label={t("professors")} items={md.professors} />
      <Chips label={t("assistants")} items={md.assistants} />
      <Chips label={t("tags")} items={md.tags} />

      {accs && accs.length > 0 ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {accs.map((acc, i) => (
            <div key={acc.year ?? i} className="rounded-lg border border-border bg-card p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold">{acc.year ?? `#${i + 1}`}</span>
                {acc.official_url ? (
                  <a
                    href={acc.official_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-primary hover:underline"
                  >
                    {t("source_ref")}
                  </a>
                ) : null}
              </div>
              <dl className="space-y-1.5 text-sm">
                {Object.entries(acc)
                  .filter(([k]) => !SKIP_KEYS.has(k))
                  .map(([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <dt className="w-28 shrink-0 text-xs text-muted-foreground">{k}</dt>
                      <dd className="flex-1">
                        {k === "Предуслов" ? (
                          <Prerequisite acc={acc} />
                        ) : (
                          String(v ?? "—")
                        )}
                      </dd>
                    </div>
                  ))}
                {!("Предуслов" in acc) && acc.prerequisite_links?.length ? (
                  <div className="flex gap-2">
                    <dt className="w-28 shrink-0 text-xs text-muted-foreground">Предуслов</dt>
                    <dd className="flex-1">
                      <Prerequisite acc={acc} />
                    </dd>
                  </div>
                ) : null}
                <Programs programs={acc.programs} />
              </dl>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 text-sm">
          <Markdown content={doc.content} />
        </div>
      )}

      {sourceUrl ? (
        <p className="mt-6">
          <a href={sourceUrl} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline">
            {t("source_ref")}
          </a>
        </p>
      ) : null}
    </Page>
  );
}
