# MCP Integration (Plug-and-Play for AI Clients)

This project exposes a Model Context Protocol (MCP) server so LLM clients can interact
with Umuve APIs through structured tools.

## Quick Start

1. Install Python dependencies:

```bash
cd backend
pip install -r requirements.txt
```

2. Export API credentials (required):

```bash
export PROXO_MCP_API_KEY="your-api-key"
```

3. Start MCP (stdio):

```bash
cd backend
bash scripts/run-mcp.sh
```

That starts an MCP server using stdio and points to `http://127.0.0.1:5000/api` by default.

## Configure Clients

### Claude Desktop

```json
{
  "mcpServers": {
    "proxo": {
      "command": "bash",
      "args": ["-lc", "cd /absolute/path/to/backend && PROXO_MCP_API_KEY=... bash scripts/run-mcp.sh"]
    }
  }
}
```

### Cursor / MCP Host (stdio)

```json
{
  "mcpServers": [
    {
      "name": "proxo",
      "type": "stdio",
      "command": "bash",
      "args": [
        "-lc",
        "cd /absolute/path/to/backend && PROXO_MCP_API_KEY=... bash scripts/run-mcp.sh"
      ]
    }
  ]
}
```

## Run over HTTP (optional)

```bash
PROXO_MCP_TRANSPORT=streamable-http \
PROXO_MCP_HOST=127.0.0.1 \
PROXO_MCP_PORT=9000 \
bash scripts/run-mcp.sh
```

Then expose MCP at:
- `http://127.0.0.1:9000/mcp`

## Runtime Settings

- `PROXO_MCP_API_URL` (default: `http://127.0.0.1:5000`)
- `PROXO_MCP_MOUNT_PATH` (default: `/api`)
- `PROXO_MCP_TENANT_ID` (optional)
- `PROXO_MCP_API_TIMEOUT_SECONDS` (default: `30`)
- `PROXO_MCP_TRANSPORT` (`stdio` | `streamable-http`, default: `stdio`)
- `PROXO_MCP_HOST` (default: `127.0.0.1`, HTTP only)
- `PROXO_MCP_PORT` (default: `9000`, HTTP only)
- `PROXO_MCP_HTTP_MOUNT_PATH` (default: `/mcp`, HTTP only)

## MCP Tools

- `proxo_health_check`
- `proxo_list_services`
- `proxo_get_booking`
- `proxo_request_quote`
- `proxo_create_booking`
- `proxo_list_available_slots`
- `proxo_invoke_api` (generic endpoint tool)
