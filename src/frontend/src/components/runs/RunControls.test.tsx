import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { RunControls } from '@/components/runs/RunControls'

const base = {
  id: 'r1',
  discovery_run_id: 'd',
  city: 'X',
  preference_id: null as string | null,
  current_stage: 'discovery',
  sources_checked: 0,
  managers_validated: 0,
  listings_seen: 0,
  great_matches: 0,
  worth_a_look: 0,
  near_misses: 0,
  filtered_out: 0,
  cost_usd_so_far: 0,
  active_revision: 1,
  started_at: new Date().toISOString(),
  finished_at: null as string | null,
  filter_summary: {},
  suggestions: [],
  suggestions_early_signal: true,
}

describe('RunControls', () => {
  it('shows Stop when run is active', () => {
    const onStop = vi.fn().mockResolvedValue(undefined)
    render(<RunControls run={{ ...base, status: 'running', cancel_requested: false }} onStop={onStop} />)
    expect(screen.getByRole('button', { name: /stop run/i })).toBeEnabled()
  })

  it('shows Stopping when cancel requested', () => {
    const onStop = vi.fn()
    render(
      <RunControls
        run={{ ...base, status: 'cancel_requested', cancel_requested: true }}
        onStop={onStop}
      />,
    )
    expect(screen.getByText(/stopping/i)).toBeInTheDocument()
  })

  it('shows Cancelled when terminal cancelled', () => {
    render(<RunControls run={{ ...base, status: 'cancelled', cancel_requested: true }} onStop={vi.fn()} />)
    expect(screen.getByText(/cancelled/i)).toBeInTheDocument()
  })

  it('shows error label when run ended in error', () => {
    render(<RunControls run={{ ...base, status: 'error', cancel_requested: false }} onStop={vi.fn()} />)
    expect(screen.getByText(/ended with error/i)).toBeInTheDocument()
  })

  it('surfaces stop failure', async () => {
    const onStop = vi.fn().mockRejectedValue(new Error('network'))
    render(<RunControls run={{ ...base, status: 'running', cancel_requested: false }} onStop={onStop} />)
    fireEvent.click(screen.getByRole('button', { name: /stop run/i }))
    expect(await screen.findByText(/network/i)).toBeInTheDocument()
  })
})
