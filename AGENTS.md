# Doormat MCP Server & Agent Integration

**Version**: 1.0  
**Created**: 2026-04-25  
**Status**: Reference Architecture  

---

## Overview

Doormat exposes a FastMCP server that allows external Claude agents to call Doormat capabilities. This enables third-party workflows like "find rentals for all my friends" or "compare listings across multiple cities."

**Use Cases**:
1. Claude Desktop integration: access Doormat from Claude conversation
2. External agents: trigger discovery + scoring programmatically
3. Multi-user federation: one Doormat instance shared via MCP across multiple users
4. Batch operations: orchestrate discovery/extraction/scoring for multiple cities

---

## Architecture

```
┌─────────────────────────────────┐
│     External Claude Agent       │
│  (Copilot, Claude Desktop, API) │
└────────────────┬────────────────┘
                 │
         MCP Protocol (stdio)
                 │
                 ▼
┌─────────────────────────────────┐
│    FastMCP Server (FastAPI)     │
│  - Discovery endpoint           │
│  - Extraction status endpoint   │
│  - Scoring endpoint             │
│  - Listing query endpoint       │
│  - Metrics/cost endpoint        │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Doormat Backend (Python)       │
│  - LLM agents                   │
│  - SQLite database              │
│  - Cost tracking                │
└─────────────────────────────────┘
```

---

## MCP Server Specification

### 1. Tools Exposed

The MCP server exposes 6 core tools:

#### 1.1 `discover_city`
Trigger property manager discovery for a new city.

**Input**:
```json
{
  "city": "string (required)",      // City name: "San Francisco"
  "state": "string (required)",     // State abbrev: "CA"
  "force_refresh": "boolean (optional, default: false)" // Bypass cache
}
```

**Output**:
```json
{
  "status": "discovering|completed|failed",
  "city": "San Francisco",
  "state": "CA",
  "managers_found": 32,
  "cache_hit": false,
  "timestamp": "2026-04-25T10:30:00Z",
  "cost_usd": 0.032,
  "execution_time_seconds": 120,
  "sample_managers": [
    {
      "name": "Downtown Properties LLC",
      "website": "https://downtowtownproperties.com",
      "listing_page_url": "https://downtowtownproperties.com/available",
      "confidence": 0.95
    }
  ]
}
```

**MCP Tool Definition**:
```json
{
  "name": "discover_city",
  "description": "Autonomously discover property managers in a US city",
  "inputSchema": {
    "type": "object",
    "properties": {
      "city": {"type": "string"},
      "state": {"type": "string", "pattern": "[A-Z]{2}"},
      "force_refresh": {"type": "boolean"}
    },
    "required": ["city", "state"]
  }
}
```

**Example Call**:
```python
discovery_result = await mcp.call_tool("discover_city", {
  "city": "San Francisco",
  "state": "CA"
})
```

---

#### 1.2 `create_preference`
Create or update a rental preference profile.

**Input**:
```json
{
  "description": "string (required)",  // "Modern 2-bed under $3500, walkable, pet-friendly"
  "city": "string (required)",         // "San Francisco"
  "user_id": "string (optional)"       // For multi-user MCP scenarios
}
```

**Output**:
```json
{
  "preference_id": "pref_sf_alice_001",
  "description": "Modern 2-bed under $3500, walkable, pet-friendly",
  "city": "San Francisco",
  "created_at": "2026-04-25T10:30:00Z"
}
```

---

#### 1.3 `trigger_extraction`
Trigger listing extraction for a specific property manager.

**Input**:
```json
{
  "property_manager_id": "string (required)",  // From discovery result
  "strategy_id": "string (optional)",          // Use cached strategy if known
  "batch_size": "integer (optional, default: 100)"
}
```

