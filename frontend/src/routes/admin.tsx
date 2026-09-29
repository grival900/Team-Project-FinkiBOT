import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  apiPut,
  GEMINI_MODELS,
  type AuthUser,
  type ReindexStatus,
  type SiteSettings,
} from "@/lib/api";
import { Notice, Page } from "@/components/Page";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin")({
  head: () => ({ meta: [{ title: "Администрација — FinkiBOT" }] }),
  component: AdminPage,
});

function AdminPage() {
  const { t } = useI18n();
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"users" | "settings">("users");

  // just for the UI - the backend checks admin rights on every request anyway
  useEffect(() => {
    if (!authLoading && (!user || !user.is_admin)) {
      navigate({ to: "/" });
    }
  }, [authLoading, user, navigate]);

  if (authLoading) {
    return (
      <Page title={t("admin")}>
        <Notice kind="info">{t("loading")}</Notice>
      </Page>
    );
  }
  if (!user?.is_admin) {
    return (
      <Page title={t("admin")}>
        <Notice kind="error">{t("admin_only")}</Notice>
      </Page>
    );
  }

  return (
    <Page title={t("admin")} wide>
      <div className="mb-4 inline-flex rounded-md border border-border bg-card p-0.5">
        {(["users", "settings"] as const).map((tb) => (
          <button
            key={tb}
            type="button"
            onClick={() => setTab(tb)}
            className={cn(
              "rounded px-3 py-1.5 text-sm font-medium transition-colors",
              tab === tb
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
          >
            {tb === "users" ? t("admin_users") : t("admin_settings")}
          </button>
        ))}
      </div>
      {tab === "users" ? (
        <UsersSection currentUserId={user.id} />
      ) : (
        <div className="space-y-6">
          <ReindexSection />
          <SettingsSection />
        </div>
      )}
    </Page>
  );
}

type Cadence = "full" | "frequent" | "slow";

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return "";
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function ReindexSection() {
  const { t } = useI18n();
  const [status, setStatus] = useState<ReindexStatus | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [incremental, setIncremental] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (timer.current !== null) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  const poll = useCallback(async () => {
    try {
      const s = await apiGet<ReindexStatus>("/admin/reindex/status");
      setStatus(s);
      if (s.state !== "running") stopPolling();
    } catch {
      /* transient — keep the interval and try again on the next tick */
    }
  }, [stopPolling]);

  const startPolling = useCallback(() => {
    stopPolling();
    void poll();
    timer.current = setInterval(poll, 1500);
  }, [poll, stopPolling]);

  // pick up a reindex that's already running (e.g. after a page reload)
  useEffect(() => {
    let cancelled = false;
    apiGet<ReindexStatus>("/admin/reindex/status")
      .then((s) => {
        if (cancelled) return;
        setStatus(s);
        if (s.state === "running") startPolling();
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [startPolling, stopPolling]);

  async function run(cadence: Cadence) {
    setStartError(null);
    setStatus({
      state: "running",
      cadence,
      incremental,
      started_at: null,
      finished_at: null,
      duration_seconds: null,
      progress_done: 0,
      progress_total: 0,
      current_scraper: null,
      scrapers: [],
      seed_refreshed: false,
      seed_document_count: null,
      error: null,
    });
    try {
      const params = new URLSearchParams();
      if (cadence !== "full") params.set("cadence", cadence);
      if (incremental) params.set("incremental", "true");
      const qs = params.toString() ? `?${params}` : "";
      await apiPost(`/admin/reindex${qs}`, {});
    } catch (err) {
      // 409 = already running, polling will show it
      const msg = err instanceof Error ? err.message : String(err);
      if (!msg.includes("409")) {
        setStartError(msg);
        setStatus(null);
        return;
      }
    }
    startPolling();
  }

  const running = status?.state === "running";
  const pct =
    status && status.progress_total > 0
      ? Math.round((status.progress_done / status.progress_total) * 100)
      : null;

  return (
    <div className="max-w-2xl rounded-lg border border-border bg-card p-4">
      <h2 className="mb-1 text-sm font-semibold">{t("reindex_title")}</h2>
      <p className="mb-3 text-xs text-muted-foreground">{t("reindex_hint")}</p>
      <div className="flex flex-wrap gap-2">
        {(["full", "frequent", "slow"] as const).map((c, i) => (
          <button
            key={c}
            type="button"
            disabled={running}
            onClick={() => run(c)}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm disabled:opacity-50",
              i === 0 ? "bg-primary font-medium text-primary-foreground" : "border border-border",
            )}
          >
            {running && status?.cadence === c
              ? t("reindex_running")
              : t(`reindex_${c}` as "reindex_full" | "reindex_frequent" | "reindex_slow")}
          </button>
        ))}
      </div>

      <label className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <input
          type="checkbox"
          checked={incremental}
          disabled={running}
          onChange={(e) => setIncremental(e.target.checked)}
        />
        {t("reindex_incremental")}
      </label>

      {running ? (
        <div className="mt-4">
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full bg-primary transition-all duration-500",
                pct === null && "w-1/3 animate-pulse",
              )}
              style={pct === null ? undefined : { width: `${pct}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {status && status.progress_total > 0
              ? `${status.progress_done} / ${status.progress_total} ${t("reindex_sources")}`
              : t("reindex_running")}
            {status?.current_scraper ? ` · ${status.current_scraper}` : ""}
            {status?.duration_seconds != null
              ? ` · ${t("reindex_elapsed")} ${fmtDuration(status.duration_seconds)}`
              : ""}
          </p>
        </div>
      ) : null}

      {status?.state === "done" ? (
        <div className="mt-4">
          <ReindexResult status={status} />
        </div>
      ) : null}

      {status?.state === "error" ? (
        <div className="mt-3">
          <Notice kind="error">
            {t("error")}: {status.error ?? "reindex failed"}
          </Notice>
        </div>
      ) : null}
      {startError ? (
        <div className="mt-3">
          <Notice kind="error">
            {t("error")}: {startError}
          </Notice>
        </div>
      ) : null}
    </div>
  );
}

function ReindexResult({ status }: { status: ReindexStatus }) {
  const { t } = useI18n();
  const changed = status.scrapers.filter((s) => s.new > 0 || s.updated > 0 || s.failed > 0);
  const totalNew = status.scrapers.reduce((n, s) => n + s.new, 0);
  const totalUpdated = status.scrapers.reduce((n, s) => n + s.updated, 0);
  const totalSeen = status.scrapers.reduce((n, s) => n + s.seen, 0);

  return (
    <Notice kind="info">
      <span className="font-medium">
        {t("reindex_done_in")} {fmtDuration(status.duration_seconds)}
      </span>
      {status.incremental ? ` · ${t("reindex_incremental_tag")}` : ""} · {totalSeen}{" "}
      {t("reindex_seen")}, {totalNew} {t("reindex_new")}, {totalUpdated} {t("reindex_updated")}
      {status.seed_refreshed ? (
        <>
          {" "}
          · {t("reindex_seed_refreshed")} ({status.seed_document_count} {t("reindex_documents")})
        </>
      ) : null}
      {changed.length > 0 ? (
        <ul className="mt-2 space-y-0.5">
          {changed.map((s) => (
            <li key={s.name} className="font-mono text-xs">
              {s.name} — {s.new} {t("reindex_new")}, {s.updated} {t("reindex_updated")}
              {s.failed > 0 ? `, ${s.failed} ${t("reindex_failed")}` : ""}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-xs">{t("reindex_no_changes")}</p>
      )}
    </Notice>
  );
}

function UsersSection({ currentUserId }: { currentUserId: string }) {
  const { t } = useI18n();
  const [users, setUsers] = useState<AuthUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function load() {
    apiGet<AuthUser[]>("/admin/users")
      .then(setUsers)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }

  useEffect(load, []);

  async function withBusy(u: AuthUser, action: () => Promise<void>) {
    setBusyId(u.id);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  const toggleAdmin = (u: AuthUser) =>
    withBusy(u, async () => {
      await apiPatch(`/admin/users/${u.id}`, { is_admin: !u.is_admin });
      load();
    });

  const toggleActive = (u: AuthUser) =>
    withBusy(u, async () => {
      await apiPatch(`/admin/users/${u.id}`, { is_active: !u.is_active });
      load();
    });

  const remove = (u: AuthUser) => {
    if (!confirm(t("confirm_delete"))) return;
    return withBusy(u, async () => {
      await apiDelete(`/admin/users/${u.id}`);
      load();
    });
  };

  const sendReset = (u: AuthUser) =>
    withBusy(u, async () => {
      setNotice(null);
      await apiPost(`/admin/users/${u.id}/reset-password`, {});
      setNotice(t("reset_link_sent"));
    });

  if (error && !users) {
    return (
      <Notice kind="error">
        {t("error")}: {error}
      </Notice>
    );
  }
  if (!users) return <Notice kind="info">{t("loading")}</Notice>;

  return (
    <div className="space-y-3">
      {error ? (
        <Notice kind="error">
          {t("error")}: {error}
        </Notice>
      ) : null}
      {notice ? <Notice kind="info">{notice}</Notice> : null}
      {users.map((u) => {
        const isSelf = u.id === currentUserId;
        const busy = busyId === u.id;
        return (
          <div key={u.id} className="rounded-lg border border-border bg-card p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium">
                  {u.email}
                  {u.is_admin ? (
                    <span className="ml-1.5 rounded-full bg-primary/12 px-2 py-0.5 text-xs text-primary">
                      {t("admin_badge")}
                    </span>
                  ) : null}
                  {!u.is_active ? (
                    <span className="ml-1.5 rounded-full bg-destructive/10 px-2 py-0.5 text-xs text-destructive">
                      {t("inactive_badge")}
                    </span>
                  ) : null}
                </p>
                <p className="text-xs text-muted-foreground">{new Date(u.created_at).toLocaleDateString()}</p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  disabled={isSelf || busy}
                  onClick={() => toggleAdmin(u)}
                  className="rounded-md border border-border px-2.5 py-1 text-xs disabled:opacity-40"
                >
                  {u.is_admin ? t("demote") : t("promote")}
                </button>
                <button
                  type="button"
                  disabled={isSelf || busy}
                  onClick={() => toggleActive(u)}
                  className="rounded-md border border-border px-2.5 py-1 text-xs disabled:opacity-40"
                >
                  {u.is_active ? t("deactivate") : t("activate")}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => sendReset(u)}
                  className="rounded-md border border-border px-2.5 py-1 text-xs disabled:opacity-40"
                >
                  {t("send_reset_link")}
                </button>
                <button
                  type="button"
                  disabled={isSelf || busy}
                  onClick={() => remove(u)}
                  className="rounded-md border border-destructive/40 px-2.5 py-1 text-xs text-destructive disabled:opacity-40"
                >
                  {t("delete")}
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function NumberField({
  label,
  value,
  nullable,
  onChange,
}: {
  label: string;
  value: number | null;
  nullable?: boolean;
  onChange: (v: number | null) => void;
}) {
  const { t } = useI18n();
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      <input
        type="number"
        min={0}
        value={value ?? ""}
        placeholder={nullable ? t("unlimited") : undefined}
        onChange={(e) => onChange(e.target.value === "" ? (nullable ? null : 0) : Number(e.target.value))}
        className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring"
      />
    </label>
  );
}

function SettingsSection() {
  const { t } = useI18n();
  const [settings, setSettings] = useState<SiteSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    apiGet<SiteSettings>("/admin/settings")
      .then(setSettings)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await apiPut<SiteSettings>("/admin/settings", {
        ...settings,
        scraper_enabled: Object.fromEntries(settings.scrapers.map((s) => [s.name, s.enabled])),
      });
      setSettings(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <Notice kind="info">{t("loading")}</Notice>;
  if (error && !settings) {
    return (
      <Notice kind="error">
        {t("error")}: {error}
      </Notice>
    );
  }
  if (!settings) return null;

  return (
    <form onSubmit={save} className="max-w-2xl space-y-4">
      <div className="grid gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-2">
        <NumberField
          label="SCRAPE_ANNOUNCEMENT_LIMIT"
          value={settings.scrape_announcement_limit}
          nullable
          onChange={(v) => setSettings({ ...settings, scrape_announcement_limit: v })}
        />
        <NumberField
          label="SCRAPE_SUBJECTS_LIMIT"
          value={settings.scrape_subjects_limit}
          nullable
          onChange={(v) => setSettings({ ...settings, scrape_subjects_limit: v })}
        />
        <NumberField
          label="SCRAPE_REQUEST_DELAY_SECONDS"
          value={settings.scrape_request_delay_seconds}
          onChange={(v) => setSettings({ ...settings, scrape_request_delay_seconds: v ?? 0 })}
        />
        <NumberField
          label="SCHEDULER_INTERVAL_MINUTES"
          value={settings.scheduler_interval_minutes}
          onChange={(v) => setSettings({ ...settings, scheduler_interval_minutes: v ?? 0 })}
        />
        <NumberField
          label="SCHEDULER_SLOW_INTERVAL_MINUTES"
          value={settings.scheduler_slow_interval_minutes}
          onChange={(v) => setSettings({ ...settings, scheduler_slow_interval_minutes: v ?? 0 })}
        />
        <label className="flex items-center gap-2 self-end pb-2">
          <input
            type="checkbox"
            checked={settings.enable_scheduler}
            onChange={(e) => setSettings({ ...settings, enable_scheduler: e.target.checked })}
          />
          <span className="text-sm">ENABLE_SCHEDULER</span>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-muted-foreground">LLM_PROVIDER</span>
          <select
            value={settings.llm_provider}
            onChange={(e) =>
              setSettings({ ...settings, llm_provider: e.target.value as SiteSettings["llm_provider"] })
            }
            className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring"
          >
            <option value="gemini">Gemini</option>
            <option value="groq">Groq</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-muted-foreground">LLM_MODEL (Gemini)</span>
          <select
            value={settings.llm_model}
            onChange={(e) => setSettings({ ...settings, llm_model: e.target.value })}
            className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring"
          >
            {/* also list the .env model if it isn't one of ours */}
            {[...new Set<string>([...GEMINI_MODELS, settings.llm_model])].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold">Scrapers</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {settings.scrapers.map((s) => (
            <label key={s.name} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={s.enabled}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    scrapers: settings.scrapers.map((x) =>
                      x.name === s.name ? { ...x, enabled: e.target.checked } : x,
                    ),
                  })
                }
              />
              <span className="font-mono text-sm">{s.name}</span>
            </label>
          ))}
        </div>
      </div>

      <button
        type="submit"
        disabled={saving}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
      >
        {t("save")}
      </button>
      {error ? (
        <Notice kind="error">
          {t("error")}: {error}
        </Notice>
      ) : null}
      {saved ? <Notice kind="info">{t("saved")}</Notice> : null}
    </form>
  );
}
