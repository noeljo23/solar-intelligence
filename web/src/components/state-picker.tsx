"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

export function StatePicker({ states, current }: { states: string[]; current: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const onChange = (value: string) => {
    const sp = new URLSearchParams(params.toString());
    sp.set("state", value);
    router.push(`${pathname}?${sp.toString()}`);
  };

  return (
    <Select value={current} onValueChange={onChange}>
      <SelectTrigger className="w-64">
        <SelectValue placeholder="Select state" />
      </SelectTrigger>
      <SelectContent>
        {states.map((s) => (
          <SelectItem key={s} value={s}>
            {s}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
