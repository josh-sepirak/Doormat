import { Page } from '@playwright/test'

export const MOCK_PREFERENCES = [
  {
    id: 1,
    city: 'Austin, TX',
    description: 'Looking for a 2BR near downtown',
    min_bedrooms: 2,
    max_price: 2500,
    has_openrouter_api_key: true,
    openrouter_key_last4: 'ab12',
    has_apify_api_token: false,
    apify_token_last4: null,
    api_provider: 'openrouter',
  },
]

export const MOCK_MANAGERS = [
  {
    id: 'mgr-1',
    name: 'Austin Realty Group',
    website: 'https://austinrealty.example.com',
    listing_page_url: 'https://austinrealty.example.com/listings',
    validated: true,
    city: 'Austin, TX',
  },
  {
    id: 'mgr-2',
    name: 'Capitol City Properties',
    website: 'https://capitolcity.example.com',
    listing_page_url: null,
    validated: false,
    city: 'Austin, TX',
  },
]

export const MOCK_LISTINGS = [
  {
    id: 'lst-1',
    address: '123 Congress Ave, Austin, TX 78701',
    price: 2200,
    bedrooms: 2,
    bathrooms: 1,
    sqft: 950,
    pets_policy: 'cats_only',
    url: 'https://austinrealty.example.com/123-congress',
    source: 'pm_direct',
    score: 78,
    score_explanation: 'Close to downtown, within budget, cats allowed',
    validation_passed: true,
    extraction_timestamp: '2024-01-15T10:00:00Z',
  },
  {
    id: 'lst-2',
    address: '456 South Lamar Blvd, Austin, TX 78704',
    price: 1950,
    bedrooms: 1,
    bathrooms: 1,
    sqft: 750,
    pets_policy: 'none_allowed',
    url: 'https://capitolcity.example.com/456-lamar',
    source: 'pm_direct',
    score: 45,
    score_explanation: 'Under budget but only 1BR and no pets',
    validation_passed: true,
    extraction_timestamp: '2024-01-15T11:00:00Z',
  },
]

// Home page uses /api/discovery/runs (returns DiscoveryRun[] directly)
export const MOCK_DISCOVERY_RUNS = [
  {
    id: 'drun-1',
    city: 'Austin, TX',
    status: 'success',
    managers_found: 2,
    started_at: '2024-01-15T09:00:00Z',
    logs: [
      { id: 1, level: 'info', component: 'discovery', message: 'Starting discovery for Austin, TX' },
      { id: 2, level: 'success', component: 'discovery', message: 'Found 2 property managers' },
    ],
  },
]

// Listings page uses /api/search-runs (SearchRun type from client)
export const MOCK_SEARCH_RUN = {
  id: 'run-1',
  discovery_run_id: 'drun-1',
  city: 'Austin, TX',
  preference_id: '1',
  status: 'success',
  current_stage: 'done',
  cancel_requested: false,
  sources_checked: 2,
  managers_validated: 2,
  listings_seen: 2,
  great_matches: 1,
  worth_a_look: 0,
  near_misses: 1,
  filtered_out: 0,
  cost_usd_so_far: 0.002,
  active_revision: 1,
  started_at: '2024-01-15T09:00:00Z',
  finished_at: '2024-01-15T09:05:00Z',
  filter_summary: {},
  suggestions: [],
  suggestions_early_signal: false,
}

export const MOCK_RUN_RESULTS = [
  {
    id: 'rr-1',
    run_id: 'run-1',
    listing_id: 'lst-1',
    revision: 1,
    category: 'great_match',
    score: 0.78,
    explanation: 'Close to downtown, within budget, cats allowed',
    filter_reasons_json: null,
  },
  {
    id: 'rr-2',
    run_id: 'run-1',
    listing_id: 'lst-2',
    revision: 1,
    category: 'near_miss',
    score: 0.45,
    explanation: 'Under budget but only 1BR and no pets',
    filter_reasons_json: null,
  },
]

export const MOCK_COST_SUMMARY = {
  total_cost_usd: 0.0042,
  total_calls: 12,
  total_tokens: 8400,
  avg_cost_per_call: 0.00035,
  cache_hit_rate: 0.2,
  budget_limit_usd: 1.0,
  budget_remaining_usd: 0.9958,
  budget_exceeded: false,
}

export async function mockBackendApis(page: Page) {
  await page.route('**/health', (route) =>
    route.fulfill({ json: { status: 'ok' } }),
  )

  await page.route('**/api/preferences', (route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({ json: MOCK_PREFERENCES })
    } else {
      route.fulfill({ json: MOCK_PREFERENCES[0] })
    }
  })

  await page.route('**/api/discovery/cities/*/managers', (route) =>
    // Home page expects a plain array for setManagers
    route.fulfill({ json: MOCK_MANAGERS }),
  )

  // Home page uses /api/discovery/runs (array response)
  await page.route('**/api/discovery/runs', (route) =>
    route.fulfill({ json: MOCK_DISCOVERY_RUNS }),
  )

  // Listings page uses /api/search-runs/{id}
  await page.route('**/api/search-runs/run-1', (route) =>
    route.fulfill({ json: MOCK_SEARCH_RUN }),
  )

  // Use regex to match path + optional query params
  await page.route(/\/api\/search-runs\/run-1\/results/, (route) =>
    route.fulfill({ json: MOCK_RUN_RESULTS }),
  )

  // POST to create a new search run
  await page.route('**/api/search-runs', (route) => {
    if (route.request().method() === 'POST') {
      route.fulfill({ status: 201, json: MOCK_SEARCH_RUN })
    } else {
      route.fulfill({ json: { runs: [], total: 0 } })
    }
  })

  await page.route('**/api/listings', (route) =>
    route.fulfill({ json: { listings: MOCK_LISTINGS, total: 2 } }),
  )

  await page.route('**/api/listings/*/save', (route) =>
    route.fulfill({ json: { ok: true } }),
  )

  await page.route('**/api/costs/summary', (route) =>
    route.fulfill({ json: MOCK_COST_SUMMARY }),
  )

  await page.route('**/api/costs/by-component', (route) =>
    route.fulfill({ json: [{ group: 'discovery', cost_usd: 0.002, call_count: 6, tokens_total: 4000 }] }),
  )

  await page.route('**/api/costs/by-model', (route) =>
    route.fulfill({
      json: [
        { group: 'openai/gpt-4o-mini', cost_usd: 0.003, call_count: 10, tokens_total: 6000 },
        { group: 'openai/gpt-4o', cost_usd: 0.0012, call_count: 2, tokens_total: 2400 },
      ],
    }),
  )

  await page.route('**/api/costs/timeseries*', (route) =>
    route.fulfill({ json: [] }),
  )

  await page.route('**/api/openrouter/models', (route) =>
    route.fulfill({ json: { models: [], object: 'list' } }),
  )

  await page.route('**/api/config', (route) =>
    route.fulfill({
      json: {
        has_openrouter_key: true,
        openrouter_key_last4: 'ab12',
        has_apify_token: false,
        apify_token_last4: null,
      },
    }),
  )
}

export async function mockBackendDown(page: Page) {
  await page.route('**/health', (route) => route.abort())
  await page.route('**/api/**', (route) => route.abort())
}
