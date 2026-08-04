"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BellIcon } from "lucide-react";

import { useAlerts, useMarkAlertRead } from "@/hooks/use-alerts";
import { useLiveNotifications } from "@/hooks/use-live-notifications";
import type { AlertSeverity, LiveNotification } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const SEVERITY_VARIANT: Record<AlertSeverity, "secondary" | "default" | "destructive"> = {
  info: "secondary",
  warning: "default",
  critical: "destructive",
};

export function NotificationBell() {
  const { data: alerts } = useAlerts();
  const markRead = useMarkAlertRead();
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleNotification = useCallback((notification: LiveNotification) => {
    const message =
      notification.type === "alert"
        ? String(notification.data.title ?? "New alert")
        : "New spending insight ready";
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 6000);
  }, []);

  useLiveNotifications(handleNotification);

  useEffect(() => {
    return () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    };
  }, []);

  const unreadCount = (alerts ?? []).filter((a) => !a.read_at).length;
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          render={
            <Button variant="ghost" size="icon-sm" className="relative">
              <BellIcon />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
              <span className="sr-only">Notifications</span>
            </Button>
          }
        />
        {open && (
          <PopoverContent>
            <p className="mb-2 text-sm font-medium">Alerts</p>
            {!alerts || alerts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No alerts yet.</p>
            ) : (
              <ul className="flex max-h-80 flex-col gap-2 overflow-y-auto">
                {alerts.map((alert) => (
                  <li key={alert.id} className="flex flex-col gap-1 rounded-lg border border-border p-2 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{alert.title}</span>
                      <Badge variant={SEVERITY_VARIANT[alert.severity] ?? "secondary"}>{alert.severity}</Badge>
                    </div>
                    <p className="text-muted-foreground">{alert.detail}</p>
                    {!alert.read_at && (
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto self-start p-0"
                        onClick={() => void markRead.mutateAsync(alert.id)}
                      >
                        Mark read
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </PopoverContent>
        )}
      </Popover>
      {toast && (
        <div className="absolute top-full right-0 z-50 mt-2 w-64 rounded-lg border border-border bg-popover p-3 text-sm text-popover-foreground shadow-md">
          {toast}
        </div>
      )}
    </div>
  );
}
