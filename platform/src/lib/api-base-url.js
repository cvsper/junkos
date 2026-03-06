function isLocalHostname(hostname) {
  return (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1"
  );
}

export function resolveApiBaseUrl(options = {}) {
  const envUrl =
    options.envUrl ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5001";
  const hostname =
    options.hostname ??
    (typeof window !== "undefined" ? window.location.hostname : undefined);

  if (hostname && isLocalHostname(hostname) && /^https?:\/\//.test(envUrl)) {
    return "/api-proxy";
  }

  return envUrl;
}
