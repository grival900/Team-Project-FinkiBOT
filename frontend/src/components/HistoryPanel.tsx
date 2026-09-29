import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import {
  clearConversations,
  deleteConversation,
  loadConversations,
  type Conversation,
} from "@/lib/chat-history";
import { cn } from "@/lib/utils";

export function HistoryPanel() {
  const { t } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const search = useRouterState({ select: (s) => s.location.search as { c?: string } });
  const [conversations, setConversations] = useState<Conversation[]>([]);

  useEffect(() => {
    const sync = () => setConversations(loadConversations(user?.id));
    sync();
    window.addEventListener("finkibot-conversations", sync);
    return () => window.removeEventListener("finkibot-conversations", sync);
  }, [user?.id]);

  function handleDelete(e: React.MouseEvent, id: string) {
    e.preventDefault();
    e.stopPropagation();
    deleteConversation(id, user?.id);
    if (search.c === id) {
      navigate({ to: "/", search: { new: Date.now() } });
    }
  }

  function handleDeleteAll() {
    if (!confirm(t("confirm_delete_all_chats"))) return;
    clearConversations(user?.id);
    if (search.c) {
      navigate({ to: "/", search: { new: Date.now() } });
    }
  }

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-l border-border bg-sidebar text-sidebar-foreground">
      <div className="flex items-center justify-between border-b border-border px-4 py-4">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {t("history")}
        </span>
        <div className="flex items-center gap-0.5">
          {conversations.length > 0 ? (
            <button
              type="button"
              onClick={handleDeleteAll}
              className="rounded-md p-1 text-destructive hover:bg-destructive/10"
              aria-label={t("delete_all_chats")}
            >
              <Trash2 className="size-4" />
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => navigate({ to: "/", search: { new: Date.now() } })}
            className="rounded-md p-1 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
            aria-label={t("new_chat")}
          >
            <Plus className="size-4" />
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {conversations.length === 0 ? (
          <p className="px-2 py-1 text-xs text-muted-foreground">{t("no_history")}</p>
        ) : (
          conversations.map((c) => (
            <Link
              key={c.id}
              to="/"
              search={{ c: c.id }}
              className={cn(
                "group flex items-center gap-1 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
                search.c === c.id && "bg-sidebar-accent text-foreground",
              )}
            >
              <span className="min-w-0 flex-1 truncate">{c.title}</span>
              <button
                type="button"
                onClick={(e) => handleDelete(e, c.id)}
                aria-label={t("delete_chat")}
                className="shrink-0 rounded p-1 text-destructive opacity-0 hover:bg-destructive/10 group-hover:opacity-100"
              >
                <Trash2 className="size-3.5" />
              </button>
            </Link>
          ))
        )}
      </div>
    </aside>
  );
}
