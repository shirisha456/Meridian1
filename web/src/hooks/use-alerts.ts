import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Alert } from "@/lib/types";

export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: async () => (await apiClient.get<Alert[]>("/api/v1/alerts")).data,
    // The WS live push is the primary delivery path; this poll is the
    // fallback for a dropped/reconnecting socket, not the main mechanism.
    refetchInterval: 30_000,
  });
}

export function useMarkAlertRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await apiClient.patch<Alert>(`/api/v1/alerts/${id}/read`)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });
}
