import Link from "next/link";
import { api } from "@/lib/api";
import { GlobalChat } from "@/components/global-chat";
import type { CountrySummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function Home() {
  const countries = await api.countries().catch(() => [] as CountrySummary[]);

  return (
    <div className="mx-auto max-w-3xl px-6 pt-16 pb-24 sm:pt-24">
      <section className="text-center space-y-5">
        <h1 className="text-[38px] sm:text-[46px] font-semibold tracking-tight text-balance leading-[1.05]">
          Solar market intelligence
          <br />
          for emerging economies.
        </h1>
        <p className="text-[17px] text-muted-foreground max-w-xl mx-auto text-balance">
          Ask anything. We cite the source.
        </p>
      </section>

      <section className="mt-10">
        <GlobalChat size="hero" />
      </section>

      <section className="mt-20">
        <div className="flex items-baseline justify-between mb-5">
          <h2 className="text-sm font-medium text-muted-foreground">Or browse by market</h2>
          <Link
            href="/markets"
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            See all →
          </Link>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
          {countries.map((c) => (
            <Link
              key={c.name}
              href={`/country/${encodeURIComponent(c.name)}`}
              className="rounded-lg border border-border bg-card px-3 py-2.5 hover:border-foreground/30 transition"
            >
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                {c.iso_code}
              </div>
              <div className="text-sm font-medium mt-0.5">{c.name}</div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
