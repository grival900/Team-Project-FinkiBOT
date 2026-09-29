import type { ChatMessage } from "./api";

export type Conversation = {
  id: string;
  title: string;
  updatedAt: number;
  messages: ChatMessage[];
};

const KEY_PREFIX = "finkibot-conversations";

// stored per user ("guest" when logged out) so accounts don't share history
function storageKey(userId: string | null | undefined): string {
  return `${KEY_PREFIX}:${userId ?? "guest"}`;
}

export function loadConversations(userId?: string | null): Conversation[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Conversation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveConversations(list: Conversation[], userId?: string | null) {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(list.slice(0, 40)));
    window.dispatchEvent(new CustomEvent("finkibot-conversations"));
  } catch {
    /* ignore */
  }
}

export function deleteConversation(id: string, userId?: string | null) {
  const rest = loadConversations(userId).filter((x) => x.id !== id);
  saveConversations(rest, userId);
}

export function clearConversations(userId?: string | null) {
  saveConversations([], userId);
}

export function newId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}
