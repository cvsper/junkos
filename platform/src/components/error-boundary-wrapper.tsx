"use client";

import { ErrorBoundary } from "@/components/error-boundary";
import type { ReactNode } from "react";

export function ErrorBoundaryWrapper({ children }: { children: ReactNode }) {
  return <ErrorBoundary>{children}</ErrorBoundary>;
}
