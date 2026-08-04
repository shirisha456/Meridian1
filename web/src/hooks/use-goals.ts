import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Goal, Page } from "@/lib/types";

interface CreateGoalInput {
  name: string;
  target_amount_minor: number;
  current_amount_minor: number;
  target_date?: string | null;
}

interface UpdateGoalInput {
  id: string;
  name?: string;
  target_amount_minor?: number;
  current_amount_minor?: number;
  target_date?: string | null;
}

export function useGoals(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["goals", limit, offset],
    queryFn: async () => (await apiClient.get<Page<Goal>>("/api/v1/goals", { params: { limit, offset } })).data,
  });
}

export function useCreateGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateGoalInput) => (await apiClient.post<Goal>("/api/v1/goals", input)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["goals"] }),
  });
}

export function useUpdateGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: UpdateGoalInput) =>
      (await apiClient.patch<Goal>(`/api/v1/goals/${id}`, input)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["goals"] }),
  });
}

export function useDeleteGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/goals/${id}`);
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["goals"] }),
  });
}
