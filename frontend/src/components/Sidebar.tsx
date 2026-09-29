import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  MessageSquare,
  Search,
  ListChecks,
  Bell,
  BarChart3,
  Wrench,
  Sun,
  Moon,
  Monitor,
  User,
  Shield,
  LogOut,
} from "lucide-react";
import { useI18n, type TKey } from "@/lib/i18n";
import { useTheme, type ThemeMode } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV: { to: string; key: TKey; icon: typeof Search }[] = [
  { to: "/", key: "nav_chat", icon: MessageSquare },
  { to: "/search", key: "nav_search", icon: Search },
  { to: "/quiz", key: "nav_quiz", icon: ListChecks },
  { to: "/subscribe", key: "nav_subscribe", icon: Bell },
  { to: "/insights", key: "nav_insights", icon: BarChart3 },
  { to: "/mcp", key: "nav_mcp", icon: Wrench },
];

const THEMES: { mode: ThemeMode; key: TKey; icon: typeof Sun }[] = [
  { mode: "light", key: "light", icon: Sun },
  { mode: "dark", key: "dark", icon: Moon },
  { mode: "system", key: "system", icon: Monitor },
];

export function Sidebar() {
  const { t, lang, setLang } = useI18n();
  const { mode, setMode } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const nav = user?.is_admin ? [...NAV, { to: "/admin", key: "admin" as const, icon: Shield }] : NAV;

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r border-border bg-sidebar text-sidebar-foreground">
      <div className="border-b border-border px-4 py-4">
        <Link to="/" className="flex items-center gap-2">
          <span className="flex size-8 flex-col items-center justify-center gap-px rounded-md bg-primary leading-none text-primary-foreground">
            <span className="text-[9px] font-extrabold tracking-wide">IO</span>
            <span className="text-[7px] font-bold tracking-wide">BOT</span>
          </span>
          <span>
            <span className="block text-sm font-semibold">{t("brand")}</span>
            <span className="block text-xs text-muted-foreground">{t("tagline")}</span>
          </span>
        </Link>
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-0.5 p-2">
        {nav.map(({ to, key, icon: Icon }) => {
          const active = to === "/" ? pathname === "/" : pathname.startsWith(to);
          return (
            <Link
              key={to}
              to={to}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-primary/12 font-medium text-primary"
                  : "text-sidebar-foreground hover:bg-sidebar-accent",
              )}
            >
              <Icon className="size-4" />
              {t(key)}
            </Link>
          );
        })}
      </nav>

      <div className="space-y-3 border-t border-border p-3">
        {user ? (
          <div className="flex items-center gap-2">
            <span className="flex size-8 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
              <User className="size-4" />
            </span>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-sm font-medium">{user.email}</span>
              <span className="block text-xs text-muted-foreground">
                {user.is_admin ? t("admin_badge") : t("profile")}
              </span>
            </span>
            <button
              type="button"
              onClick={() => {
                logout();
                navigate({ to: "/" });
              }}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
              aria-label={t("logout")}
            >
              <LogOut className="size-4" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="flex size-8 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
              <User className="size-4" />
            </span>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block text-sm font-medium">{t("guest")}</span>
              <span className="block text-xs text-muted-foreground">{t("no_login")}</span>
            </span>
            <Link to="/login" className="text-xs text-primary hover:underline">
              {t("login")}
            </Link>
          </div>
        )}

        <div>
          <span className="mb-1 block text-xs text-muted-foreground">{t("theme")}</span>
          <div className="flex gap-1 rounded-md border border-border p-0.5">
            {THEMES.map(({ mode: m, key, icon: Icon }) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={cn(
                  "flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-xs transition-colors",
                  mode === m
                    ? "bg-primary/12 text-primary"
                    : "text-muted-foreground hover:bg-sidebar-accent",
                )}
              >
                <Icon className="size-3.5" />
                {t(key)}
              </button>
            ))}
          </div>
        </div>

        <div>
          <span className="mb-1 block text-xs text-muted-foreground">{t("language")}</span>
          <div className="flex gap-1 rounded-md border border-border p-0.5">
            {(["mk", "en"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={cn(
                  "flex-1 rounded px-2 py-1 text-xs uppercase transition-colors",
                  lang === l
                    ? "bg-primary/12 text-primary"
                    : "text-muted-foreground hover:bg-sidebar-accent",
                )}
              >
                {l === "mk" ? "МК" : "EN"}
              </button>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}
