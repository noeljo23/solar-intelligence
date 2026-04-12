import { api } from "@/lib/api";
import { Sidebar } from "@/components/sidebar";

export const dynamic = "force-dynamic";

export default async function MethodologyLayout({ children }: { children: React.ReactNode }) {
  const countries = await api.countries().catch(() => []);
  return (
    <div className="flex min-h-screen">
      <Sidebar countries={countries} activeCountry={null} />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-6 sm:px-10 py-10">{children}</div>
      </main>
    </div>
  );
}
