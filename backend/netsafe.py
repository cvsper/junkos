"""SSRF-safe outbound fetch (audit F22).

``safe_fetch(url, max_bytes)`` is the ONLY sanctioned way to download a
user-supplied URL (quote photo conversion, operator document verification).

Guarantees:
- http(s) only, hostname required, no credentials in the URL
- every DNS answer for the host is checked against the blocked ranges
  (loopback, RFC1918, link-local / cloud metadata, CGNAT, ULA, multicast,
  unspecified) before a connection is opened
- redirects are followed by hand (max 3) and each hop is re-validated
- the body is streamed with a hard byte cap and a connect/read timeout

DNS-rebinding between resolve and connect is not fully closed here (that
needs a pinned-IP transport); the window is small and the metadata/RFC1918
classes that matter most are rejected on every hop.
"""

import ipaddress
import socket
from urllib.parse import urlparse, urljoin

import requests

__all__ = ["safe_fetch", "UnsafeURLError", "is_safe_url"]

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_TIMEOUT = (5, 15)  # (connect, read) seconds
MAX_REDIRECTS = 3

_BLOCKED_NETWORKS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8",          # "this" network / unspecified
    "10.0.0.0/8",
    "100.64.0.0/10",      # CGNAT
    "127.0.0.0/8",
    "169.254.0.0/16",     # link-local + cloud metadata (169.254.169.254)
    "172.16.0.0/12",
    "192.0.0.0/24",
    "192.168.0.0/16",
    "198.18.0.0/15",      # benchmarking
    "224.0.0.0/4",        # multicast
    "240.0.0.0/4",        # reserved + broadcast
    "::/128",
    "::1/128",
    "::ffff:0:0/96",      # IPv4-mapped — checked via the mapped v4 below too
    "64:ff9b::/96",       # NAT64
    "fc00::/7",           # ULA
    "fe80::/10",          # link-local
    "ff00::/8",           # multicast
)]


class UnsafeURLError(ValueError):
    """Raised when a URL (or one of its redirect hops) fails validation."""


def _ip_blocked(ip):
    addr = ipaddress.ip_address(ip)
    # Unwrap IPv4-mapped IPv6 so ::ffff:10.0.0.1 is judged as 10.0.0.1
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped
    if addr.is_private or addr.is_loopback or addr.is_link_local \
            or addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return True
    return any(addr in net for net in _BLOCKED_NETWORKS)


def _resolve_all(host, port):
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError("DNS resolution failed for {!r}".format(host)) from exc
    ips = {info[4][0] for info in infos}
    if not ips:
        raise UnsafeURLError("no addresses for {!r}".format(host))
    return ips


def validate_url(url):
    """Return the parsed URL if it is fetchable, else raise UnsafeURLError."""
    if not isinstance(url, str) or len(url) > 2048:
        raise UnsafeURLError("url must be a string of at most 2048 chars")
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("only http(s) URLs are allowed")
    if not parsed.hostname:
        raise UnsafeURLError("url has no host")
    if parsed.username or parsed.password:
        raise UnsafeURLError("credentials in url are not allowed")
    host = parsed.hostname
    if host.lower() in ("localhost",) or host.endswith(".localhost") \
            or host.endswith(".local") or host.endswith(".internal"):
        raise UnsafeURLError("internal hostnames are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    # Literal IPs are validated directly; names via every DNS answer.
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
        ips = {str(literal)}
    except ValueError:
        ips = _resolve_all(host, port)
    for ip in ips:
        if _ip_blocked(ip):
            raise UnsafeURLError("destination {} is not a public address".format(ip))
    return parsed


def is_safe_url(url):
    try:
        validate_url(url)
        return True
    except UnsafeURLError:
        return False


def safe_fetch(url, max_bytes=DEFAULT_MAX_BYTES, timeout=DEFAULT_TIMEOUT,
               max_redirects=MAX_REDIRECTS, headers=None):
    """Fetch ``url`` safely. Returns ``(content_bytes, content_type)``.

    Raises ``UnsafeURLError`` for a blocked destination / bad scheme / too
    many redirects / oversized body, and ``requests.RequestException`` for
    transport errors.
    """
    hdrs = {"User-Agent": "umuve-fetch/1.0", "Accept": "*/*"}
    if headers:
        hdrs.update(headers)

    current = url
    for _hop in range(max_redirects + 1):
        validate_url(current)
        resp = requests.get(current, headers=hdrs, timeout=timeout,
                            stream=True, allow_redirects=False)
        try:
            if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    raise UnsafeURLError("redirect without Location")
                current = urljoin(current, location)
                continue
            resp.raise_for_status()
            declared = resp.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise UnsafeURLError("response exceeds {} bytes".format(max_bytes))
            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise UnsafeURLError("response exceeds {} bytes".format(max_bytes))
                chunks.append(chunk)
            content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            return b"".join(chunks), content_type
        finally:
            resp.close()
    raise UnsafeURLError("too many redirects (>{})".format(max_redirects))
