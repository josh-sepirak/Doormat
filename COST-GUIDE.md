# Cost Engineering Guide

Doormat is designed to run for under $1/month for typical personal use. This is achieved through a multi-tier model routing strategy and aggressive result caching.

## Model Tiers

We use two primary tiers of models:

1. **Cheap / Fast (Tier 1)**: 
   - **Model**: `google/gemma-4-31b-it:free` (via OpenRouter)
   - **Used For**: Discovery search, initial listing extraction (Mode A).
   - **Cost**: $0.00 (Free)
   - **Note**: If free models are unavailable, we fallback to Claude 3 Haiku (~$0.00025 per 1k tokens).

2. **Reasoning (Tier 2)**:
   - **Model**: `anthropic/claude-3.5-sonnet`
   - **Used For**: Listing scoring, agentic recovery extraction (Mode B).
   - **Cost**: ~$0.003 / 1k input tokens.
   - **Note**: Used sparingly only when high reasoning is required to match complex preferences or fix broken extraction paths.

## Model Routing

The `LLMClient` automatically routes tasks based on the `task` parameter:

| Task | Model | Why |
|---|---|---|
| `discovery` | Cheap | Identifying company names is a broad knowledge task, not reasoning-heavy. |
| `extraction` | Cheap | Mode A relies on structured HTML parsing which modern small models do well. |
| `scoring` | Reasoning | Comparing prose preferences to listing details requires nuanced semantic understanding. |

## Optimization Techniques

### 1. Deterministic Extraction (Mode A)
Most listings are extracted using Mode A, which uses the Cheap tier. We only escalate to Mode B (Agentic Reasoning) if Mode A fails quality gates (e.g., missing price or low confidence).

### 2. Strategy Caching
When Mode B successfully fixes an extraction, it emits a `strategy_update`. This is cached and used by subsequent Mode A calls for the same property manager, preventing future expensive recovery calls.

### 3. Budget Limits
You can set a hard budget limit in `src/backend/.env`:
```env
BUDGET_LIMIT_USD=5.0
```
The system will log warnings if this limit is exceeded and display status in the Cost Dashboard.

## Monitoring Costs

View real-time spending in the **Cost Dashboard** within the app:
- **Daily Spend**: Track trends over the last 30 days.
- **By Component**: See if discovery, extraction, or scoring is driving costs.
- **By Model**: Audit usage across different LLM providers.
