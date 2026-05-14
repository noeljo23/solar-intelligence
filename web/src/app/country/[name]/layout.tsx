import { CountrySubNav } from "@/components/country-subnav";

export const dynamic = "force-dynamic";

export default function CountryLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { name: string };
}) {
  const name = decodeURIComponent(params.name);
  return (
    <div className="mx-auto max-w-5xl px-6 sm:px-8 py-10">
      <CountrySubNav country={name} />
      {children}
    </div>
  );
}
