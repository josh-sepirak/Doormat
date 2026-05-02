'use client'

import { useState } from 'react'
import { createTrustedSource } from '@/client/trusted-sources'
import { Button } from '@/components/Button'

export function AddPropertyManagerModal({
  open,
  onClose,
  onSaved,
  defaultCity = '',
}: {
  open: boolean
  onClose: () => void
  onSaved: () => void
  defaultCity?: string
}) {
  const [label, setLabel] = useState('')
  const [url, setUrl] = useState('')
  const [city, setCity] = useState(defaultCity)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  if (!open) return null

  let faviconHost = ''
  try {
    const u = new URL(url.startsWith('http') ? url : `https://${url}`)
    faviconHost = u.hostname
  } catch {
    faviconHost = ''
  }
  const faviconSrc = faviconHost
    ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(faviconHost)}&sz=32`
    : ''

  async function save() {
    setError(null)
    setSaving(true)
    try {
      await createTrustedSource({
        kind: 'property_manager',
        label: label.trim() || 'Property manager',
        url: url.trim(),
        city: city.trim() || null,
      })
      onSaved()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="pm-source-title"
        className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <h2 id="pm-source-title" className="text-lg font-semibold text-slate-900 dark:text-white">
          Add trusted property manager
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Paste the listings or inventory page you want scraped (same city you use in preferences).
        </p>

        <label className="mt-4 block text-sm">
          <span className="text-slate-600 dark:text-slate-300">Display name</span>
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-800"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Valley Rentals LLC"
          />
        </label>

        <label className="mt-3 block text-sm">
          <span className="text-slate-600 dark:text-slate-300">Listings page URL</span>
          <div className="mt-1 flex items-center gap-2">
            {faviconSrc && url.length > 6 ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={faviconSrc} alt="" width={20} height={20} className="shrink-0 rounded" />
            ) : null}
            <input
              className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-800"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/rentals"
            />
          </div>
        </label>

        <label className="mt-3 block text-sm">
          <span className="text-slate-600 dark:text-slate-300">City (for matching runs)</span>
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-800"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="e.g. Lancaster, CA"
          />
        </label>

        {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}

        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" color="blue" disabled={saving || !url.trim()} onClick={() => void save()}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
    </div>
  )
}
