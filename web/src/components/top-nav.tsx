import Link from "next/link";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/markets", label: "Markets" },
  { href: "/methodology", label: "Methodology" },
];

export function TopNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2">
          <svg
            viewBox="0 0 24 24"
            className="h-[22px] w-[22px] text-primary"
            fill="currentColor"
            aria-label="Solis sad moon"
          >
            <circle cx="12" cy="12" r="10" />
            <circle cx="9" cy="10.5" r="1.1" fill="white" />
            <circle cx="15" cy="10.5" r="1.1" fill="white" />
            <path
              d="M8.5 16.5 Q12 14 15.5 16.5"
              stroke="white"
              strokeWidth="1.4"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
          <span className="text-sm font-semibold tracking-tight">Solis</span>
        </Link>
        <nav className="flex items-center gap-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
