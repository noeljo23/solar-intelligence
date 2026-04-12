import { api } from "@/lib/api";
import { Sidebar } from "@/components/sidebar";

export const dynamic = "force-dynamic";

export default async function CountryLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { name: string };
}) {
  const countries = await api.countries().catch(() => []);
  const active = decodeURIComponent(params.name);
  return (
    <div className="flex min-h-screen">
      <Sidebar countries={countries} activeCountry={active} />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl px-6 sm:px-10 py-10">{children}</div>
      </main>
    </div>
  );
}
