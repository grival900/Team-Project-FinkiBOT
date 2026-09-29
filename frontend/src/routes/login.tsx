import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Notice, Page } from "@/components/Page";
import { useI18n } from "@/lib/i18n";
import { continueAsGuest, useAuth } from "@/lib/auth";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [{ title: "Најава — FinkiBOT" }],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { t } = useI18n();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      navigate({ to: "/" });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  function guest() {
    continueAsGuest();
    navigate({ to: "/" });
  }

  return (
    <Page title={t("login")}>
      <form onSubmit={submit} className="mx-auto flex max-w-sm flex-col items-center gap-4">
        <label className="block w-full">
          <span className="mb-1 block text-xs text-muted-foreground">{t("email")}</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring"
          />
        </label>
        <label className="block w-full">
          <span className="mb-1 block text-xs text-muted-foreground">{t("password")}</span>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring"
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {t("login")}
        </button>

        {loading ? <Notice kind="info">{t("loading")}</Notice> : null}
        {error ? (
          <Notice kind="error">
            {t("error")}: {error}
          </Notice>
        ) : null}

        <p className="text-sm text-muted-foreground">
          {t("no_account_yet")}{" "}
          <Link to="/register" className="text-primary hover:underline">
            {t("register")}
          </Link>
        </p>

        <button type="button" onClick={guest} className="text-sm text-muted-foreground hover:underline">
          {t("continue_as_guest")}
        </button>
      </form>
    </Page>
  );
}
