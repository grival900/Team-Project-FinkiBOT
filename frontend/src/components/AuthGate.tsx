import { useEffect } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { isGuest, useAuth } from "@/lib/auth";

// Pages that work before logging in or choosing "Continue as guest".
// /widget is the chat inside the WordPress bubble, so it must never ask for a login.
export const PUBLIC_PATHS = new Set(["/login", "/register", "/reset-password", "/widget"]);

export function AuthGate() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  useEffect(() => {
    if (loading || user || isGuest() || PUBLIC_PATHS.has(pathname)) return;
    navigate({ to: "/login" });
  }, [loading, user, pathname, navigate]);

  return null;
}