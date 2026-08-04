import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Account, AccountType, Page } from "@/lib/types";

interface CreateAccountInput {
  name: string;
  type: AccountType;
  currency: string;
  current_balance_minor: number;
}

interface UpdateAccountInput {
  id: string;
  name?: string;
  type?: AccountType;
  currency?: string;
  current_balance_minor?: number;
}

export function useAccounts(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["accounts", limit, offset],
    queryFn: async () => (await apiClient.get<Page<Account>>("/api/v1/accounts", { params: { limit, offset } })).data,
  });
}

export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateAccountInput) => (await apiClient.post<Account>("/api/v1/accounts", input)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

export function useUpdateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: UpdateAccountInput) =>
      (await apiClient.patch<Account>(`/api/v1/accounts/${id}`, input)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

export function useDeleteAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/accounts/${id}`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}
