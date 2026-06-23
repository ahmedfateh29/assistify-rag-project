"use client";

import { useMemo } from "react";
import { useProfile } from "@/src/hooks/useProfile";
import { homePathForRole, sideLinksForRole, topLinksForRole } from "@/src/lib/navigation";

export function useRoleNav() {
  const { profile } = useProfile();
  const role = profile?.role ?? "customer";

  return useMemo(
    () => ({
      role,
      homeHref: homePathForRole(role),
      topLinks: topLinksForRole(role),
      sideLinks: sideLinksForRole(role),
    }),
    [role],
  );
}
