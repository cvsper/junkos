#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${PROXO_MCP_API_KEY:-}" ]]; then
  echo "Missing required env: PROXO_MCP_API_KEY"
  echo "Set it before starting MCP (or use a read-only API key)."
  exit 1
fi

export PROXO_MCP_API_URL="${PROXO_MCP_API_URL:-http://127.0.0.1:5000}"
export PROXO_MCP_MOUNT_PATH="${PROXO_MCP_MOUNT_PATH:-/api}"
export PROXO_MCP_TRANSPORT="${PROXO_MCP_TRANSPORT:-stdio}"
export PROXO_MCP_API_TIMEOUT_SECONDS="${PROXO_MCP_API_TIMEOUT_SECONDS:-30}"
export PROXO_MCP_HTTP_MOUNT_PATH="${PROXO_MCP_HTTP_MOUNT_PATH:-/mcp}"

echo "Starting Proxo MCP server"
echo " - API base: ${PROXO_MCP_API_URL}"
echo " - API mount: ${PROXO_MCP_MOUNT_PATH}"
echo " - Transport: ${PROXO_MCP_TRANSPORT}"

if [[ "${PROXO_MCP_TRANSPORT}" == "streamable-http" ]]; then
  echo " - MCP mount: ${PROXO_MCP_HTTP_MOUNT_PATH:-/mcp}"
  echo " - Host: ${PROXO_MCP_HOST:-127.0.0.1}"
  echo " - Port: ${PROXO_MCP_PORT:-9000}"
fi

python3 mcp_server.py
