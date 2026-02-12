"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { initPostHog, posthog } from "@/lib/posthog";

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  useEffect(() => {
    initPostHog();
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined" && posthog?.capture) {
      posthog.capture("$pageview", { path: pathname });
    }
  }, [pathname]);

  return <>{children}</>;
}
