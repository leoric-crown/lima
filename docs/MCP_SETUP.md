# LIMA MCP Server Setup

## Available MCP Servers

| Server | URL | Transport | Source |
|--------|-----|-----------|--------|
| **n8n-mcp** | `http://localhost:8042/mcp` | HTTP | [czlonkowski/n8n-mcp](https://github.com/czlonkowski/n8n-mcp) |
| **postgres-mcp** | `http://localhost:8700/sse` | SSE | [crystaldba/postgres-mcp](https://github.com/crystaldba/postgres-mcp) |

## Claude Code CLI Setup

```bash
# Load environment variables
cd /path/to/lima
source .env

# Add n8n-mcp (workflow development)
claude mcp add-json lima-n8n \
  '{"type":"http","url":"http://localhost:8042/mcp","headers":{"Authorization":"Bearer '"$MCP_AUTH_TOKEN"'"}}'

# Add postgres-mcp (database access)
claude mcp add --transport sse lima-postgres http://localhost:8700/sse
```

## Raw JSON (General MCP Clients)

### n8n-mcp

```json
{
  "type": "http",
  "url": "http://localhost:8042/mcp",
  "headers": {
    "Authorization": "Bearer YOUR_MCP_AUTH_TOKEN"
  }
}
```

### postgres-mcp

```json
{
  "type": "sse",
  "url": "http://localhost:8700/sse"
}
```

## Verification

```bash
# Test n8n-mcp
curl http://localhost:8042/health

# Test postgres-mcp
curl http://localhost:8700/sse
```

## Tools Provided

### n8n-mcp
- Workflow management (list, create, update, execute)
- Node documentation lookup
- Workflow validation

### postgres-mcp
- SQL query execution
- Schema exploration
- Query explain plans
- Index analysis
