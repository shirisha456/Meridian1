import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import type { ForecastResponse } from "@/lib/types";

export function useForecast(horizonDays = 30) {
  return useQuery({
    queryKey: ["forecast", horizonDays],
    queryFn: async () =>
      (await apiClient.get<ForecastResponse>("/api/v1/forecast", { params: { horizon_days: horizonDays } })).data,
  });
}
