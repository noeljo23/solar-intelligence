import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/10 text-primary ring-primary/30",
        secondary: "border-transparent bg-secondary/10 text-secondary ring-secondary/30",
        outline: "border-border bg-background/30 text-foreground ring-transparent",
        success: "border-transparent bg-emerald-500/10 text-emerald-400 ring-emerald-500/30",
        warning: "border-transparent bg-amber-500/10 text-amber-400 ring-amber-500/30",
        destructive: "border-transparent bg-rose-500/10 text-rose-400 ring-rose-500/30",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
