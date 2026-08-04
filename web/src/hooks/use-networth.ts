import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { NetWorthSnapshot } from "@/lib/types";

export function useNetWorthHistory(days = 90) {
  return useQuery({
    queryKey: ["networth", days],
    queryFn: async () => (await apiClient.get<NetWorthSnapshot[]>("/api/v1/networth", { params: { days } })).data,
  });
}

export function useRecomputeNetWorth() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => (await apiClient.post<NetWorthSnapshot>("/api/v1/networth/recompute")).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["networth"] }),
  });
}
