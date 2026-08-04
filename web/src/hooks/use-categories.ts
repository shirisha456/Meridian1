import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { Category } from "@/lib/types";

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: async () => (await apiClient.get<Category[]>("/api/v1/categories")).data,
  });
}
