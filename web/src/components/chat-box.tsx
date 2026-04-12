"use client";

import { useRef, useState } from "react";
import { Send, Sparkles, ExternalLink, Bot, User as UserIcon } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ChatResponseOut } from "@/lib/types";

type Msg =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; sources?: Array<Record<string, unknown>> };

const SUGGESTIONS = [
  "What are the main regulatory barriers?",
  "How does interconnection work here?",
  "Which state has the best feasibility score and why?",
  "Compare net metering rules across states.",
];

export function ChatBox({ country, stateNames }: { country: string; stateNames: string[] }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function submit(text: string) {
    if (!text.trim() || loading) return;
    const newHistory: Msg[] = [...messages, { role: "user", content: text }];
    setMessages(newHistory);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const history = newHistory.slice(0, -1).map((m) => ({ role: m.role, content: m.content }));
      const resp: ChatResponseOut = await api.chat(country, text, history);
      setMessages([...newHistory, { role: "assistant", content: resp.answer, sources: resp.sources }]);
      requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 rounded-xl border border-border/60 bg-card/40 overflow-hidden">
      <div className="px-5 py-3 border-b border-border/60 flex items-center gap-2 text-sm">
        <Sparkles className="h-4 w-4 text-primary" />
        <span className="font-medium">Ask about {country}</span>
        <span className="text-muted-foreground">·</span>
        <span className="text-xs text-muted-foreground">{stateNames.length} states indexed</span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-6 space-y-5 scrollbar-thin">
        {messages.length === 0 && (
          <div className="max-w-2xl">
            <p className="text-sm text-muted-foreground mb-4">
              Grounded in verified policy and market documents. Answers cite specific sources.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => submit(s)}
                  className="text-left rounded-lg border border-border/60 bg-card/40 hover:bg-card/70 hover:border-border transition-colors p-3 text-sm"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => <Bubble key={i} msg={m} />)}

        {loading && (
          <div className="flex gap-3 text-sm text-muted-foreground">
            <Bot className="h-5 w-5 text-primary mt-0.5" />
            <span className="animate-pulse">Thinking…</span>
          </div>
        )}

        {error && <div className="text-sm text-destructive">{error}</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
        className="border-t border-border/60 p-3 flex gap-2"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Ask something about solar in ${country}…`}
          disabled={loading}
          className="flex-1"
        />
        <Button type="submit" disabled={loading || !input.trim()} size="sm">
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

function Bubble({ msg }: { msg: Msg }) {
  if (msg.role === "user") {
    return (
      <div className="flex gap-3 justify-end">
        <div className="rounded-2xl bg-primary/15 border border-primary/20 text-foreground px-4 py-2.5 text-sm max-w-2xl">
          {msg.content}
        </div>
        <UserIcon className="h-5 w-5 text-muted-foreground mt-1.5 shrink-0" />
      </div>
    );
  }
  return (
    <div className="flex gap-3">
      <Bot className="h-5 w-5 text-primary mt-1 shrink-0" />
      <div className="space-y-3 max-w-3xl">
        <div className="text-sm leading-relaxed whitespace-pre-wrap text-foreground/95">{msg.content}</div>
        {msg.sources && msg.sources.length > 0 && (
          <details className="group">
            <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground select-none">
              {msg.sources.length} source{msg.sources.length === 1 ? "" : "s"}
            </summary>
            <div className="mt-2 space-y-1">
              {msg.sources.map((s, i) => {
                const org = typeof s.organization === "string" ? s.organization : "Source";
                const doc = typeof s.document === "string" ? s.document : "";
                const url = typeof s.url === "string" ? s.url : "";
                return url ? (
                  <a
                    key={i}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-xs text-muted-foreground hover:text-primary"
                  >
                    <span className="text-foreground font-medium">{org}</span>
                    <span>·</span>
                    <span className="truncate">{doc}</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : null;
              })}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
