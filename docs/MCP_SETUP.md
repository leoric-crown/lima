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

**Documentation & Reference:**
- `search_nodes` - Search 543+ n8n nodes from n8n-nodes-base and @n8n/n8n-nodes-langchain
- `get_node` - Get detailed node properties, operations, and configuration schemas
- `search_documentation` - Search official n8n documentation (87% coverage including AI nodes)
- `search_templates` - Browse 2,709 workflow templates with metadata
- `get_template` - Get complete template configurations from 2,646 pre-extracted workflows

**Workflow Management** (requires `N8N_API_KEY`):
- `n8n_list_workflows` - List all workflows in your n8n instance
- `n8n_get_workflow` - Get workflow details by ID
- `n8n_create_workflow` - Create new workflows programmatically
- `n8n_update_workflow` - Modify existing workflow configurations
- `n8n_execute_workflow` - Run workflows and retrieve results

### postgres-mcp

**Schema Exploration:**
- `list_schemas` - List all database schemas
- `list_objects` - List tables, views, sequences, extensions in a schema
- `get_object_details` - Get columns, constraints, indexes for an object

**Query Execution:**
- `execute_sql` - Run SQL statements (read-only in restricted mode)
- `explain_query` - Generate execution plans, simulate hypothetical indexes

**Performance Analysis:**
- `get_top_queries` - Report slowest queries via `pg_stat_statements`
- `analyze_workload_indexes` - Identify resource-intensive queries, recommend indexes
- `analyze_query_indexes` - Analyze specific queries and recommend optimal indexes
- `analyze_db_health` - Health checks: buffer cache, connections, constraints, indexes, vacuum status
