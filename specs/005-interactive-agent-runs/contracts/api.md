# Search Runs API Contract

**Version:** 1.0  
**Base Path:** `/api/search-runs`  
**Auth:** Optional bearer token via `AUTH_BEARER_TOKEN` env var (all endpoints)  
**Format:** JSON  

---

## Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| POST | / | Create + trigger new search run |
| GET | /active | Get currently active run |
| GET | /{run_id} | Get run state, filters, suggestions |
| GET | /{run_id}/events | Poll run events (after-sequence pagination) |
| POST | /{run_id}/stop | Request cancellation |
| GET | /{run_id}/results | Query results with category/reason filters |
| PATCH | /{run_id}/filters | Update filters mid-run, reclassify |

---

## POST /api/search-runs

**Create and start a new search run.**

### Request

```json
{
  "preference_id": "uuid (required)",
  "auto_stop_after_minutes": "integer (optional)",
  "async": "boolean (optional, default: true)"
}
```

### Response (202 Accepted / 200 OK)

```json
{
  "id": "uuid",
  "status": "discovering|extracting|scoring|completed|error|cancelled|cancel_requested",
  "city": "San Francisco",
  "created_at": "ISO 8601",
  "started_at": "ISO 8601",
  "finished_at": null,
  "elapsed_seconds": 15,
  "active_revision": 1,
  "counters": {
    "managers_discovered": 32,
    "managers_scraped": 8,
    "listings_extracted": 145,
    "listings_scored": 89,
    "listings_classified": {
      "match": 45,
      "near_miss": 22,
      "rejected": 78
    }
  },
  "cost_usd": 0.042,
  "filters": {
    "max_price": 3500,
    "min_bedrooms": 2,
    "pets_required": true
  },
  "suggestion_summary": {
    "early_signals": [
      "Raise budget by ~$200 to unlock 15 near-misses"
    ],
    "final_suggestions": null
  },
  "warnings": [
    "Discovery still in progress; results may be incomplete."
  ]
}
```

---

## GET /api/search-runs/active

**Get currently active run (if any).**

### Response (200 OK / 204 No Content)

```json
{
  "id": "uuid",
  "status": "discovering|extracting|...",
  "city": "San Francisco",
  "elapsed_seconds": 45,
  "counters": {
    "managers_discovered": 32,
    "listings_extracted": 145
  },
  "cost_usd": 0.087
}
```

Returns **204 No Content** if no active run exists.

---

## GET /api/search-runs/{run_id}

**Get full run state, filters, suggestions.**

### Response (200 OK)

```json
{
  "id": "uuid",
  "status": "discovering|extracting|scoring|completed|error|cancelled|cancel_requested",
  "city": "San Francisco",
  "created_at": "ISO 8601",
  "finished_at": null,
  "elapsed_seconds": 120,
  "active_revision": 2,
  "counters": {
    "managers_discovered": 32,
    "listings_classified": {
      "match": 67,
      "near_miss": 45,
      "rejected": 133
    }
  },
  "cost_usd": 0.256,
  "filters": {
    "max_price": 3500,
    "min_bedrooms": 2,
    "pets_required": true
  },
  "suggestion_summary": {
    "early_signals": [
      "Raise budget by ~$200 to unlock 15 additional near-misses",
      "Check pet policies—many matches allow dogs but not cats"
    ],
    "final_suggestions": null
  },
  "warnings": [
    "Discovery still in progress; filter changes will apply only to newly extracted listings"
  ]
}
```

---

## GET /api/search-runs/{run_id}/events

**Poll run events with cursor-based after-sequence pagination.**

### Query Parameters

- `after_sequence` (integer, optional, default: 0)
- `limit` (integer, optional, default: 50, max: 500)
- `event_type` (string, optional)
- `user_visible_only` (boolean, optional, default: false)

### Response (200 OK)

```json
{
  "run_id": "uuid",
  "events": [
    {
      "id": "uuid",
      "sequence": 15,
      "type": "stage_started",
      "stage": "discovery",
      "created_at": "ISO 8601",
      "payload": {
        "stage": "discovery",
        "city": "San Francisco"
      },
      "visibility": "user_visible"
    },
    {
      "id": "uuid",
      "sequence": 16,
      "type": "candidate_found",
      "stage": "discovery",
      "created_at": "ISO 8601",
      "payload": {
        "name": "Downtown Properties LLC",
        "url": "https://...",
        "confidence": 0.95
      },
      "visibility": "user_visible"
    },
    {
      "id": "uuid",
      "sequence": 17,
      "type": "listing_classified_match",
      "stage": "extraction",
      "created_at": "ISO 8601",
      "payload": {
        "listing_id": "uuid",
        "address": "123 Main St, SF",
        "score": 92
      },
      "visibility": "user_visible"
    }
  ],
  "max_sequence": 17,
  "has_more": false
}
```