**Output**:
```json
{
  "status": "extracting|completed|failed",
  "property_manager_id": "pm_downtown_sf",
  "listings_extracted": 245,
  "listings_validated": 210,
  "validation_rate": 0.86,
  "cost_usd": 0.052,
  "execution_time_seconds": 180,
  "failed_listings": [
    {
      "url": "https://...",
      "reason": "Missing price field"
    }
  ]
}
```

---

#### 1.4 `score_listings`
Score listings against a preference profile.

**Input**:
```json
{
  "preference_id": "string (required)",
  "city": "string (required)",
  "limit": "integer (optional, default: 10)",
  "min_score": "integer (optional, default: 60)",
  "format": "string (optional, enum: ['json', 'text'])"
}
```

**Output**:
```json
{
  "preference_id": "pref_sf_alice_001",
  "city": "San Francisco",
  "total_listings": 1250,
  "filtered_by_score": 89,
  "top_matches": [
    {
      "address": "123 Main St, SF, CA",
      "bedrooms": 2,
      "price": 3200,
      "url": "https://...",
      "match_score": 94,
      "reasoning": "Excellent match: price under budget, walkable neighborhood, modern finishes"
    },
    {
      "address": "456 Valencia, SF, CA",
      "bedrooms": 2,
      "price": 3400,
      "url": "https://...",
      "match_score": 88,
      "reasoning": "Great match: matches budget, pet-friendly, good walkability"
    }
  ],
  "cost_usd": 0.018,
  "execution_time_seconds": 45
}
```

---

#### 1.5 `get_listings`
Query listings with filters and pagination.

**Input**:
```json
{
  "city": "string (required)",
  "preference_id": "string (optional)",
  "min_price": "integer (optional)",
  "max_price": "integer (optional)",
  "bedrooms": "integer (optional)",
  "limit": "integer (optional, default: 20, max: 100)",
  "offset": "integer (optional, default: 0)"
}
```

**Output**:
```json
{
  "city": "San Francisco",
  "total_count": 1250,
  "returned_count": 20,
  "offset": 0,
  "listings": [
    {
      "id": "listing_123",
      "address": "123 Main St",
      "bedrooms": 2,
      "bathrooms": 1,
      "price": 3200,
      "url": "https://...",
      "property_manager": "Downtown Properties LLC",
      "extraction_timestamp": "2026-04-25T09:15:00Z"
    }
  ]
}
```

---

#### 1.6 `get_metrics`
Fetch cost and performance metrics.

**Input**:
```json
{
  "metric": "string (enum: ['cost_total', 'cost_by_component', 'cost_by_city', 'performance'])",
  "time_window": "string (optional, enum: ['1h', '24h', '7d', '30d', 'all'])",
  "city": "string (optional, for filtering)"
}
```

**Output**:
```json
{
  "metric": "cost_by_component",
  "time_window": "30d",
  "data": {
    "discovery": {
      "calls": 5,
      "cost_usd": 0.15,
      "avg_cost_per_city": 0.03
    },
    "extraction": {
      "calls": 1250,
      "cost_usd": 0.45,
      "avg_cost_per_listing": 0.00036
    },
    "scoring": {
      "calls": 340,
      "cost_usd": 0.68,
      "avg_cost_per_listing": 0.002
    }
  },
  "total_cost_usd": 1.28,
  "cache_hit_rate": 0.38
}
```

---

### 2. Resource Types

MCP also exposes resource types for read-only access:

#### 2.1 City Resource
```
doormat://city/{city}/{state}
```

Returns discovered property managers for a city.

#### 2.2 Listing Resource
```
doormat://listing/{listing_id}
```

Returns full listing detail (with extraction metadata, scores, cost).

#### 2.3 Preference Resource
```
doormat://preference/{preference_id}
```

Returns preference profile with scoring results.

---

### 3. Sampling Pattern (for streaming large results)

Some MCP calls may return large result sets. Use sampling:

```json
{
  "method": "get_listings",
  "params": {
    "city": "San Francisco",
    "limit": 100,
    "sampling": {
      "enabled": true,
      "sample_rate": 0.1,  // Return 10% of results
      "deterministic": true
    }
  }
}
```

