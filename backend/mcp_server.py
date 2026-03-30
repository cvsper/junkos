"""
Model Context Protocol (MCP) server for Umuve endpoints.

The server intentionally exposes a narrow set of first-class tools plus a generic
API proxy tool so new endpoints can be used immediately without a full schema change.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Dict, List, Literal, Optional, Tuple

import httpx
from mcp.server.fastmcp import FastMCP
from urllib.parse import urlparse

HTTPMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]

API_BASE_URL = os.getenv("PROXO_MCP_API_URL", "http://127.0.0.1:5000").rstrip("/")
API_MOUNT_PATH = os.getenv("PROXO_MCP_MOUNT_PATH", "/api").strip("/")
API_KEY = os.getenv("PROXO_MCP_API_KEY", "").strip()
TENANT_ID = os.getenv("PROXO_MCP_TENANT_ID", "").strip()
REQUEST_TIMEOUT_SECONDS = os.getenv("PROXO_MCP_API_TIMEOUT_SECONDS", "30").strip() or "30"

mcp = FastMCP("proxo_mcp")


def _format_json(value: Any) -> str:
    return json.dumps(value, indent=2, default=str, sort_keys=True)


def _emit_boot_log(event: str, level: str = "info", **payload: Any) -> None:
    message = {"event": event, "level": level, **payload}
    print(json.dumps(message, sort_keys=True), file=sys.stderr)


def _coerce_transport() -> str:
    return os.getenv("PROXO_MCP_TRANSPORT", "stdio").strip().lower()


def _coerce_timeout_seconds() -> float:
    try:
        timeout = float(REQUEST_TIMEOUT_SECONDS)
    except ValueError as exc:
        raise ValueError("PROXO_MCP_API_TIMEOUT_SECONDS must be numeric (for example: 30)") from exc

    if timeout <= 0:
        raise ValueError("PROXO_MCP_API_TIMEOUT_SECONDS must be greater than 0.")

    return timeout


def _coerce_positive_int(value: str, name: str, *, min_value: int = 1, max_value: Optional[int] = None) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc

    if parsed < min_value:
        raise ValueError(f"{name} must be >= {min_value}.")

    if max_value is not None and parsed > max_value:
        raise ValueError(f"{name} must be <= {max_value}.")

    return parsed


def _normalize_mount_path(raw: str) -> str:
    normalized = raw.strip()
    if not normalized:
        return ""
    return normalized.strip("/")


def _startup_smoke_attempts() -> int:
    return _coerce_positive_int(
        os.getenv("PROXO_MCP_STARTUP_SMOKE_ATTEMPTS", "2"),
        "PROXO_MCP_STARTUP_SMOKE_ATTEMPTS",
        min_value=0,
    )


def _to_bool(value: str, default: bool = False) -> bool:
    raw = value.strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "enabled"}


def _base_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "proxo-mcp/1.0",
    }
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    if TENANT_ID:
        headers["X-Tenant-ID"] = TENANT_ID
    return headers


def _build_url(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path is required")
    if path.startswith("http://") or path.startswith("https://"):
        raise ValueError("Only API-relative paths are allowed (for example: /services).")

    rel_path = path.lstrip("/")
    base = API_BASE_URL
    if API_MOUNT_PATH:
        if rel_path:
            return f"{base}/{API_MOUNT_PATH}/{rel_path}"
        return f"{base}/{API_MOUNT_PATH}"
    return f"{base}/{rel_path}" if rel_path else base


def _dependency_checks() -> List[str]:
    errors: List[str] = []
    for package in ("httpx", "mcp"):
        try:
            version(package)
        except PackageNotFoundError:
            errors.append(f"Missing Python package `{package}`. Run `pip install -r requirements.txt`.")
    return errors


def _build_error_details(error: Exception) -> Dict[str, Any]:
    if isinstance(error, httpx.TimeoutException):
        return {
            "error_type": "timeout",
            "message": str(error),
            "hint": "Increase PROXO_MCP_API_TIMEOUT_SECONDS or check API responsiveness.",
        }
    if isinstance(error, httpx.ConnectError):
        return {
            "error_type": "connection_failed",
            "message": str(error),
            "hint": "Check PROXO_MCP_API_URL and backend reachability.",
        }
    if isinstance(error, httpx.HTTPStatusError):
        return {
            "error_type": "http_status",
            "status_code": error.response.status_code,
            "body": error.response.text[:500],
            "message": str(error),
            "hint": "Verify API credentials, method, and endpoint path.",
        }
    return {
        "error_type": error.__class__.__name__,
        "message": str(error),
    }


def _tool_error(message: str, error: Exception) -> str:
    return _format_json(_error_payload(message, _build_error_details(error)))


def _validation_errors() -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not API_KEY:
        errors.append("PROXO_MCP_API_KEY is required and cannot be empty.")

    if not API_BASE_URL:
        errors.append("PROXO_MCP_API_URL is required and cannot be empty.")
    else:
        parsed = urlparse(API_BASE_URL)
        if parsed.scheme not in {"http", "https"}:
            errors.append("PROXO_MCP_API_URL must include http:// or https://.")
        if not parsed.netloc:
            errors.append("PROXO_MCP_API_URL must include a host value.")

    if " " in API_MOUNT_PATH:
        errors.append("PROXO_MCP_MOUNT_PATH cannot contain spaces.")

    try:
        _coerce_timeout_seconds()
    except ValueError as exc:
        errors.append(str(exc))

    if _normalize_mount_path(API_MOUNT_PATH) == "":
        warnings.append("PROXO_MCP_MOUNT_PATH is empty; API calls will target base URL directly.")

    transport = _coerce_transport()
    if transport not in {"stdio", "streamable-http"}:
        errors.append("PROXO_MCP_TRANSPORT must be `stdio` or `streamable-http`.")
    elif transport == "streamable-http":
        host = os.getenv("PROXO_MCP_HOST", "127.0.0.1").strip()
        if not host:
            errors.append("PROXO_MCP_HOST must not be empty for streamable-http transport.")

    try:
        _coerce_positive_int(os.getenv("PROXO_MCP_PORT", "9000"), "PROXO_MCP_PORT", max_value=65535)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        _startup_smoke_attempts()
    except ValueError as exc:
        errors.append(str(exc))

    errors.extend(_dependency_checks())
    return errors, warnings


async def _call_api(
    method: HTTPMethod,
    path: str,
    query: Optional[Dict[str, Any]] = None,
    body: Optional[Any] = None,
    custom_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    url = _build_url(path)
    headers = _base_headers()
    if custom_headers:
        headers.update({str(k): str(v) for k, v in custom_headers.items() if k and v is not None})

    async with httpx.AsyncClient(timeout=_coerce_timeout_seconds()) as client:
        response = await client.request(
            method=method,
            url=url,
            params=query,
            json=body,
            headers=headers,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            payload = response.json()
        else:
            payload = {"text": response.text}

        return {
            "ok": True,
            "status_code": response.status_code,
            "url": str(response.url),
            "headers": {
                "content-type": response.headers.get("content-type"),
                "server": response.headers.get("server"),
            },
            "payload": payload,
        }


def _error_payload(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "ok": False,
        "error": message,
        "details": details or {},
    }


async def _startup_smoke_check() -> Dict[str, Any]:
    try:
        response = await _call_api("GET", "/health")
        return {
            "ok": True,
            "status_code": response["status_code"],
            "url": response["url"],
            "payload": response["payload"],
        }
    except Exception as exc:
        details = _build_error_details(exc)
        return {
            "ok": False,
            "error": str(exc),
            "details": details,
        }


def _log_startup_snapshot() -> None:
    normalized_mount = _normalize_mount_path(API_MOUNT_PATH)
    _emit_boot_log(
        "startup.config",
        level="info",
        api_base_url=API_BASE_URL,
        api_mount_path=normalized_mount,
        transport=_coerce_transport(),
        request_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        has_api_key=bool(API_KEY),
        has_tenant_id=bool(TENANT_ID),
    )


def _run_startup_checks() -> bool:
    errors, warnings = _validation_errors()
    _log_startup_snapshot()

    for warning in warnings:
        _emit_boot_log("startup.warning", level="warning", message=warning)

    if errors:
        _emit_boot_log("startup.validation_failed", level="error", errors=errors)
        return False

    _emit_boot_log("startup.validation_ok", level="info")
    return True


async def _run_smoke_sequence() -> bool:
    attempts = _startup_smoke_attempts()
    if attempts == 0:
        _emit_boot_log("startup.smoke_skipped", level="info", reason="PROXO_MCP_STARTUP_SMOKE_ATTEMPTS=0")
        return True

    last: Dict[str, Any] = {"ok": False, "error": "not run"}
    for attempt in range(1, attempts + 1):
        result = await _startup_smoke_check()
        last = result
        if result["ok"]:
            _emit_boot_log(
                "startup.smoke_ok",
                level="info",
                attempt=attempt,
                url=result.get("url"),
                status_code=result.get("status_code"),
            )
            return True

        _emit_boot_log(
            "startup.smoke_failed",
            level="warning",
            attempt=attempt,
            attempts=attempts,
            error=result.get("error"),
            details=result.get("details"),
        )

        if attempt < attempts:
            await asyncio.sleep(1)

    if _to_bool(os.getenv("PROXO_MCP_SMOKE_FAIL_FAST", "0")):
        _emit_boot_log("startup.smoke_abort", level="error", reason="startup smoke check failed and PROXO_MCP_SMOKE_FAIL_FAST is enabled")
        return False

    return bool(last.get("ok"))


@mcp.tool(name="proxo_health_check", annotations={"readOnlyHint": True, "idempotentHint": True})
def proxo_health_check() -> str:
    """Check API health without mutating any state."""
    return _format_json({
        "service": "proxo_mcp",
        "api_base": f"{API_BASE_URL}/{API_MOUNT_PATH}".rstrip("/"),
        "transport": os.getenv("PROXO_MCP_TRANSPORT", "stdio"),
        "has_api_key": bool(API_KEY),
    })


@mcp.tool(name="proxo_list_services", annotations={"readOnlyHint": True, "idempotentHint": True})
async def proxo_list_services() -> str:
    """List available service offerings from the platform."""
    try:
        response = await _call_api("GET", "/services")
        return _format_json(response)
    except Exception as exc:
        return _tool_error("Error fetching services.", exc)


@mcp.tool(name="proxo_get_booking", annotations={"readOnlyHint": True, "idempotentHint": True})
async def proxo_get_booking(booking_id: int) -> str:
    """Get a booking by ID."""
    try:
        response = await _call_api("GET", f"/bookings/{booking_id}")
        return _format_json(response)
    except Exception as exc:
        return _tool_error(f"Error fetching booking {booking_id}.", exc)


@mcp.tool(name="proxo_request_quote", annotations={"readOnlyHint": True, "idempotentHint": True})
async def proxo_request_quote(
    zip_code: str,
    service_ids: List[int],
    notes: Optional[str] = None,
) -> str:
    """Get a price estimate for selected service IDs."""
    payload: Dict[str, Any] = {"zip_code": zip_code, "services": service_ids}
    if notes:
        payload["notes"] = notes
    try:
        response = await _call_api("POST", "/quote", body=payload)
        return _format_json(response)
    except Exception as exc:
        return _tool_error("Error requesting quote.", exc)


@mcp.tool(name="proxo_create_booking", annotations={"destructiveHint": True, "idempotentHint": False})
async def proxo_create_booking(
    address: str,
    services: List[int],
    scheduled_datetime: str,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    zip_code: Optional[str] = None,
    photos: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> str:
    """Create a booking using the compatibility /bookings endpoint."""
    payload: Dict[str, Any] = {
        "address": address,
        "services": services,
        "scheduled_datetime": scheduled_datetime,
        "customer": {
            "name": customer_name,
            "email": customer_email,
            "phone": customer_phone,
        },
    }
    if zip_code:
        payload["zip_code"] = zip_code
    if photos:
        payload["photos"] = photos
    if notes:
        payload["notes"] = notes
    try:
        response = await _call_api("POST", "/bookings", body=payload)
        return _format_json(response)
    except Exception as exc:
        return _tool_error("Error creating booking.", exc)


@mcp.tool(name="proxo_list_available_slots", annotations={"readOnlyHint": True, "idempotentHint": True})
async def proxo_list_available_slots(date: Optional[str] = None) -> str:
    """Fetch available booking slots for a date (YYYY-MM-DD)."""
    query = {"date": date} if date else None
    try:
        response = await _call_api("GET", "/bookings/available-slots", query=query)
        return _format_json(response)
    except Exception as exc:
        return _tool_error("Error fetching available slots.", exc)


@mcp.tool(name="proxo_invoke_api", annotations={"openWorldHint": True})
async def proxo_invoke_api(
    method: HTTPMethod,
    path: str,
    query: Optional[Dict[str, Any]] = None,
    body: Optional[Any] = None,
    custom_headers: Optional[Dict[str, str]] = None,
) -> str:
    """
    Invoke any API path on the configured backend.

    Use this for endpoints not covered by first-class tools.
    """
    try:
        response = await _call_api(method, path, query=query, body=body, custom_headers=custom_headers)
        return _format_json(response)
    except Exception as exc:
        return _tool_error(f"Error invoking {method} {path}.", exc)


if __name__ == "__main__":
    if not _run_startup_checks():
        raise SystemExit(2)

    if _startup_smoke_attempts() > 0:
        smoke_ok = asyncio.run(_run_smoke_sequence())
        if not smoke_ok and _to_bool(os.getenv("PROXO_MCP_SMOKE_FAIL_FAST", "0")):
            raise SystemExit(3)

    transport = _coerce_transport()
    if transport == "streamable-http":
        host = os.getenv("PROXO_MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
        port = _coerce_positive_int(os.getenv("PROXO_MCP_PORT", "9000"), "PROXO_MCP_PORT", max_value=65535)
        mount = os.getenv("PROXO_MCP_HTTP_MOUNT_PATH", "/mcp").strip() or "/mcp"
        if not mount.startswith("/"):
            mount = f"/{mount}"
        _emit_boot_log("startup.run", level="info", transport="streamable-http", host=host, port=port, mount=mount)
        mcp.run(transport="streamable-http", host=host, port=port, path=mount)
    else:
        _emit_boot_log("startup.run", level="info", transport="stdio")
        mcp.run(transport="stdio")
