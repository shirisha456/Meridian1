import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Page, Transaction } from "@/lib/types";

export interface TransactionFilters {
  account_id?: string;
  category_id?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

interface CreateTransactionInput {
  account_id: string;
  category_id?: string | null;
  merchant_name: string;
  description?: string | null;
  amount_minor: number;
  txn_date: string;
}

export function useTransactions(filters: TransactionFilters = {}) {
  return useQuery({
    queryKey: ["transactions", filters],
    queryFn: async () =>
      (
        await apiClient.get<Page<Transaction>>("/api/v1/transactions", {
          params: { limit: 25, offset: 0, ...filters },
        })
      ).data,
  });
}

export function useCreateTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateTransactionInput) =>
      (await apiClient.post<Transaction>("/api/v1/transactions", input)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["budgets"] });
    },
  });
}

export function useDeleteTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/transactions/${id}`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["budgets"] });
    },
  });
}