**Event Types:**

| Type | Stage | Visibility |
|------|-------|------------|
| `stage_started` | discovery/extraction/scoring | User |
| `stage_completed` | * | User |
| `candidate_found` | discovery | User |
| `manager_validated` | discovery | User |
| `listings_extracted` | extraction | User |
| `hard_filters_applied` | extraction | User |
| `listing_classified_match` | extraction | User |
| `listing_classified_near_miss` | extraction | User |
| `listing_classified_rejected` | extraction | User |
| `filter_summary_updated` | * | User |
| `suggestion_updated` | * | User |
| `cancellation_requested` | * | User |
| `run_cancelled` | * | User |
| `recipe_applied` | extraction | Developer |

---

## POST /api/search-runs/{run_id}/stop

**Request cancellation of active run.**

### Response (200 OK)

```json
{
  "id": "uuid",
  "status": "cancel_requested",
  "message": "Cancellation requested. Finishing current work unit..."
}
```

Status transitions to `cancelled` once backend completes current unit.

---

## GET /api/search-runs/{run_id}/results

**Query classified listings with category and reason filters.**

### Query Parameters

- `category` (string, optional) — `match|near_miss|rejected`
- `reason_code` (string, optional)
- `limit` (integer, optional, default: 20, max: 100)
- `offset` (integer, optional, default: 0)
- `revision` (integer, optional, default: latest)

### Response (200 OK)

```json
{
  "run_id": "uuid",
  "total_count": 247,
  "filtered_count": 89,
  "returned_count": 20,
  "offset": 0,
  "revision": 2,
  "results": [
    {
      "id": "uuid",
      "listing_id": "uuid",
      "address": "123 Main St, San Francisco, CA",
      "price": 3200,
      "bedrooms": 2,
      "bathrooms": 1.5,
      "url": "https://...",
      "property_manager": "Downtown Properties LLC",
      "category": "match",
      "score": 92,
      "score_explanation": "Strong match: modern finishes, walkable, pets OK, under budget.",
      "filter_reasons": [
        {
          "filter": "price",
          "status": "pass",
          "expected": "≤ $3500",
          "actual": "$3200",
          "severity": "info"
        },
        {
          "filter": "bedrooms",
          "status": "pass",
          "expected": "≥ 2",
          "actual": 2,
          "severity": "info"
        }
      ]
    }
  ]
}
```

---

## PATCH /api/search-runs/{run_id}/filters

**Update filters mid-run; triggers reclassification.**

### Request

```json
{
  "max_price": 3800,
  "min_bedrooms": 2,
  "pets_required": false
}
```

### Response (200 OK)

```json
{
  "id": "uuid",
  "active_revision": 3,
  "filters": {
    "max_price": 3800,
    "pets_required": false
  },
  "reclassification": {
    "triggered": true,
    "revision": 3,
    "affected_results": 156,
    "category_changes": {
      "match": 3,
      "near_miss": 12,
      "rejected": -15
    }
  },
  "suggestion_summary": {
    "early_signals": [
      "Lowering pet requirement unlocked 12 near-misses; consider a few."
    ]
  }
}
```

---

## Error Responses

All errors return:

```json
{
  "detail": "Error message",
  "code": "NOT_FOUND | BAD_REQUEST | CONFLICT | INTERNAL_ERROR",
  "request_id": "uuid"
}
```

| Status | When |
|--------|------|
| 200 | Success |
| 202 | Async work accepted |
| 204 | No content (no active run) |
| 400 | Bad request (invalid filters) |
| 404 | Not found |
| 409 | Conflict (run terminal, run active) |
| 500 | Server error |

---

## Pagination Patterns

### After-Sequence (Events)

For live polling:

```javascript
let maxSeq = 0;
const resp = await fetch(`/api/search-runs/${id}/events?after_sequence=${maxSeq}`);
const { events, max_sequence } = await resp.json();
maxSeq = max_sequence;
```

### Offset (Results)

For paginated tables:

```javascript
const limit = 20;
const resp = await fetch(`/api/search-runs/${id}/results?offset=${page * limit}&limit=${limit}`);
const { results, filtered_count } = await resp.json();
```

---

## Rate Limiting (Self-Hosted)

Default (localhost): None  
With auth: 1 new run/min, 10 queries/sec, 100 polls/sec

Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## Version History

**v1.0 (2026-05-01)**
- Initial spec: Phases 1-8 complete
- After-sequence event pagination
- Revision-based filter reclassification
- Deterministic classification (no LLM in scoring logic)
