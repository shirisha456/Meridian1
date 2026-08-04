"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { bootstrapSession } from "@/lib/api-client";

declare global {
  var BASE_UI_ANIMATIONS_DISABLED: boolean | undefined;
}

// Popups/dialogs/selects in this app render and unmount with no CSS
// open/close animation (see components/ui/dialog.tsx and friends). Base
// UI's own unmount timing normally waits for Element.getAnimations() to
// resolve before removing a closed popup from the DOM — with nothing to
// animate that should resolve on the next frame regardless, but this
// documented flag skips that wait entirely and unmounts synchronously,
// which is both faster and removes any dependency on animation-frame
// timing (e.g. a backgrounded/non-visible tab throttling rAF).
if (typeof window !== "undefined") {
  globalThis.BASE_UI_ANIMATIONS_DISABLED = true;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, staleTime: 30_000 },
        },
      }),
  );

  useEffect(() => {
    void bootstrapSession();
  }, []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
