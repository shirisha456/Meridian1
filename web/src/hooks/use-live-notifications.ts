"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/lib/auth-store";
import { resolveWsUrl } from "@/lib/resolve-api-url";
import type { LiveNotification, WsTicketResponse } from "@/lib/types";

const RECONNECT_DELAYS_MS = [1000, 2000, 5000, 10000, 15000];

// WS tickets are single-use and 30s-lived (server-side, see the backend's
// app/core/ws_tickets.py) specifically so a long-lived access token never
// has to sit in a URL where a proxy/server access log could capture it.
// That means every connection attempt — including every reconnect after
// a dropped socket — needs its own freshly minted ticket; a stale one
// from a previous attempt cannot be reused.
export function useLiveNotifications(onNotification?: (notification: LiveNotification) => void) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const queryClient = useQueryClient();
  const onNotificationRef = useRef(onNotification);
  useEffect(() => {
    onNotificationRef.current = onNotification;
  }, [onNotification]);

  useEffect(() => {
    if (!accessToken) return;

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let stopped = false;

    function scheduleReconnect() {
      if (stopped) return;
      const delay = RECONNECT_DELAYS_MS[Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)];
      attempt += 1;
      reconnectTimer = setTimeout(() => void connect(), delay);
    }

    async function connect() {
      if (stopped) return;
      try {
        const { data } = await apiClient.post<WsTicketResponse>("/api/v1/auth/ws-ticket");
        if (stopped) return;

        const ws = new WebSocket(`${resolveWsUrl()}/ws/live?ticket=${data.ticket}`);
        socket = ws;

        ws.onopen = () => {
          attempt = 0;
        };
        ws.onmessage = (event) => {
          const notification = JSON.parse(event.data) as LiveNotification;
          if (notification.type === "alert") {
            void queryClient.invalidateQueries({ queryKey: ["alerts"] });
          } else if (notification.type === "insight") {
            void queryClient.invalidateQueries({ queryKey: ["insights"] });
          }
          onNotificationRef.current?.(notification);
        };
        ws.onclose = scheduleReconnect;
        ws.onerror = () => ws.close();
      } catch {
        scheduleReconnect();
      }
    }

    void connect();

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [accessToken, queryClient]);
}
