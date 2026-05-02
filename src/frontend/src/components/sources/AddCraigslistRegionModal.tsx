'use client'

import { useState } from 'react'
import {
  fetchCraigslistRegions,
  parseCraigslistRegionUrl,
  type CraigslistSuggestion,
} from '@/client/craigslist-regions'
import { createTrustedSource } from '@/client/trusted-sources'
import { Button } from '@/components/Button'

export function AddCraigslistRegionModal({
  open,
  onClose,
  onSaved,
  initialCity = '',
  initialState = 'CA',
}: {
  open: boolean
  onClose: () => void
  onSaved: () => void
  initialCity?: string
  initialState?: string
}) {
  const [city, setCity] = useState(initialCity)
  const [state, setState] = useState(initialState)
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<CraigslistSuggestion[]>([])
  const [geoName, setGeoName] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [pasteUrl, setPasteUrl] = useState('')
  const [pasteError, setPasteError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  if (!open) return null

  async function loadSuggestions() {
    setLoading(true)
    setSaveError(null)
    try {
      const res = await fetchCraigslistRegions(city.trim(), state.trim())
      setSuggestions(res.suggestions)
      setGeoName(res.geocoded.display_name)
      setSelected(res.suggestions[0]?.subdomain ?? null)
    } catch (e) {
      setSuggestions([])
      setSaveError(e instanceof Error ? e.message : 'Could not load suggestions')
    } finally {
      setLoading(false)
    }
  }

  async function validatePaste() {
    setPasteError(null)
    const r = await parseCraigslistRegionUrl(pasteUrl.trim())
    if (!r.valid) {
      setPasteError(r.error || 'Invalid URL')
      return null
    }
    return r
  }

  async function save() {
    setSaveError(null)
    setSaving(true)
    try {
      let label = ''
      let url = ''
      if (advancedOpen && pasteUrl.trim()) {
        const parsed = await validatePaste()
        if (!parsed) {
          setSaving(false)
          return
        }
        label = parsed.label || parsed.subdomain
        url = parsed.url
      } else {
        const pick = suggestions.find((s) => s.subdomain === selected)
        if (!pick) {
          setSaveError('Pick a suggested region first, or use Advanced paste.')
          setSaving(false)
          return
        }
        label = pick.label
        url = pick.url
      }
      await createTrustedSource({
        kind: 'craigslist_region',
        label,
        url,
        city: `${city.trim()}, ${state.trim().toUpperCase()}`,
      })
      onSaved()
      onClose()
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="cl-region-title"
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <h2 id="cl-region-title" className="text-lg font-semibold text-slate-900 dark:text-white">
          Add trusted Craigslist region
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Geocode your city, pick the regional site that matches where you search.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          <label className="block min-w-[140px] flex-1 text-sm">
            <span className="text-slate-600 dark:text-slate-300">City</span>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-800"
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
          </label>
          <label className="block w-24 text-sm">
            <span className="text-slate-600 dark:text-slate-300">State</span>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 uppercase dark:border-slate-600 dark:bg-slate-800"
              value={state}
              onChange={(e) => setState(e.target.value)}
              maxLength={32}
            />
          </label>
          <div className="flex w-full items-end sm:w-auto">
            <Button type="button" color="blue" onClick={() => void loadSuggestions()} disabled={loading}>
              {loading ? 'Loading…' : 'Suggest regions'}
            </Button>
          </div>
        </div>

        {geoName ? (
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">Geocoded: {geoName}</p>
        ) : null}

        {suggestions.length > 0 ? (
          <ul className="mt-4 space-y-2">
            {suggestions.map((s) => (
              <li key={s.subdomain}>
                <label className="flex cursor-pointer gap-3 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                  <input
                    type="radio"
                    name="cl-region"
                    checked={selected === s.subdomain}
                    onChange={() => setSelected(s.subdomain)}
                  />
                  <span>
                    <span className="font-medium text-slate-900 dark:text-white">{s.label}</span>
                    <span className="block text-xs text-slate-500 dark:text-slate-400">
                      {s.subdomain}.craigslist.org — {s.distance_mi} mi
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        ) : null}

        <button
          type="button"
          className="mt-4 text-sm text-blue-600 underline dark:text-blue-400"
          onClick={() => setAdvancedOpen((v) => !v)}
        >
          {advancedOpen ? 'Hide' : 'Advanced'}: paste URL or subdomain
        </button>
        {advancedOpen ? (
          <div className="mt-2">
            <input
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
              placeholder="https://inlandempire.craigslist.org or inlandempire"
              value={pasteUrl}
              onChange={(e) => setPasteUrl(e.target.value)}
            />
            {pasteError ? <p className="mt-1 text-xs text-red-600">{pasteError}</p> : null}
          </div>
        ) : null}

        {saveError ? <p className="mt-3 text-sm text-red-600">{saveError}</p> : null}

        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" color="blue" disabled={saving} onClick={() => void save()}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
    </div>
  )
}
