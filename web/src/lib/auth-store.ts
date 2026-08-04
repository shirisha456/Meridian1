import { create } from "zustand";

import type { User } from "@/lib/types";

interface AuthState {
  // In memory only, never persisted (localStorage/sessionStorage) — an
  // access token there would be readable by any XSS payload. The refresh
  // token is an httpOnly cookie the JS layer never touches at all.
  accessToken: string | null;
  user: User | null;
  isBootstrapping: boolean;
  setAuth: (token: string, user?: User) => void;
  setBootstrapped: () => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  user: null,
  isBootstrapping: true,
  // user is optional here deliberately: POST /auth/refresh returns only
  // {access_token, token_type}, no user. Keep the existing user in the
  // store rather than overwriting it with undefined on every silent
  // refresh (see api-client.ts).
  setAuth: (token, user) => set({ accessToken: token, user: user ?? get().user, isBootstrapping: false }),
  setBootstrapped: () => set({ isBootstrapping: false }),
  clearAuth: () => set({ accessToken: null, user: null, isBootstrapping: false }),
}));
