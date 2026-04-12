import { cn } from "@/lib/utils";
import { RATING_TONE } from "@/lib/api";
import type { Rating } from "@/lib/types";

export function RatingBadge({
  rating,
  className,
}: {
  rating: Rating | null;
  className?: string;
}) {
  if (!rating) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full border border-border px-2.5 py-0.5 text-xs font-medium text-muted-foreground",
          className,
        )}
      >
        Unrated
      </span>
    );
  }
  const tone = RATING_TONE[rating];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        tone.bg,
        tone.text,
        tone.ring,
        className,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {rating}
    </span>
  );
}
