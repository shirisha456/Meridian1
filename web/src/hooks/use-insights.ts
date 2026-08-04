import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import { apiClient } from "@/lib/api-client";
import type { Insight } from "@/lib/types";

export function useLatestInsight() {
  return useQuery({
    queryKey: ["insights", "latest"],
    queryFn: async () => {
      try {
        return (await apiClient.get<Insight>("/api/v1/insights/latest")).data;
      } catch (error) {
        // No insight generated yet for this user is a valid, expected
        // state (404), not an error condition worth surfacing.
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          return null;
        }
        throw error;
      }
    },
  });
}

export function useGenerateInsight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (period?: { period_start?: string; period_end?: string }) =>
      (await apiClient.post<Insight>("/api/v1/insights/generate", period ?? {})).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["insights"] }),
  });
}
