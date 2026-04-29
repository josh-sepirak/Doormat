import { render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({
  fetchSearchRun: vi.fn(),
  fetchSearchRunEvents: vi.fn().mockResolvedValue([]),
  stopSearchRun: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/client/search-runs', () => client)

import { RunReport } from '@/components/runs/RunReport'

vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}))

const runSnap = {
  id: 'run-a',
  discovery_run_id: 'd',
  city: 'Portland',
  preference_id: null as string | null,
  status: 'running',
  current_stage: 'discovery',
  cancel_requested: false,
  sources_checked: 1,
  managers_validated: 2,
  listings_seen: 3,
  extraction_attempts: 6,
  great_matches: 0,
  worth_a_look: 1,
  near_misses: 0,
  filtered_out: 4,
  cost_usd_so_far: 0.02,
  active_revision: 1,
  started_at: new Date().toISOString(),
  finished_at: null as string | null,
  filter_summary: {},
  suggestions: [{ kind: 'rent', message: 'Try raising max rent', count: 2 }],
  suggestions_early_signal: true,
}

describe('RunReport', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('loads run details and shows counters, suggestions, and activity heading', async () => {
    client.fetchSearchRun.mockResolvedValue(runSnap)

    render(<RunReport runId="run-a" />)

    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: /portland/i })).toBeInTheDocument())
    expect(screen.getByText(/live activity/i)).toBeInTheDocument()
    const counters = screen.getByRole('region', { name: /run counters/i })
    expect(within(counters).getByText('2')).toBeInTheDocument()
    expect(within(counters).getByText(/extraction attempts/i)).toBeInTheDocument()
    expect(within(counters).getByText('6')).toBeInTheDocument()
    expect(screen.getByText(/try raising max rent/i)).toBeInTheDocument()
    expect(screen.getByText(/early signal/i)).toBeInTheDocument()
    expect(client.fetchSearchRun).toHaveBeenCalled()
  })

  it('lists warnings from user events', async () => {
    client.fetchSearchRun.mockResolvedValue(runSnap)
    client.fetchSearchRunEvents.mockResolvedValue([
      {
        id: 'e1',
        sequence: 1,
        event_type: 'warning',
        stage: 'discovery',
        message: 'Rate limit approaching',
        payload_json: null,
        visibility: 'user',
        timestamp: new Date().toISOString(),
      },
    ])

    render(<RunReport runId="run-a" />)

    const warnRegion = await screen.findByRole('region', { name: /^warnings$/i })
    expect(within(warnRegion).getByText(/rate limit approaching/i)).toBeInTheDocument()
  })
})
