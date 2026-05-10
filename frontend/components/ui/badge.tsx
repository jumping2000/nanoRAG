import * as React from "react";

import { cn } from "@/lib/utils";

export function Badge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-border/80 bg-muted/70 px-2.5 py-1 text-xs font-medium text-foreground/80",
        className,
      )}
      {...props}
    />
  );
}
