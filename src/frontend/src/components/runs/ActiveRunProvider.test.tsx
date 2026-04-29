import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ActiveRunProvider, useActiveRun } from '@/components/runs/ActiveRunProvider'

const mockRun = {
  id: 'run-1',
  discovery_run_id: 'd1',
  city: 'Austin',
  preference_id: null as string | null,
  status: 'running',
  current_stage: 'discovery',
  cancel_requested: false,
  sources_checked: 2,
  managers_validated: 1,
  listings_seen: 0,
  great_matches: 0,
  worth_a_look: 0,
  near_misses: 0,
  filtered_out: 0,
  cost_usd_so_far: 0.012,
  active_revision: 1,
  started_at: new Date().toISOString(),
  finished_at: null as string | null,
  filter_summary: {},
  suggestions: [],
  suggestions_early_signal: true,
}

function Consumer() {
  const { run, loading } = useActiveRun()
  if (loading) return <span>loading</span>
  if (!run) return <span>inactive</span>
  return <span data-testid="city">{run.city}</span>
}

describe('ActiveRunProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('hydrates active run from API and reconnects on poll', async () => {
    const activeJson = { active: true, run: mockRun }
    const inactiveJson = { active: false, run: null }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => activeJson,
      } as Response)
      .mockResolvedValue({
        ok: true,
        json: async () => inactiveJson,
      } as Response)
    vi.stubGlobal('fetch', fetchMock)

    render(
      <ActiveRunProvider>
        <Consumer />
      </ActiveRunProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('city')).toHaveTextContent('Austin'))
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/search-runs/active'),
      expect.objectContaining({ cache: 'no-store' }),
    )

    await vi.advanceTimersByTimeAsync(3100)
    await waitFor(() => expect(screen.getByText('inactive')).toBeInTheDocument())
    expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2)
  })
})
