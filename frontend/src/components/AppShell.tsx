import type { ReactNode } from "react";
import { useRouterState } from "@tanstack/react-router";
import { isGuest, useAuth } from "@/lib/auth";
import { PUBLIC_PATHS } from "@/components/AuthGate";
import { Sidebar } from "@/components/Sidebar";
import { HistoryPanel } from "@/components/HistoryPanel";

// No sidebar until the visitor has logged in or chosen "Continue as guest".
// We watch the route too, because the guest choice doesn't change auth state.
export function AppShell({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const authorized = user !== null || isGuest();
  const onPublicPath = PUBLIC_PATHS.has(pathname);

  // the WordPress widget iframe gets just the chat, no sidebar and no auth wait
  if (pathname === "/widget") {
    return <main className="h-screen overflow-hidden bg-background">{children}</main>;
  }

  // Auth is only known in the browser, so render nothing until it's loaded -
  // otherwise protected pages flash for a moment before the redirect to /login.
  if (loading || (!authorized && !onPublicPath)) {
    return <div className="h-screen bg-background" />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      {authorized ? <Sidebar /> : null}
      <main className="bg-plaid min-w-0 flex-1 overflow-y-auto">{children}</main>
      {authorized ? <HistoryPanel /> : null}
    </div>
  );
}
