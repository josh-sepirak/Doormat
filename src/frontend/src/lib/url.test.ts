import { describe, expect, it } from 'vitest'

import { safeHttpUrl } from './url'

describe('safeHttpUrl', () => {
  it('returns https and http URLs', () => {
    expect(safeHttpUrl('https://example.com/a')).toBe('https://example.com/a')
    expect(safeHttpUrl('http://example.com/a')).toBe('http://example.com/a')
  })

  it('rejects script and data URLs', () => {
    expect(safeHttpUrl('javascript:alert(1)')).toBeNull()
    expect(safeHttpUrl('data:text/html,<script>alert(1)</script>')).toBeNull()
  })

  it('returns null for empty, missing, or malformed input', () => {
    expect(safeHttpUrl(null)).toBeNull()
    expect(safeHttpUrl(undefined)).toBeNull()
    expect(safeHttpUrl('')).toBeNull()
    expect(safeHttpUrl('not a url')).toBeNull()
  })
})
