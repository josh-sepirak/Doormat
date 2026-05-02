import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/client/craigslist-regions', () => ({
  fetchCraigslistRegions: vi.fn().mockResolvedValue({
    geocoded: { lat: 34, lon: -118, display_name: 'Lancaster, CA' },
    suggestions: [
      {
        subdomain: 'inlandempire',
        label: 'inland empire',
        url: 'https://inlandempire.craigslist.org',
        distance_mi: 40,
      },
    ],
  }),
  parseCraigslistRegionUrl: vi.fn(),
}))

vi.mock('@/client/trusted-sources', () => ({
  createTrustedSource: vi.fn().mockResolvedValue({ id: '1' }),
}))

import { AddCraigslistRegionModal } from './AddCraigslistRegionModal'

describe('AddCraigslistRegionModal', () => {
  it('loads suggestions and shows radio for nearest region', async () => {
    const onClose = vi.fn()
    const onSaved = vi.fn()
    render(
      <AddCraigslistRegionModal open onClose={onClose} onSaved={onSaved} initialCity="Lancaster" initialState="CA" />,
    )

    fireEvent.click(screen.getByRole('button', { name: /suggest regions/i }))
    expect(await screen.findByText(/inland empire/i)).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /inland empire/i })).toBeInTheDocument()
  })
})
