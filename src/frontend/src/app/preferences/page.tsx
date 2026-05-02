'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import Link from 'next/link'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { Container } from '@/components/Container'
import { Button } from '@/components/Button'
import { PreferencePromptsPanel } from '@/components/preferences/PreferencePromptsPanel'
import { TextField, SelectField } from '@/components/Fields'
import {
  CTX_FILTERS,
  SORTS,
  TIERS,
  fmtContext,
  fmtPrice,
  getTier,
  matchesCtx,
  pill, pillOff, pillOn,
  roleBtn, roleBtnOff, roleBtnOn, tierColors,
  type CtxFilter,
  type ModelInfo,
  type Preference,
  type SortBy,
  type TierFilter,
} from './model-utils'

interface SystemConfig {
  has_openrouter_key: boolean
  openrouter_key_last4: string | null
  has_apify_token: boolean
  apify_token_last4: string | null
}

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function ModelChip({
  label,
  hint,
  model,
  onClear,
}: {
  label: string
  hint: string
  model: ModelInfo | undefined
  onClear: () => void
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/50">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
          {label}
        </span>
        {model && (
          <button
            type="button"
            onClick={onClear}
            aria-label={`Remove ${label}`}
            className="rounded p-0.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        )}
      </div>
      {model ? (
        <div className="mt-1.5">
          <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
            {model.name}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-400 dark:text-slate-500">
            <span className="tabular-nums">{fmtPrice(model.prompt_price)}/1M in</span>
            <span aria-hidden="true">·</span>
            <span>{fmtContext(model.context_length)} ctx</span>
          </div>
        </div>
      ) : (
        <p className="mt-1.5 text-sm text-slate-400 dark:text-slate-500">{hint}</p>
      )}
    </div>
  )
}

function ModelRow({
  model,
  isFast,
  isSmart,
  onSetFast,
  onSetSmart,
}: {
  model: ModelInfo
  isFast: boolean
  isSmart: boolean
  onSetFast: () => void
  onSetSmart: () => void
}) {
  const tier = getTier(model.prompt_price)
  const highlighted = isFast || isSmart
  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 transition-colors ${
        highlighted
          ? 'bg-blue-50 dark:bg-blue-950/20'
          : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
      }`}
      role="listitem"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span
            className={`truncate text-sm font-medium ${
              highlighted
                ? 'text-blue-800 dark:text-blue-300'
                : 'text-slate-800 dark:text-slate-200'
            }`}
          >
            {model.name}
          </span>
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${tierColors[tier]}`}>
            {tier}
          </span>
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0 text-xs text-slate-400 dark:text-slate-500">
          <span>{model.provider}</span>
          <span aria-hidden="true">·</span>
          <span className="tabular-nums">{fmtContext(model.context_length)} ctx</span>
          <span aria-hidden="true">·</span>
          <span className="tabular-nums">
            {fmtPrice(model.prompt_price)} in / {fmtPrice(model.completion_price)} out
          </span>
        </div>
      </div>
      <div className="flex shrink-0 gap-1.5">
        <button
          type="button"
          onClick={onSetFast}
          aria-pressed={isFast}
          className={`${roleBtn} ${isFast ? roleBtnOn : roleBtnOff}`}
        >
          Fast
        </button>
        <button
          type="button"
          onClick={onSetSmart}
          aria-pressed={isSmart}
          className={`${roleBtn} ${isSmart ? roleBtnOn : roleBtnOff}`}
        >
          Smart
        </button>
      </div>
    </div>
  )
}

