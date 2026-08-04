import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Institution } from "@/lib/types";

interface LinkInstitutionInput {
  public_token: string;
  institution_id?: string;
  institution_name?: string;
}

export function useInstitutions() {
  return useQuery({
    queryKey: ["institutions"],
    queryFn: async () => (await apiClient.get<Institution[]>("/api/v1/institutions")).data,
  });
}

export function useCreateLinkToken() {
  return useMutation({
    mutationFn: async () => (await apiClient.post<{ link_token: string }>("/api/v1/institutions/link-token")).data,
  });
}

export function useLinkInstitution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: LinkInstitutionInput) =>
      (await apiClient.post<Institution>("/api/v1/institutions", input)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["institutions"] });
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useUnlinkInstitution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/institutions/${id}`);
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["institutions"] }),
  });
}

export function useSyncInstitution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await apiClient.post<{ transactions_changed: number }>(`/api/v1/institutions/${id}/sync`)).data,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}
