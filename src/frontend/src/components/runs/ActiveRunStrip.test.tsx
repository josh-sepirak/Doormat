import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ActiveRunProvider } from '@/components/runs/ActiveRunProvider'
import { ActiveRunStrip } from '@/components/runs/ActiveRunStrip'

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}))

const mockRun = {
  id: 'run-xyz',
  discovery_run_id: 'd1',
  city: 'Denver',
  preference_id: null as string | null,
  status: 'running',
  current_stage: 'scraping',
  cancel_requested: false,
  sources_checked: 3,
  managers_validated: 2,
  listings_seen: 5,
  great_matches: 1,
  worth_a_look: 0,
  near_misses: 0,
  filtered_out: 0,
  cost_usd_so_far: 0.045,
  active_revision: 1,
  started_at: new Date(Date.now() - 90_000).toISOString(),
  finished_at: null as string | null,
  filter_summary: {},
  suggestions: [],
  suggestions_early_signal: true,
}

describe('ActiveRunStrip', () => {
  it('shows stage, counters, elapsed, cost, report link, and stop', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ active: true, run: mockRun }),
      } as Response),
    )

    render(
      <ActiveRunProvider>
        <ActiveRunStrip />
      </ActiveRunProvider>,
    )

    expect(await screen.findByRole('region', { name: /active search run/i })).toBeInTheDocument()
    expect(screen.getByText(/scraping/i)).toBeInTheDocument()
    expect(screen.getByText(/mgr 2/)).toBeInTheDocument()
    expect(screen.getByText(/\$0\.045/)).toBeInTheDocument()
    const report = screen.getByRole('link', { name: /open report/i })
    expect(report).toHaveAttribute('href', '/runs/run-xyz')
    expect(screen.getByRole('button', { name: /stop run/i })).toBeInTheDocument()
  })
})