function ModelPicker({
  allModels,
  fastModel,
  smartModel,
  onFastChange,
  onSmartChange,
}: {
  allModels: ModelInfo[]
  fastModel: string
  smartModel: string
  onFastChange: (id: string) => void
  onSmartChange: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [tierFilter, setTierFilter] = useState<TierFilter>('All')
  const [providerFilter, setProviderFilter] = useState('All')
  const [ctxFilter, setCtxFilter] = useState<CtxFilter>('Any')
  const [sortBy, setSortBy] = useState<SortBy>('Cheapest')
  const searchRef = useRef<HTMLInputElement>(null)

  const providers = useMemo(
    () => Array.from(new Set(allModels.map((m) => m.provider))).sort(),
    [allModels],
  )

  const filtered = useMemo(() => {
    let list = allModels
    if (tierFilter !== 'All') list = list.filter((m) => getTier(m.prompt_price) === tierFilter)
    if (providerFilter !== 'All') list = list.filter((m) => m.provider === providerFilter)
    if (ctxFilter !== 'Any') list = list.filter((m) => matchesCtx(m.context_length, ctxFilter))
    if (query) {
      const q = query.toLowerCase()
      list = list.filter(
        (m) =>
          m.name.toLowerCase().includes(q) ||
          m.id.toLowerCase().includes(q) ||
          m.provider.toLowerCase().includes(q),
      )
    }
    return list
  }, [allModels, tierFilter, providerFilter, ctxFilter, query])

  const sorted = useMemo(() => {
    const list = [...filtered]
    if (sortBy === 'Largest ctx') return list.sort((a, b) => b.context_length - a.context_length)
    if (sortBy === 'Name A-Z') return list.sort((a, b) => a.name.localeCompare(b.name))
    return list.sort((a, b) => a.prompt_price - b.prompt_price)
  }, [filtered, sortBy])

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => searchRef.current?.focus(), 50)
      return () => clearTimeout(t)
    }
  }, [open])

  const fastInfo = allModels.find((m) => m.id === fastModel)
  const smartInfo = allModels.find((m) => m.id === smartModel)

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ModelChip
          label="Fast model"
          hint="Pick a cheap model that runs frequently"
          model={fastInfo}
          onClear={() => onFastChange('')}
        />
        <ModelChip
          label="Smart model"
          hint="Pick a powerful model for complex tasks"
          model={smartInfo}
          onClear={() => onSmartChange('')}
        />
      </div>

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
      >
        <svg
          className="h-4 w-4 text-slate-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803 7.5 7.5 0 0016.803 15.803z"
          />
        </svg>
        {open ? 'Close browser' : 'Browse models'}
        <span className="text-xs text-slate-400">({allModels.length})</span>
      </button>

      {open && (
        <div className="rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
          {(fastModel || smartModel) && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-t-xl border-b border-blue-100 bg-blue-50 px-4 py-2.5 dark:border-blue-900/30 dark:bg-blue-950/20">
              {fastModel && fastInfo && (
                <span className="flex items-center gap-1.5 text-xs text-blue-700 dark:text-blue-300">
                  <span className="font-semibold">Fast:</span>
                  <span className="max-w-[200px] truncate">{fastInfo.name}</span>
                </span>
              )}
              {smartModel && smartInfo && (
                <span className="flex items-center gap-1.5 text-xs text-blue-700 dark:text-blue-300">
                  <span className="font-semibold">Smart:</span>
                  <span className="max-w-[200px] truncate">{smartInfo.name}</span>
                </span>
              )}
            </div>
          )}
          <div className="flex flex-col gap-3 border-b border-slate-100 p-4 dark:border-slate-800 sm:flex-row sm:items-center">
            <div className="relative min-w-0 flex-1">
              <svg
                className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803 7.5 7.5 0 0016.803 15.803z"
                />
              </svg>
              <input
                ref={searchRef}
                type="search"
                aria-label="Search models"
                placeholder="Search by name, ID, or provider…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-8 pr-3 text-sm text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:placeholder-slate-500 dark:focus:bg-slate-800"
              />
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <span className="text-xs text-slate-400">Sort:</span>
              {SORTS.map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={sortBy === s}
                  onClick={() => setSortBy(s)}
                  className={`rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    sortBy === s
                      ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                      : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-3 border-b border-slate-100 p-4 dark:border-slate-800">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 w-14 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Tier
              </span>
              <div className="flex flex-wrap gap-1.5">
                {TIERS.map((t) => (
                  <button
                    key={t}
                    type="button"
                    aria-pressed={tierFilter === t}
                    onClick={() => setTierFilter(t)}
                    className={`${pill} ${tierFilter === t ? pillOn : pillOff}`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-start gap-3">
              <span className="mt-0.5 w-14 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Provider
              </span>
              <div className="flex flex-wrap gap-1.5">
                {['All', ...providers].map((p) => (
                  <button
                    key={p}
                    type="button"
                      aria-pressed={providerFilter === p}
                    onClick={() => setProviderFilter(p)}
                    className={`${pill} ${providerFilter === p ? pillOn : pillOff}`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-start gap-3">
              <span className="mt-0.5 w-14 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Context
              </span>
              <div className="flex flex-wrap gap-1.5">
                {CTX_FILTERS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-pressed={ctxFilter === c}
                    onClick={() => setCtxFilter(c)}
                    className={`${pill} ${ctxFilter === c ? pillOn : pillOff}`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="px-4 py-2 text-xs text-slate-400 dark:text-slate-500">
            {sorted.length === 0
              ? 'No models match — try different filters.'
              : `${sorted.length} of ${allModels.length} models`}
          </div>

          <div
            className="max-h-[28rem] divide-y divide-slate-100 overflow-y-auto dark:divide-slate-800"
            role="list"
            aria-label="Available models"
          >
            {sorted.length === 0 ? (
              <div className="px-4 py-10 text-center text-sm text-slate-400 dark:text-slate-500">
                No models match your current filters.
              </div>
            ) : (
              sorted.map((model) => (
                <ModelRow
                  key={model.id}
                  model={model}
                  isFast={fastModel === model.id}
                  isSmart={smartModel === model.id}
                  onSetFast={() => onFastChange(model.id)}
                  onSetSmart={() => onSmartChange(model.id)}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function PreferencesPage() {
  const [preferences, setPreferences] = useState<Preference[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const [city, setCity] = useState('')
  const [description, setDescription] = useState('')
  const [apiProvider, setApiProvider] = useState('openrouter')
  const [openrouterKey, setOpenrouterKey] = useState('')
  const [apifyToken, setApifyToken] = useState('')
  const [removeOpenrouterKey, setRemoveOpenrouterKey] = useState(false)
  const [removeApifyToken, setRemoveApifyToken] = useState(false)
  const [sourcesEnabled, setSourcesEnabled] = useState<string[]>(['craigslist'])
  const [fastModel, setFastModel] = useState('')
  const [smartModel, setSmartModel] = useState('')
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [fetchedModels, setFetchedModels] = useState(false)
  const [systemConfig, setSystemConfig] = useState<SystemConfig | null>(null)
  const [missingTrustedClRegion, setMissingTrustedClRegion] = useState(false)

  const activePreference = preferences[0]
  const canFetchModels =
    openrouterKey.length >= 20 ||
    (!!activePreference?.has_openrouter_api_key && !removeOpenrouterKey) ||
    (!!systemConfig?.has_openrouter_key && !removeOpenrouterKey)

  useEffect(() => {
    // Fetch system config (defaults from .env)
    fetch(`${API}/api/config`)
      .then((r) => r.json())
      .then((data) => setSystemConfig(data))
      .catch(() => {})

    fetch(`${API}/api/preferences`)
      .then((r) => r.json())
      .then((data: Preference[]) => {
        setPreferences(data)
        if (data.length > 0) {
          const p = data[0]
          setCity(p.city)
          setDescription(p.description)
          setApiProvider(p.api_provider)
          setOpenrouterKey('')
          setApifyToken('')
          setFastModel(p.fast_model || '')
          setSmartModel(p.smart_model || '')
          setSourcesEnabled(p.sources_enabled?.length ? p.sources_enabled : ['craigslist'])
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const prefCity = (city.trim() || activePreference?.city || '').trim()
    if (!prefCity || !sourcesEnabled.includes('craigslist')) {
      queueMicrotask(() => setMissingTrustedClRegion(false))
      return
    }
    const q = encodeURIComponent(prefCity)
    fetch(`${API}/api/trusted-sources?kind=craigslist_region&city=${q}`)
      .then((r) => r.json())
      .then((rows: unknown) => {
        const ok = Array.isArray(rows) && rows.length > 0
        queueMicrotask(() => setMissingTrustedClRegion(!ok))
      })
      .catch(() => {
        queueMicrotask(() => setMissingTrustedClRegion(false))
      })
  }, [city, activePreference?.city, activePreference?.id, sourcesEnabled])

  const resetLoadedModels = () => {
    setAvailableModels([])
    setFetchedModels(false)
  }

  const handleLoadModels = async () => {
    if (!canFetchModels) return
    setLoadingModels(true)
    setFetchedModels(false)
    try {
      const resp = await fetch(`${API}/api/openrouter/models`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: openrouterKey.trim() || undefined,
          preference_id: activePreference?.id,
          curated: false,
        }),
      })
      if (!resp.ok) throw new Error('Could not load models')
      const data: unknown = await resp.json()
      setAvailableModels(Array.isArray(data) ? (data as ModelInfo[]) : [])
    } catch {
      setAvailableModels([])
    } finally {
      setLoadingModels(false)
      setFetchedModels(true)
    }
  }

  useEffect(() => {
    if (message?.type === 'success') {
      const t = setTimeout(() => setMessage(null), 3000)
      return () => clearTimeout(t)
    }
  }, [message])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      const body: Record<string, unknown> = {
        city,
        description,
        api_provider: apiProvider,
        fast_model: fastModel || null,
        smart_model: smartModel || null,
        sources_enabled: sourcesEnabled,
      }
      if (openrouterKey.trim()) {
        body.openrouter_api_key = openrouterKey.trim()
      } else if (removeOpenrouterKey) {
        body.openrouter_api_key = null
      }
      // If no key provided and no active preference exists, we leave it out 
      // so it falls back to the system key in the backend.

      if (apifyToken.trim()) {
        body.apify_api_token = apifyToken.trim()
      } else if (removeApifyToken) {
        body.apify_api_token = null
      }
      let resp: Response
      if (preferences.length > 0) {
        resp = await fetch(`${API}/api/preferences/${preferences[0].id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      } else {
        resp = await fetch(`${API}/api/preferences`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      }
      if (resp.ok) {
        const updated = await resp.json()
        setPreferences([updated])
        setOpenrouterKey('')
        setApifyToken('')
        setRemoveOpenrouterKey(false)
        setRemoveApifyToken(false)
        setMessage({ text: 'Preferences saved!', type: 'success' })
      } else {
        const err = await resp.json().catch(() => ({}))
        const detail: string = err.detail || resp.statusText
        const msg = detail.toLowerCase().includes('secret_key')
          ? 'Backend is missing SECRET_KEY. Add SECRET_KEY=any-random-string to your .env file and restart the server.'
          : `Failed: ${detail}`
        setMessage({ text: msg, type: 'error' })
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setMessage({ text: `Error: ${msg}`, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <>
        <Header />
        <main className="flex flex-1 items-center justify-center">
          <p className="text-slate-500">Loading…</p>
        </main>
        <Footer />
      </>
    )
  }

  return (
    <>
      <Header />
      <main className="flex-1">
        <Container className="py-16">
          <div className="mx-auto max-w-2xl">
            <h1 className="font-display text-3xl font-medium tracking-tight text-slate-900 dark:text-slate-100">
              Preferences
            </h1>
            <p className="mt-2 text-lg text-slate-600 dark:text-slate-400">
              Configure your search criteria and API keys.
            </p>

            <form onSubmit={handleSave} className="mt-10 space-y-10">
              <fieldset>
                <legend className="font-display text-xl font-medium text-slate-900 dark:text-slate-100">
                  Search Preferences
                </legend>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  What are you looking for and where?
                </p>
                <div className="mt-6 space-y-6">
                  <TextField
                    label="City"
                    name="city"
                    placeholder="e.g. Austin, TX"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    required
                  />
                  <div>
                    <label
                      htmlFor="description"
                      className="mb-3 block text-sm font-medium text-slate-700 dark:text-slate-300"
                    >
                      Description
                    </label>
                    <textarea
                      id="description"
                      name="description"
                      rows={4}
                      className="block w-full appearance-none rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder-slate-500 sm:text-sm"
                      placeholder="e.g. 2BR pet-friendly apartment under $2000 near downtown"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </fieldset>

              <fieldset>
                <legend className="font-display text-xl font-medium text-slate-900 dark:text-slate-100">
                  API Configuration
                </legend>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Configure your LLM provider and API keys. Keys are stored locally.
                </p>
                <div className="mt-6 space-y-6">
                  <SelectField
                    label="API Provider"
                    name="api_provider"
                    value={apiProvider}
                    onChange={(e) => setApiProvider(e.target.value)}
                  >
                    <option value="openrouter">OpenRouter</option>
                  </SelectField>

                  <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                    Required for discovery
                  </p>
                  <TextField
                    label="OpenRouter API Key"
                    name="openrouter_api_key"
                    type="password"
                    placeholder={
                      openrouterKey.length > 0
                        ? ''
                        : activePreference?.has_openrouter_api_key
                        ? 'Leave blank to keep existing key'
                        : systemConfig?.has_openrouter_key
                        ? `Auto-loaded from system (ends in ${systemConfig.openrouter_key_last4})`
                        : 'sk-or-v1-...'
                    }
                    value={openrouterKey}
                    onChange={(e) => {
                      setOpenrouterKey(e.target.value)
                      setRemoveOpenrouterKey(false)
                      resetLoadedModels()
                    }}
                  />
                  <div className="flex items-center justify-between">
                    <div className="flex gap-2">
                      {activePreference?.has_openrouter_api_key && !removeOpenrouterKey && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-green-50 px-2 py-1 text-[10px] font-medium text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-900/20 dark:text-green-400">
                          <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4.13-5.682z" clipRule="evenodd" />
                          </svg>
                          Profile Key Active
                        </span>
                      )}
                      {systemConfig?.has_openrouter_key && !activePreference?.has_openrouter_api_key && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10 dark:bg-blue-900/20 dark:text-blue-400">
                          <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" />
                            <path fillRule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                          </svg>
                          System Default Active
                        </span>
                      )}
                    </div>
                  </div>
                  {activePreference?.has_openrouter_api_key && (
                    <div className="-mt-4 flex items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
                      <p>
                        {removeOpenrouterKey
                          ? 'Stored key will be removed on save.'
                          : `Stored key ending in ${activePreference.openrouter_key_last4}. Enter a new key only if you want to replace it.`}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          setOpenrouterKey('')
                          setRemoveOpenrouterKey((value) => !value)
                          resetLoadedModels()
                        }}
                        className="min-h-[36px] shrink-0 rounded-md px-2 py-1 font-medium text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30"
                      >
                        {removeOpenrouterKey ? 'Keep key' : 'Remove key'}
                      </button>
                    </div>
                  )}

                  <p className="mt-6 text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
                    Optional
                  </p>
                  <TextField
                    label="Apify API Token (optional)"
                    name="apify_api_token"
                    type="password"
                    placeholder={
                      apifyToken.length > 0
                        ? ''
                        : activePreference?.has_apify_api_token
                        ? 'Leave blank to keep existing token'
                        : systemConfig?.has_apify_token
                        ? `Auto-loaded from system (ends in ${systemConfig.apify_token_last4})`
                        : 'apify_api_...'
                    }
                    value={apifyToken}
                    onChange={(e) => {
                      setApifyToken(e.target.value)
                      setRemoveApifyToken(false)
                    }}
                  />
                  <div className="flex items-center justify-between">
                    <div className="flex gap-2">
                      {activePreference?.has_apify_api_token && !removeApifyToken && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-green-50 px-2 py-1 text-[10px] font-medium text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-900/20 dark:text-green-400">
                          <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4.13-5.682z" clipRule="evenodd" />
                          </svg>
                          Profile Token Active
                        </span>
                      )}
                      {systemConfig?.has_apify_token && !activePreference?.has_apify_api_token && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10 dark:bg-blue-900/20 dark:text-blue-400">
                          <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" />
                            <path fillRule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                          </svg>
                          System Default Active
                        </span>
                      )}
                    </div>
                  </div>
                  {activePreference?.has_apify_api_token && (
                    <div className="-mt-4 flex items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
                      <p>
                        {removeApifyToken
                          ? 'Stored token will be removed on save.'
                          : `Stored token ending in ${activePreference.apify_token_last4}.`}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          setApifyToken('')
                          setRemoveApifyToken((value) => !value)
                        }}
                        className="min-h-[36px] shrink-0 rounded-md px-2 py-1 font-medium text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30"
                      >
                        {removeApifyToken ? 'Keep token' : 'Remove token'}
                      </button>
                    </div>
                  )}

                  {canFetchModels && (
                    <div className="border-t border-slate-200 pt-6 dark:border-slate-700">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                            Model selection
                          </p>
                          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                            Click Fast or Smart on any row to assign it. Fast runs frequently; Smart
                            handles complex tasks.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={handleLoadModels}
                          disabled={loadingModels}
                          className="min-h-[40px] shrink-0 rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900"
                        >
                          {loadingModels ? 'Loading...' : 'Load models'}
                        </button>
                      </div>

                      {loadingModels && (
                        <div className="mt-4 flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
                          <svg
                            className="h-3.5 w-3.5 motion-safe:animate-spin"
                            viewBox="0 0 24 24"
                            fill="none"
                            aria-hidden="true"
                          >
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                            />
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8v8z"
                            />
                          </svg>
                          Fetching models from OpenRouter…
                        </div>
                      )}

                      {!loadingModels && fetchedModels && availableModels.length === 0 && (
                        <p className="mt-4 text-xs text-red-500 dark:text-red-400">
                          Could not load models. Check your API key.
                        </p>
                      )}

                      {!loadingModels && availableModels.length > 0 && (
                        <div className="mt-5">
                          <ModelPicker
                            allModels={availableModels}
                            fastModel={fastModel}
                            smartModel={smartModel}
                            onFastChange={setFastModel}
                            onSmartChange={setSmartModel}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </fieldset>

              <fieldset>
                <legend className="text-sm font-semibold leading-6 text-slate-900 dark:text-white">
                  Listing sources
                </legend>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Choose which platforms to search. Zillow and Facebook require an Apify token.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {[
                    { id: 'craigslist', label: 'Craigslist', requiresApify: false },
                    { id: 'zillow', label: 'Zillow', requiresApify: true },
                    { id: 'facebook', label: 'Facebook Marketplace', requiresApify: true },
                  ].map(({ id, label, requiresApify }) => {
                    const active = sourcesEnabled.includes(id)
                    const needsToken = requiresApify && !apifyToken.trim() && !activePreference?.has_apify_api_token
                    return (
                      <button
                        key={id}
                        type="button"
                        disabled={needsToken}
                        title={needsToken ? 'Add an Apify token to enable this source' : undefined}
                        onClick={() =>
                          setSourcesEnabled((prev) =>
                            prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
                          )
                        }
                        className={[
                          'rounded-full border px-4 py-1.5 text-sm font-medium transition-colors',
                          active && !needsToken
                            ? 'border-blue-600 bg-blue-600 text-white dark:border-blue-500 dark:bg-blue-500'
                            : needsToken
                              ? 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-600'
                              : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-slate-500',
                        ].join(' ')}
                      >
                        {label}
                      </button>
                    )
                  })}
                </div>
                {missingTrustedClRegion && sourcesEnabled.includes('craigslist') ? (
                  <div
                    className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-100"
                    role="status"
                  >
                    Craigslist will auto-pick a regional site from your city name — which can be wrong for
                    ambiguous names (e.g. Lancaster).{' '}
                    <Link
                      href={(() => {
                        const raw = (city.trim() || activePreference?.city || '').trim()
                        const parts = raw
                          .split(',')
                          .map((s) => s.trim())
                          .filter(Boolean)
                        let c = raw
                        let s = 'CA'
                        if (parts.length >= 2) {
                          const last = parts[parts.length - 1]!
                          if (last.length === 2) {
                            c = parts.slice(0, -1).join(', ')
                            s = last.toUpperCase()
                          }
                        }
                        return `/sources?addRegion=1&city=${encodeURIComponent(c)}&state=${encodeURIComponent(s)}`
                      })()}
                      className="font-medium text-amber-900 underline dark:text-amber-200"
                    >
                      Confirm your Craigslist region
                    </Link>{' '}
                    under Trusted sources.
                  </div>
                ) : null}
              </fieldset>

              <div className="flex items-center justify-end gap-x-4">
                <div role="status" aria-live="polite" className="text-sm">
                  {message?.type === 'success' && (
                    <span className="font-medium text-green-600 dark:text-green-400">Saved</span>
                  )}
                  {message?.type === 'error' && (
                    <span className="text-red-600 dark:text-red-400">{message.text}</span>
                  )}
                </div>
                <Button type="submit" color="blue" disabled={saving}>
                  {saving ? 'Saving…' : 'Save Preferences'}
                </Button>
              </div>
            </form>

            {activePreference ? <PreferencePromptsPanel preferenceId={activePreference.id} /> : null}
          </div>
        </Container>
      </main>
      <Footer />
    </>
  )
}
