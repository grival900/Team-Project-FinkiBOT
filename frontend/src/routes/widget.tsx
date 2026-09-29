import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { streamChat, type ChatMessage, type LlmProvider } from "@/lib/api";
import { Markdown } from "@/components/Markdown";

// The chat inside the WordPress bubble widget: no sidebar, no login, no saved history
// (closing the bubble starts a new conversation).
export const Route = createFileRoute("/widget")({
  head: () => ({
    meta: [{ title: "FinkiBOT" }],
  }),
  component: WidgetChatPage,
});

function WidgetChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeProvider, setActiveProvider] = useState<LlmProvider | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const history = messages;
    const nextMessages: ChatMessage[] = [...history, { role: "user", content: text }];
    setMessages(nextMessages);
    setInput("");
    setError(null);
    setLoading(true);
    setActiveProvider(null);

    let acc = "";
    setMessages([...nextMessages, { role: "assistant", content: "" }]);
    try {
      await streamChat(
        text,
        history,
        (chunk) => {
          acc += chunk;
          setMessages([...nextMessages, { role: "assistant", content: acc }]);
        },
        undefined,
        setActiveProvider,
      );
    } catch {
      setError("Не успеав да добијам одговор. Обидете се повторно.");
      setMessages(nextMessages);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="flex shrink-0 items-center gap-2 border-b border-border px-4 py-3">
        <div className="h-2 w-2 rounded-full bg-primary" />
        <span className="text-sm font-semibold">FinkiBOT</span>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Прашај ме нешто за ФИНКИ - соопштенија, предмети, професори, распореди, консултации...
          </p>
        ) : null}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div
              className={
                m.role === "user"
                  ? "max-w-[85%] rounded-2xl bg-primary px-3 py-2 text-sm text-primary-foreground"
                  : "max-w-[85%] rounded-2xl bg-muted px-3 py-2 text-sm"
              }
            >
              {m.role === "assistant" ? <Markdown content={m.content} /> : m.content}
            </div>
          </div>
        ))}
        {error ? <p className="text-xs text-destructive">{error}</p> : null}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={send} className="flex shrink-0 gap-2 border-t border-border p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Прашај нешто за ФИНКИ..."
          className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="flex items-center justify-center rounded-md bg-primary px-3 py-2 text-primary-foreground disabled:opacity-50"
          aria-label="Испрати"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}