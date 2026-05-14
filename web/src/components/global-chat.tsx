"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { ArrowUp, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import type { GlobalChatResponseOut } from "@/lib/types";

type Msg =
  | { role: "user"; content: string }
  | {
      role: "assistant";
      content: string;
      countries?: string[];
      sources?: Array<Record<string, unknown>>;
    };

const SUGGESTIONS = [
  "Compare net metering in Mexico and Brazil",
  "Which country has the fastest interconnection times?",
  "Summarize tax incentives for solar in Colombia",
  "What is PMGD in Chile?",
];

export function GlobalChat({ size = "hero" }: { size?: "hero" | "page" }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function submit(text: string) {
    const value = text.trim();
    if (!value || loading) return;
    const next: Msg[] = [...messages, { role: "user", content: value }];
    setMessages(next);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const history = next.slice(0, -1).map((m) => ({ role: m.role, content: m.content }));
      const resp: GlobalChatResponseOut = await api.chatGlobal(value, history);
      setMessages([
        ...next,
        {
          role: "assistant",
          content: resp.answer,
          countries: resp.countries_used,
          sources: resp.sources,
        },
      ]);
      requestAnimationFrame(() =>
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const hasMessages = messages.length > 0;
  const inputClass =
    size === "hero"
      ? "w-full resize-none bg-transparent text-lg placeholder:text-muted-foreground focus:outline-none px-5 py-4 min-h-[64px] max-h-[200px]"
      : "w-full resize-none bg-transparent placeholder:text-muted-foreground focus:outline-none px-4 py-3 min-h-[52px] max-h-[180px]";

  return (
    <div className="w-full">
      {hasMessages && (
        <div
          ref={scrollRef}
          className="mb-4 max-h-[55vh] overflow-y-auto space-y-6 scrollbar-thin pr-1"
        >
          {messages.map((m, i) => (
            <Bubble key={i} msg={m} />
          ))}
          {loading && (
            <div className="flex gap-3 text-sm text-muted-foreground">
              <span className="animate-pulse">Thinking…</span>
            </div>
          )}
          {error && <div className="text-sm text-destructive">{error}</div>}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
        className="relative rounded-2xl border border-border bg-card shadow-sm focus-within:border-foreground/30 transition"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit(input);
            }
          }}
          placeholder="Ask about any market…"
          disabled={loading}
          rows={1}
          className={inputClass}
        />
        <div className="flex items-center justify-between px-3 pb-2 pt-1">
          <span className="text-[11px] text-muted-foreground">
            Answers are grounded in verified policy + market documents.
          </span>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-40"
            aria-label="Send"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
      </form>

      {!hasMessages && size === "hero" && (
        <div className="mt-4 flex flex-wrap gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => submit(s)}
              className="rounded-full border border-border bg-card px-3.5 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/30 transition"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Bubble({ msg }: { msg: Msg }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-2xl rounded-2xl bg-muted px-4 py-2.5 text-[18px] text-foreground">
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {msg.countries && msg.countries.length > 0 && (
        <div className="flex flex-wrap gap-1.5 text-[13px]">
          {msg.countries.map((c) => (
            <Link
              key={c}
              href={`/country/${encodeURIComponent(c)}`}
              className="rounded-full border border-border bg-card px-2.5 py-0.5 text-muted-foreground hover:text-foreground hover:border-foreground/30"
            >
              {c}
            </Link>
          ))}
        </div>
      )}
      <div className="text-[20px] leading-relaxed whitespace-pre-wrap text-foreground">
        {msg.content}
      </div>
      {msg.sources && msg.sources.length > 0 && (
        <details className="group">
          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground select-none">
            {msg.sources.length} source{msg.sources.length === 1 ? "" : "s"}
          </summary>
          <div className="mt-2 space-y-1.5">
            {msg.sources.map((s, i) => {
              const country = typeof s.country === "string" ? s.country : "";
              const raw = typeof s.sources === "string" ? s.sources : "";
              const first = raw.split(" | ")[0] ?? raw;
              const match = first.match(/^(.+?):\s(.+?)\s\(.+?\)\s<(.+)>$/);
              const org = match?.[1] ?? first;
              const doc = match?.[2] ?? "";
              const url = match?.[3] ?? "";
              return (
                <a
                  key={i}
                  href={url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  {country && (
                    <span className="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-foreground">
                      {country}
                    </span>
                  )}
                  <span className="truncate">
                    <span className="font-medium text-foreground">{org}</span>
                    {doc && <span> · {doc}</span>}
                  </span>
                  {url && <ExternalLink className="h-3 w-3 shrink-0" />}
                </a>
              );
            })}
          </div>
        </details>
      )}
    </div>
  );
}
