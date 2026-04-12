"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Telescope,
  MessageSquareText,
  ShieldCheck,
  BookOpenText,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { CountrySummary } from "@/lib/types";

interface SidebarProps {
  countries: CountrySummary[];
  activeCountry: string | null;
}

const NAV = [
  { key: "",            label: "Dashboard",  icon: LayoutDashboard },
  { key: "/deep-dive",  label: "Deep Dive",  icon: Telescope },
  { key: "/chat",       label: "Ask AI",     icon: MessageSquareText },
  { key: "/audit",      label: "Data Audit", icon: ShieldCheck },
] as const;

export function Sidebar({ countries, activeCountry }: SidebarProps) {
  const pathname = usePathname() || "";

  return (
    <aside className="hidden lg:flex lg:w-72 shrink-0 border-r border-border/60 bg-card/30 backdrop-blur-md">
      <div className="flex flex-col w-full h-screen sticky top-0">
        <div className="px-6 py-5 border-b border-border/60">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-secondary shadow-lg shadow-primary/20">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div className="leading-tight">
              <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">PowerTrust</div>
              <div className="text-sm font-semibold">Solar Intelligence</div>
            </div>
          </Link>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin">
          {activeCountry && (
            <div className="px-3 pb-3">
              <div className="text-[11px] uppercase tracking-widest text-muted-foreground mb-2">
                Views
              </div>
              <nav className="space-y-0.5">
                {NAV.map((item) => {
                  const href = `/country/${encodeURIComponent(activeCountry)}${item.key}`;
                  const active =
                    pathname === href ||
                    (item.key === "" && pathname === `/country/${encodeURIComponent(activeCountry)}`);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.label}
                      href={href}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                        active
                          ? "bg-primary/15 text-primary font-medium"
                          : "text-muted-foreground hover:bg-accent/10 hover:text-foreground",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </Link>
                  );
                })}
                <Link
                  href="/methodology"
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors mt-3",
                    pathname === "/methodology"
                      ? "bg-primary/15 text-primary font-medium"
                      : "text-muted-foreground hover:bg-accent/10 hover:text-foreground",
                  )}
                >
                  <BookOpenText className="h-4 w-4" />
                  Methodology
                </Link>
              </nav>
            </div>
          )}

          <div className="px-3 pt-3">
            <div className="text-[11px] uppercase tracking-widest text-muted-foreground mb-2">
              Countries · {countries.length}
            </div>
            <div className="space-y-1">
              {countries.map((c) => {
                const active = activeCountry === c.name;
                return (
                  <Link
                    key={c.name}
                    href={`/country/${encodeURIComponent(c.name)}`}
                    className={cn(
                      "flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors",
                      active
                        ? "bg-accent/15 text-foreground"
                        : "text-muted-foreground hover:bg-accent/10 hover:text-foreground",
                    )}
                  >
                    <span className="truncate flex-1">{c.name}</span>
                    {c.avg_score != null && (
                      <span className="text-xs font-mono tabular-nums text-muted-foreground">
                        {c.avg_score.toFixed(0)}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        </div>

        <div className="px-6 py-3 border-t border-border/60 text-[11px] text-muted-foreground">
          Zero-hallucination RAG · 10 markets
        </div>
      </div>
    </aside>
  );
}
