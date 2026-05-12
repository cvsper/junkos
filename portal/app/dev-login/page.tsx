"use client";
import { useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";

function DevLoginInner() {
  const router = useRouter();
  const search = useSearchParams();
  useEffect(() => {
    const token = search.get("t");
    const org = search.get("o");
    const role = search.get("r") || "owner";
    if (token && org) {
      localStorage.setItem("umuve_portal_token", token);
      localStorage.setItem("umuve_portal_org", org);
      localStorage.setItem("umuve_portal_role", role);
      router.replace("/");
    }
  }, [search, router]);
  return <div className="p-8 text-gray-500">Logging in…</div>;
}

export default function DevLogin() {
  return <Suspense><DevLoginInner /></Suspense>;
}
