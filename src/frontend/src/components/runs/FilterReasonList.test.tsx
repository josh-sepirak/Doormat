import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { FilterReasonList, parseFilterReasons } from '@/components/runs/FilterReasonList'

describe('FilterReasonList', () => {
  it('parses valid JSON filter reasons and handles null/invalid', () => {
    expect(parseFilterReasons(null)).toEqual([])
    expect(parseFilterReasons('invalid json')).toEqual([])
    expect(parseFilterReasons('[]')).toEqual([])

    const parsed = parseFilterReasons(
      JSON.stringify([
        {
          filter_code: 'visual_trampoline',
          label: 'Fits 12ft Trampoline',
          verdict: 'confirmed',
          evidence: 'Photo 2 shows flat grass lawn (~35ft diameter).',
          photo_index: 2,
          is_visual: true,
        },
      ]),
    )
    expect(parsed).toHaveLength(1)
    expect(parsed[0].label).toBe('Fits 12ft Trampoline')
    expect(parsed[0].photo_index).toBe(2)
  })

  it('renders green confirmed visual badge with photo button', () => {
    const onPhotoClick = vi.fn()
    const reasonsJson = JSON.stringify([
      {
        filter_code: 'visual_trampoline',
        label: 'Fits 12ft Trampoline',
        verdict: 'confirmed',
        evidence: 'Photo 2 shows flat grass lawn with clearance.',
        photo_index: 2,
        is_visual: true,
      },
    ])

    render(<FilterReasonList reasonsJson={reasonsJson} onPhotoClick={onPhotoClick} />)

    expect(screen.getByText('Fits 12ft Trampoline')).toBeInTheDocument()
    expect(screen.getByText('Photo 2 shows flat grass lawn with clearance.')).toBeInTheDocument()

    const photoBtn = screen.getByRole('button', { name: /photo 2/i })
    expect(photoBtn).toBeInTheDocument()

    fireEvent.click(photoBtn)
    expect(onPhotoClick).toHaveBeenCalledWith(2)
  })

  it('renders compromise and not_possible badges alongside standard filter reasons', () => {
    const reasonsJson = JSON.stringify([
      {
        filter_code: 'visual_yard',
        label: 'Tight Fit / Paved Only',
        verdict: 'likely_compromise',
        evidence: 'Photo 1 shows concrete patio, no open lawn.',
        photo_index: 1,
        is_visual: true,
      },
      {
        filter_code: 'visual_dogs',
        label: 'No Yard Space',
        verdict: 'not_possible',
        evidence: '3rd floor apartment with no lawn access.',
        is_visual: true,
      },
      {
        filter_code: 'min_bedrooms_near',
        label: 'Bedrooms (near miss)',
        expected: '>=2',
        actual: '1',
        severity: 'near_miss',
        suggestion: 'One fewer bedroom may unlock similar locations',
      },
    ])

    render(<FilterReasonList reasonsJson={reasonsJson} />)

    expect(screen.getByText('Tight Fit / Paved Only')).toBeInTheDocument()
    expect(screen.getByText('No Yard Space')).toBeInTheDocument()
    expect(screen.getByText('Bedrooms (near miss)')).toBeInTheDocument()
    expect(screen.getByText('Expected >=2')).toBeInTheDocument()
  })
})
