"use client";

import * as React from "react";
import { Select as SelectPrimitive } from "@base-ui/react/select";
import { CheckIcon, ChevronDownIcon } from "lucide-react";

import { cn } from "@/lib/utils";

// Base UI's own close-then-unmount timing (waiting on
// Element.getAnimations()) doesn't reliably fire in every environment
// this app runs in — same root cause documented in dialog.tsx. Rather
// than rely on it, this context lets SelectContent unmount itself via a
// plain React conditional the moment `open` goes false, which is
// synchronous and has no animation-frame dependency.
const SelectOpenContext = React.createContext(false);

function Select<Value, Multiple extends boolean | undefined = false>({
  children,
  open: openProp,
  onOpenChange,
  defaultOpen = false,
  ...props
}: SelectPrimitive.Root.Props<Value, Multiple>) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const open = openProp ?? uncontrolledOpen;
  const handleOpenChange = onOpenChange ?? setUncontrolledOpen;
  return (
    <SelectPrimitive.Root open={open} onOpenChange={handleOpenChange} {...props}>
      <SelectOpenContext.Provider value={open}>{children}</SelectOpenContext.Provider>
    </SelectPrimitive.Root>
  );
}

function SelectValue(props: SelectPrimitive.Value.Props) {
  return <SelectPrimitive.Value data-slot="select-value" {...props} />;
}

function SelectTrigger({ className, children, ...props }: SelectPrimitive.Trigger.Props) {
  return (
    <SelectPrimitive.Trigger
      data-slot="select-trigger"
      className={cn(
        "flex h-8 w-full items-center justify-between gap-1.5 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 data-placeholder:text-muted-foreground",
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon render={<ChevronDownIcon className="size-4 shrink-0 text-muted-foreground" />} />
    </SelectPrimitive.Trigger>
  );
}

function SelectContent({ className, children, ...props }: SelectPrimitive.Popup.Props) {
  const open = React.useContext(SelectOpenContext);
  if (!open) return null;

  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Positioner className="z-50" sideOffset={4}>
        <SelectPrimitive.Popup
          data-slot="select-content"
          className={cn(
            "z-50 max-h-(--available-height) min-w-(--anchor-width) overflow-y-auto rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-md",
            className,
          )}
          {...props}
        >
          <SelectPrimitive.List>{children}</SelectPrimitive.List>
        </SelectPrimitive.Popup>
      </SelectPrimitive.Positioner>
    </SelectPrimitive.Portal>
  );
}

function SelectItem({ className, children, ...props }: SelectPrimitive.Item.Props) {
  return (
    <SelectPrimitive.Item
      data-slot="select-item"
      className={cn(
        "relative flex w-full cursor-default items-center gap-1.5 rounded-md py-1.5 pr-8 pl-2 text-sm outline-none select-none focus:bg-accent focus:text-accent-foreground data-disabled:pointer-events-none data-disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator className="absolute right-2 flex size-4 items-center justify-center">
        <CheckIcon className="size-4" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}

export { Select, SelectContent, SelectItem, SelectTrigger, SelectValue };