---

## FastMCP Implementation

### Server Definition (`src/backend/doormat/mcp_server.py`)

```python
from fastmcp import FastMCP
from pydantic import BaseModel

mcp = FastMCP(name="doormat", version="1.0")

@mcp.tool()
async def discover_city(city: str, state: str, force_refresh: bool = False):
    """Autonomously discover property managers in a US city."""
    # Implementation...
    pass

@mcp.tool()
async def create_preference(description: str, city: str, user_id: str = None):
    """Create or update a rental preference profile."""
    # Implementation...
    pass

# ... other tools ...

@mcp.run()
async def main():
    """Start MCP server."""
    # Runs on stdio
    pass
```

### Startup in FastAPI Lifespan

```python
# src/backend/doormat/main.py
from contextlib import asynccontextmanager
from doormat.mcp_server import mcp

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await mcp.initialize()
    yield
    # Shutdown
    await mcp.shutdown()

app = FastAPI(lifespan=lifespan)
```

### Integration with External Agents

#### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "doormat": {
      "command": "python",
      "args": ["-m", "doormat.mcp_server"]
    }
  }
}
```

#### Copilot CLI / Zo Computer

```yaml
# skills/doormat-mcp/manifest.yaml
name: doormat
description: AI-first rental finder
mcp_server: doormat_mcp_server
tools:
  - discover_city
  - create_preference
  - trigger_extraction
  - score_listings
  - get_listings
  - get_metrics
```

---

## Agent Orchestration Patterns

### Pattern 1: Simple Discovery + Scoring

```
External Agent
    ↓
1. Call discover_city("San Francisco", "CA")
    ↓ (waits 2 min)
2. Call create_preference("2-bed under $3k")
    ↓
3. Call score_listings(preference_id, "San Francisco", limit=5)
    ↓
Return top 5 matches to user
```

### Pattern 2: Batch Multi-City

```
For each city in [San Francisco, Oakland, Berkeley]:
    1. discover_city(city)
    2. trigger_extraction(all property managers)
    3. score_listings(preference_id, city, limit=3)

Aggregate results across cities
Return combined top 20 matches
```

### Pattern 3: Conversational Refinement

```
1. User: "Find me rentals in SF"
   → create_preference("rentals in SF")
   
2. Agent scores 50 listings
   → User: "These are too expensive and far from downtown"
   
3. Agent refines preference: "SF, max $2500, walkable to downtown"
   → update preference
   → re-score all cached listings
   
4. Return refined results
```

---

## Error Handling & Retries

### Timeout Handling

MCP tools may take time (discovery = 2+ minutes). Handle gracefully:

```python
# In external agent
response = await mcp.call_tool("discover_city", params, timeout=300)
if response["status"] == "discovering":
    # Poll for completion
    while response["status"] != "completed":
        await asyncio.sleep(10)
        response = await mcp.get_task_status(task_id)
