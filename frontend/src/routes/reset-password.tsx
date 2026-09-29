import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Notice, Page } from "@/components/Page";
import { useI18n } from "@/lib/i18n";

type ResetSearch = { token?: string | undefined };

export const Route = createFileRoute("/reset-password")({
  validateSearch: (search: Record<string, unknown>): ResetSearch => ({
    token: typeof search["token"] === "string" ? search["token"] : undefined,
  }),
  head: () => ({
    meta: [{ title: "Ресетирање лозинка — FinkiBOT" }],
  }),
  component: ResetPasswordPage,
});

function ResetPasswordPage() {
  const { t } = useI18n();
  const { token } = Route.useSearch();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      await apiPost("/auth/reset-password", { token, new_password: password });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <Page title={t("reset_password")}>
        <Notice kind="error">{t("error")}</Notice>
      </Page>
    );
  }

  return (
    <Page title={t("reset_password")}>
      <form onSubmit={submit} className="mx-auto flex max-w-sm flex-col items-center gap-4">
        <label className="block w-full">
          <span className="mb-1 block text-xs text-muted-foreground">{t("new_password")}</span>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring"
          />
        </label>
        <button
          type="submit"
          disabled={loading || done}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("reset_password")}
        </button>

        {loading ? <Notice kind="info">{t("loading")}</Notice> : null}
        {error ? (
          <Notice kind="error">
            {t("error")}: {error}
          </Notice>
        ) : null}
        {done ? (
          <Notice kind="info">
            {t("reset_password_ok")}{" "}
            <Link to="/login" className="text-primary hover:underline">
              {t("login")}
            </Link>
          </Notice>
        ) : null}
      </form>
    </Page>
  );
}
