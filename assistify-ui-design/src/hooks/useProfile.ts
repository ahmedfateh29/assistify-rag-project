"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/src/lib/apiClient";
import { exitUrlForRole } from "@/src/lib/navigation";
import type { UserProfile } from "@/src/lib/types";

export function useProfile() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<UserProfile>("/api/my-profile");
      setProfile(data);
    } catch (err) {
      setProfile(null);
      setError(err instanceof Error ? err : new Error("Failed to load profile"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  const exitUrl = profile ? exitUrlForRole(profile.role) : "/";

  return { profile, isLoading, error, exitUrl, refresh };
}
