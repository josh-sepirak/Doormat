import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { RunSuggestions } from '@/components/runs/RunSuggestions'

const baseRun = {
  id: 'r',
  discovery_run_id: 'd',
  city: 'C',
  preference_id: null as string | null,
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
  active_revision: 1,
  started_at: new Date().toISOString(),
  finished_at: null as string | null,
  filter_summary: {},
  suggestions: [],
  suggestions_early_signal: true,
}

describe('RunSuggestions', () => {
  it('shows early-signal label while run is active', () => {
    render(
      <RunSuggestions
        run={{ ...baseRun, suggestions_early_signal: true }}
        suggestions={[{ kind: 'pets', message: 'Pet policy unknown on several listings', count: 3 }]}
      />,
    )
    expect(screen.getByText(/early signal/i)).toBeInTheDocument()
    expect(screen.getByText(/pet policy unknown/i)).toBeInTheDocument()
    expect(screen.getByText('(3)')).toBeInTheDocument()
  })

  it('shows final label when suggestions are finalized', () => {
    render(
      <RunSuggestions
        run={{ ...baseRun, status: 'success', suggestions_early_signal: false }}
        suggestions={[{ kind: 'beds', message: 'Lower bedroom minimum', count: 1 }]}
      />,
    )
    expect(screen.getByText(/final for this run/i)).toBeInTheDocument()
  })
})
