import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('next/navigation', () => {
  const searchParams = new URLSearchParams('run=run-1&category=filtered_out')
  return {
    useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
    useSearchParams: () => searchParams,
  }
})

vi.mock('@/components/listings/ListingMiniMap', () => ({
  ListingMiniMap: () => null,
}))

import ListingsPage from '@/app/listings/page'

const longWait = { timeout: 5000 }

describe('ListingsPage run mode', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it(
    'renders category tabs and filter reasons for run results',
    async () => {
      vi.useRealTimers()

      const runPayload = {
        id: 'run-1',
        discovery_run_id: 'd',
        city: 'Miami',
        preference_id: null,
        status: 'success',
        current_stage: 'complete',
        cancel_requested: false,
        sources_checked: 0,
        managers_validated: 0,
        listings_seen: 1,
        great_matches: 0,
        worth_a_look: 0,
        near_misses: 0,
        filtered_out: 1,
        cost_usd_so_far: 0,
        active_revision: 1,
        started_at: new Date().toISOString(),
        finished_at: new Date().toISOString(),
        filter_summary: {},
        suggestions: [],
        suggestions_early_signal: false,
      }

      const resultsPayload = [
        {
          id: 'res1',
          listing_id: 'lst1',
          revision: 1,
          category: 'filtered_out',
          score: null,
          filter_reasons_json: JSON.stringify([
            {
              label: 'Max rent',
              expected: '<=$2000',
              actual: '$2400',
              severity: 'hard_fail',
              suggestion: 'Raise max rent',
            },
          ]),
          explanation: 'Outside budget',
        },
      ]

      const listingRow = {
        id: 'lst1',
        address: '1 Main',
        price: 2400,
        bedrooms: 1,
        bathrooms: 1,
        sqft: null,
        pets_policy: 'unknown',
        url: null,
        source: 'pm_direct',
        score: null,
        score_explanation: null,
        validation_passed: true,
        extraction_timestamp: new Date().toISOString(),
      }

      function requestUrl(input: RequestInfo | URL): string {
        if (typeof input === 'string') return input
        if (input instanceof URL) return input.href
        if (typeof Request !== 'undefined' && input instanceof Request) return input.url
        return String(input)
      }

      vi.stubGlobal(
        'fetch',
        vi.fn(async (input: RequestInfo | URL) => {
          const u = requestUrl(input)
          if (u.includes('/api/search-runs/run-1/results')) {
            return { ok: true, json: async () => resultsPayload } as Response
          }
          if (/\/api\/search-runs\/run-1(?:\?|$)/.test(u) || u.endsWith('/api/search-runs/run-1')) {
            return { ok: true, json: async () => runPayload } as Response
          }
          if (u.includes('/api/listings')) {
            return {
              ok: true,
              json: async () => ({ listings: [listingRow] }),
            } as Response
          }
          return { ok: true, json: async () => ({}) } as Response
        }),
      )

      render(<ListingsPage />)

      expect(await screen.findByRole('tab', { name: /filtered out/i }, longWait)).toHaveAttribute(
        'aria-selected',
        'true',
      )

      await waitFor(
        () => {
          expect(screen.getByText(/raise max rent/i)).toBeInTheDocument()
          expect(document.body.textContent).toMatch(/1 Main|Listing lst1/)
        },
        longWait,
      )
    },
    10_000,
  )
})
