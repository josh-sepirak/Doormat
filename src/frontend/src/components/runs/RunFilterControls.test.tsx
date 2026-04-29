import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  patchSearchRunFilters: vi.fn(),
}))

vi.mock('@/client/search-runs', () => ({
  patchSearchRunFilters: mocks.patchSearchRunFilters,
}))

import { RunFilterControls } from '@/components/runs/RunFilterControls'

const run = {
  id: 'run-f',
  discovery_run_id: 'd',
  city: 'Seattle',
  preference_id: 'p1',
  status: 'running',
  current_stage: 'discovery',
  cancel_requested: false,
  sources_checked: 0,
  managers_validated: 0,
  listings_seen: 0,
  great_matches: 0,
  worth_a_look: 0,
  near_misses: 0,
  filtered_out: 0,
  cost_usd_so_far: 0,
  active_revision: 2,
  started_at: new Date().toISOString(),
  finished_at: null as string | null,
  filter_summary: {},
  suggestions: [],
  suggestions_early_signal: true,
}

describe('RunFilterControls', () => {
  it('mentions next-run-only scope for city and keys in helper copy', () => {
    const onPatched = vi.fn()
    render(<RunFilterControls run={run} onPatched={onPatched} />)
    expect(screen.getByText(/next/i)).toBeInTheDocument()
    expect(screen.getByText(/city/i)).toBeInTheDocument()
    expect(screen.getByText(/api keys/i)).toBeInTheDocument()
  })

  it('submits patch when max rent entered', async () => {
    mocks.patchSearchRunFilters.mockResolvedValue({ ...run, active_revision: 3 })
    const onPatched = vi.fn()
    render(<RunFilterControls run={run} onPatched={onPatched} />)
    fireEvent.change(screen.getByPlaceholderText(/3500/i), { target: { value: '2800' } })
    fireEvent.click(screen.getByRole('button', { name: /apply to current run/i }))
    await waitFor(() =>
      expect(mocks.patchSearchRunFilters).toHaveBeenCalledWith('run-f', { max_price: 2800 }),
    )
    expect(onPatched).toHaveBeenCalled()
  })
})
