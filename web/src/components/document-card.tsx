import { ExternalLink, ShieldCheck, Languages } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { DocumentOut } from "@/lib/types";

const LANG_LABELS: Record<string, string> = {
  pt: "Portuguese",
  es: "Spanish",
  id: "Bahasa Indonesia",
  vi: "Vietnamese",
  ms: "Malay",
};

function detectLangsFromSources(doc: DocumentOut): string[] {
  const hits = new Set<string>();
  for (const s of doc.sources) {
    const hay = `${s.url} ${s.organization}`.toLowerCase();
    if (/\.br\b|aneel|cemig|copel/.test(hay)) hits.add("pt");
    if (/\.mx\b|\.cl\b|\.co\b|cre\.|cne\.|creg|ixl|cfe/.test(hay)) hits.add("es");
    if (/\.id\b|esdm|memr|pln\b/.test(hay)) hits.add("id");
    if (/\.vn\b|evn|moit/.test(hay)) hits.add("vi");
    if (/\.my\b|tnb|suruhanjaya/.test(hay)) hits.add("ms");
  }
  return Array.from(hits);
}

export function DocumentCard({ doc }: { doc: DocumentOut }) {
  const langs = detectLangsFromSources(doc);
  const confidenceVariant = doc.confidence === "high" ? "success" : doc.confidence === "medium" ? "warning" : "destructive";

  return (
    <div className="rounded-xl border border-border/60 bg-card/40 p-5 space-y-3 transition-colors hover:border-border">
      <div className="flex items-center gap-2 flex-wrap">
        <code className="text-[11px] font-mono text-muted-foreground">{doc.id}</code>
        <Badge variant={confidenceVariant}>
          <ShieldCheck className="h-3 w-3 mr-1" />
          {doc.confidence}
        </Badge>
        {langs.map((l) => (
          <Badge key={l} variant="outline">
            <Languages className="h-3 w-3 mr-1" />
            {LANG_LABELS[l] ?? l.toUpperCase()}
          </Badge>
        ))}
        <span className="text-xs text-muted-foreground ml-auto">Verified {doc.last_verified}</span>
      </div>

      <p className="text-sm leading-relaxed text-foreground/90">{doc.content}</p>

      <div className="space-y-1 pt-1">
        {doc.sources.map((s, i) => (
          <a
            key={i}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-primary transition-colors group"
          >
            <span className="text-foreground font-medium">{s.organization}</span>
            <span>·</span>
            <span className="truncate">{s.document}</span>
            <span>·</span>
            <span className="tabular-nums">{s.accessed}</span>
            <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
          </a>
        ))}
      </div>
    </div>
  );
}
