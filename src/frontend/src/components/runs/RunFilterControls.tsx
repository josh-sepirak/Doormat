'use client'

import { useState } from 'react'

import type { SearchRun } from '@/client/search-runs'
import { patchSearchRunFilters } from '@/client/search-runs'

type RunFilterControlsProps = {
  run: SearchRun
  onPatched: (run: SearchRun) => void
}

export function RunFilterControls({ run, onPatched }: RunFilterControlsProps) {
  const [maxPrice, setMaxPrice] = useState('')
  const [minBedrooms, setMinBedrooms] = useState('')
  const [minBathrooms, setMinBathrooms] = useState('')
  const [petsRequired, setPetsRequired] = useState<boolean | ''>('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const terminal = ['success', 'error', 'cancelled'].includes(run.status)
  if (terminal) {
    return null
  }

  const apply = async () => {
    setError(null)
    setSaving(true)
    try {
      const body: Record<string, unknown> = {}
      if (maxPrice.trim()) body.max_price = Number(maxPrice)
      if (minBedrooms.trim()) body.min_bedrooms = parseInt(minBedrooms, 10)
      if (minBathrooms.trim()) body.min_bathrooms = parseFloat(minBathrooms)
      if (petsRequired !== '') body.pets_required = petsRequired

      if (Object.keys(body).length === 0) {
        setError('Update at least one filter, or leave fields blank to skip.')
        return
      }

      const updated = await patchSearchRunFilters(run.id, body)
      onPatched(updated)
      setMaxPrice('')
      setMinBedrooms('')
      setMinBathrooms('')
      setPetsRequired('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Update failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
      <h2 className="font-display text-lg font-medium text-slate-900 dark:text-slate-100">
        Adjust filters for this run
      </h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Changes re-score listings already found (revision {run.active_revision}). City, API keys, and source scope
        apply on the <strong>next</strong> run only — set those from Preferences before you start.
      </p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-slate-600 dark:text-slate-400">Max rent (USD / mo)</span>
          <input
            type="number"
            min={1}
            step={50}
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            placeholder="e.g. 3500"
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-600 dark:text-slate-400">Min bedrooms</span>
          <input
            type="number"
            min={0}
            value={minBedrooms}
            onChange={(e) => setMinBedrooms(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            placeholder="e.g. 2"
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-600 dark:text-slate-400">Min bathrooms</span>
          <input
            type="number"
            min={0}
            step={0.5}
            value={minBathrooms}
            onChange={(e) => setMinBathrooms(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            placeholder="e.g. 1"
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-600 dark:text-slate-400">Pets required</span>
          <select
            value={petsRequired === '' ? '' : petsRequired ? 'yes' : 'no'}
            onChange={(e) => {
              const v = e.target.value
              if (v === '') setPetsRequired('')
              else setPetsRequired(v === 'yes')
            }}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">No change</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </label>
      </div>

      {error ? (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400" role="alert">
          {error}
        </p>
      ) : null}

      <button
        type="button"
        onClick={() => void apply()}
        disabled={saving}
        className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
      >
        {saving ? 'Applying…' : 'Apply to current run'}
      </button>
    </section>
  )
}
