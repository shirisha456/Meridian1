import { Progress as ProgressPrimitive } from "@base-ui/react/progress";

import { cn } from "@/lib/utils";

function Progress({
  className,
  value,
  indicatorClassName,
  ...props
}: ProgressPrimitive.Root.Props & { indicatorClassName?: string }) {
  return (
    <ProgressPrimitive.Root value={value} data-slot="progress" className={cn("w-full", className)} {...props}>
      <ProgressPrimitive.Track className="relative flex h-1.5 w-full items-center overflow-hidden rounded-full bg-muted">
        <ProgressPrimitive.Indicator
          data-slot="progress-indicator"
          className={cn("h-full bg-primary transition-all", indicatorClassName)}
        />
      </ProgressPrimitive.Track>
    </ProgressPrimitive.Root>
  );
}

export { Progress };
