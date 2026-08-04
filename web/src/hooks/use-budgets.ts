import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Budget, BudgetActual } from "@/lib/types";

interface UpsertBudgetInput {
  category_id: string;
  month: string;
  amount_minor: number;
}

export function useBudgets(month: string) {
  return useQuery({
    queryKey: ["budgets", "list", month],
    queryFn: async () => (await apiClient.get<Budget[]>("/api/v1/budgets", { params: { month } })).data,
  });
}

export function useBudgetActual(month: string) {
  return useQuery({
    queryKey: ["budgets", "actual", month],
    queryFn: async () =>
      (await apiClient.get<BudgetActual[]>("/api/v1/budgets/actual", { params: { month } })).data,
  });
}

export function useUpsertBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: UpsertBudgetInput) => (await apiClient.put<Budget>("/api/v1/budgets", input)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["budgets"] }),
  });
}
