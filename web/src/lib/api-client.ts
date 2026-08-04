import axios, { type InternalAxiosRequestConfig } from "axios";

import { useAuthStore } from "@/lib/auth-store";
import { resolveApiUrl } from "@/lib/resolve-api-url";
import type { TokenResponse, User } from "@/lib/types";

const API_URL = resolveApiUrl();

export const apiClient = axios.create({
  baseURL: API_URL,
  // Rides the httpOnly refresh-token cookie along with every request so
  // POST /api/v1/auth/refresh can read it without the JS layer ever
  // handling the refresh token itself.
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

function isAuthEndpoint(url?: string): boolean {
  return Boolean(url && url.startsWith("/api/v1/auth/"));
}

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  try {
    // A raw axios.post, not apiClient, so this call never re-enters the
    // response interceptor below (would otherwise risk a refresh loop).
    const response = await axios.post<TokenResponse>(
      `${API_URL}/api/v1/auth/refresh`,
      {},
      { withCredentials: true },
    );
    useAuthStore.getState().setAuth(response.data.access_token);
    return response.data.access_token;
  } catch {
    useAuthStore.getState().clearAuth();
    return null;
  }
}

export async function bootstrapSession(): Promise<void> {
  // Deliberately doesn't reuse refreshAccessToken(): that helper calls
  // setAuth() with no user as soon as the token comes back, which is fine
  // mid-session (isBootstrapping is already false and a user is already
  // in the store), but on a fresh page load there's no existing user for
  // setAuth's fallback to preserve — isBootstrapping would flip to false
  // with user still null, and the dashboard's auth gate would redirect to
  // /login before the /me fetch below ever gets a chance to run. So this
  // does both network calls first and only touches the store once, at
  // the very end, with token and user together.
  try {
    const refreshResponse = await axios.post<TokenResponse>(
      `${API_URL}/api/v1/auth/refresh`,
      {},
      { withCredentials: true },
    );
    const token = refreshResponse.data.access_token;
    const existingUser = useAuthStore.getState().user;
    const user =
      existingUser ??
      (
        await axios.get<User>(`${API_URL}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
      ).data;
    useAuthStore.getState().setAuth(token, user);
  } catch {
    useAuthStore.getState().clearAuth();
  }
}

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config as RetryableConfig | undefined;
    if (
      error.response?.status !== 401 ||
      !config ||
      config._retried ||
      isAuthEndpoint(config.url)
    ) {
      return Promise.reject(error);
    }

    config._retried = true;
    refreshInFlight ??= refreshAccessToken().finally(() => {
      refreshInFlight = null;
    });
    const token = await refreshInFlight;

    if (!token) {
      return Promise.reject(error);
    }
    config.headers.Authorization = `Bearer ${token}`;
    return apiClient(config);
  },
);

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const message = error.response?.data?.error?.message;
    if (typeof message === "string") {
      return message;
    }
  }
  return fallback;
}
