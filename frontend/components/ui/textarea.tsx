import * as React from "react";

import { cn } from "@/lib/utils";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => {
  return (
    <textarea
      ref={ref}
      className={cn(
        "min-h-[56px] w-full resize-none rounded-3xl border border-border/80 bg-card/75 px-4 py-3 text-sm text-foreground outline-none placeholder:text-foreground/45 focus:border-primary/60 focus:ring-2 focus:ring-primary/20",
        className,
      )}
      {...props}
    />
  );
});

Textarea.displayName = "Textarea";
