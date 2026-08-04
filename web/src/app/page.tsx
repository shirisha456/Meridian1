"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuthStore } from "@/lib/auth-store";

export default function Home() {
  const router = useRouter();
  const { isBootstrapping, user } = useAuthStore();

  useEffect(() => {
    if (isBootstrapping) return;
    router.replace(user ? "/dashboard" : "/login");
  }, [isBootstrapping, user, router]);

  return null;
}
