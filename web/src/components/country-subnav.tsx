"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export function CountrySubNav({ country }: { country: string }) {
  const pathname = usePathname();
  const base = `/country/${encodeURIComponent(country)}`;
  const tabs = [
    { href: base, label: "Overview" },
    { href: `${base}/deep-dive`, label: "Deep dive" },
    { href: `${base}/chat`, label: "Chat" },
    { href: `${base}/audit`, label: "Audit" },
  ];

  return (
    <nav className="mb-8 flex gap-1 border-b border-border">
      {tabs.map((t) => {
        const active =
          t.href === base
            ? pathname === base
            : pathname === t.href || pathname?.startsWith(t.href + "/");
        return (
          <Link
            key={t.href}
            href={t.href}
            className={cn(
              "px-3 py-2 -mb-px text-sm border-b-2 transition",
              active
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