```

### Rate Limiting

External agents calling MCP tools are rate-limited:
- Discovery: 1 per minute (expensive)
- Extraction: 10 per minute
- Scoring: 100 per minute
- Queries: 1000 per minute

Response on limit exceeded:
```json
{
  "error": "rate_limit_exceeded",
  "retry_after_seconds": 60,
  "current_usage": "2/1 per minute",
  "upgrade_path": "self-host Doormat locally for unlimited access"
}
```

---

## Security & Authentication

### Default: No Auth (Localhost)

```python
# config.py
AUTH_MODE = "none"  # Default: localhost only
```

### Optional: Bearer Token (Self-Hosters)

For self-hosters exposing Doormat on a network:

```python
# config.py
AUTH_MODE = "bearer"  # Require token
BEARER_TOKEN = "sk-doormat-xxxxxx"
```

MCP calls must include header:
```
Authorization: Bearer sk-doormat-xxxxxx
```

### API Key Rotation

Rotate bearer tokens via:
```bash
doormat rotate-token
```

Old token revoked immediately; grace period = 60 seconds.

---

## Observability & Cost

### MCP Call Logging

Every MCP tool call is logged with:

```json
{
  "timestamp": "2026-04-25T10:30:00Z",
  "mcp_tool": "score_listings",
  "caller": "claude-desktop",
  "input_size_bytes": 156,
  "execution_time_ms": 2340,
  "cost_usd": 0.018,
  "status": "success"
}
```

### Metrics Endpoint (for monitoring)

```
GET /metrics
```

Includes MCP-specific metrics:
```
doormat_mcp_calls_total{tool="score_listings"}
doormat_mcp_latency_ms{tool="discover_city", quantile="p95"}
doormat_mcp_cost_usd{tool="extraction"}
```

---

## Testing & Validation

### MCP Server Unit Tests

```python
# tests/mcp/test_discover_city.py
async def test_discover_city():
    result = await mcp.discover_city("San Francisco", "CA")
    assert result["status"] in ["discovering", "completed"]
    assert len(result["sample_managers"]) > 0
    assert result["cost_usd"] > 0
```

### Integration Test: External Agent

```python
# tests/mcp/test_external_agent.py
async def test_claude_agent_via_mcp():
    """Simulate Claude Desktop calling Doormat MCP server."""
    async with MCPClient("doormat") as client:
        # Discover SF
        discovery = await client.call_tool("discover_city", {
            "city": "San Francisco",
            "state": "CA"
        })
        assert discovery["status"] == "completed"
        
        # Score listings
        pref = await client.call_tool("create_preference", {
            "description": "2-bed under $3k",
            "city": "San Francisco"
        })
        scores = await client.call_tool("score_listings", {
            "preference_id": pref["preference_id"],
            "city": "San Francisco"
        })
        assert len(scores["top_matches"]) > 0
```

---

## Deployment & Configuration

### Docker Compose (with MCP)

```yaml
# docker-compose.yml
services:
  doormat-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      MCP_ENABLED: "true"
      MCP_HOST: "0.0.0.0"
      MCP_PORT: "3001"
    volumes:
      - ./doormat.db:/app/doormat.db

  # Optional: MCP relay for Claude Desktop
  mcp-relay:
    image: doormat:latest
    command: python -m doormat.mcp_server
    environment:
      DOORMAT_API_URL: "http://doormat-api:8000"
```

### Claude Desktop Config

Place in `~/.config/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "doormat": {
      "command": "python",
      "args": ["-m", "doormat.mcp_server"],
      "env": {
        "DOORMAT_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

---

## Example Usage (Claude Desktop)

```
User: "Find me walkable 2-bed rentals in San Francisco under $3500"

Claude: I'll help you find rentals in San Francisco. Let me start by discovering property managers there.

[Claude calls: discover_city("San Francisco", "CA")]
Result: Found 32 property managers

Now let me create your preference profile and score available listings.

[Claude calls: create_preference("Walkable 2-bed in San Francisco under $3500")]
[Claude calls: score_listings(preference_id, "San Francisco", limit=10)]
Result: Found 8 excellent matches

Here are your top 3 matches:

1. **123 Main St, Downtown SF** - $3,200/mo, 2bd/1ba
   "Perfect match: walkable downtown location, modern finishes, under budget"

2. **456 Valencia St, Mission** - $3,400/mo, 2bd/1.5ba
   "Great fit: walkable neighborhood, vibrant area, parking included"

3. **789 Oak St, Haight** - $3,100/mo, 2bd/1ba
   "Excellent value: walkable commercial district, renovated 2023"

Would you like me to save these listings or search another city?
```

---

## Approval & Handoff

**MCP Owner**: Doormat Backend + Integration  
**Approved**: 2026-04-25  
**Next Step**: Implement MCP server + wire into FastAPI lifespan

