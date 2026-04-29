'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import clsx from 'clsx'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { Container } from '@/components/Container'
import { Button } from '@/components/Button'
import { HouseBuildingAnimation } from '@/components/HouseBuildingAnimation'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Preference {
  id: string
  description: string
  city: string
  api_provider: string
  has_openrouter_api_key: boolean
  openrouter_key_last4: string | null
  has_apify_api_token: boolean
  apify_token_last4: string | null
}

interface DiscoveryEvent {
  id: number
  message: string
  type: 'info' | 'success' | 'error' | 'progress' | 'warning'
  timestamp: string
}

interface RunLog {
  id: string
  sequence: number
  level: 'info' | 'success' | 'error' | 'debug' | 'warning'
  component: string
  message: string
  timestamp: string
}

interface DiscoveryRun {
  id: string
  city: string
  status: 'running' | 'success' | 'error'
  managers_found: number | null
  started_at: string
  finished_at: string | null
  logs: RunLog[]
}

interface PropertyManager {
  id: string
  city: string
  name: string
  website: string | null
  listing_page_url: string | null
  validated: boolean
}

interface Listing {
  id: string
  address: string
  price: number
  bedrooms: number
  bathrooms: number
  sqft: number | null
  pets_policy: string
  score: number | null
  score_explanation: string | null
  url: string | null
  saved: boolean
  property_manager_id: string
  validation_passed: boolean
}

interface ScrapeResult {
  city: string
  managers_scraped: number
  listings_extracted: number
  listings_scored: number
}

export default function Dashboard() {
  const [preferences, setPreferences] = useState<Preference[]>([])
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<DiscoveryEvent[]>([])
  const [health, setHealth] = useState<'ok' | 'down' | 'checking'>('checking')
  const [runs, setRuns] = useState<DiscoveryRun[]>([])
  const [expandedRun, setExpandedRun] = useState<string | null>(null)
  const [managers, setManagers] = useState<PropertyManager[]>([])
  const [listings, setListings] = useState<Listing[]>([])
  const [scraping, setScraping] = useState(false)
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const seenLogIdsRef = useRef<Set<string>>(new Set())

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
  }, [])

  const fetchManagers = useCallback((city: string) => {
    fetch(`${API}/api/discovery/cities/${encodeURIComponent(city)}/managers`)
      .then((r) => r.json())
      .then((data: PropertyManager[]) => setManagers(data))
      .catch(() => {})
  }, [])

  const fetchRuns = useCallback(() => {
    fetch(`${API}/api/discovery/runs`)
      .then((r) => r.json())
      .then(setRuns)
      .catch(() => {})
  }, [])

  const fetchListings = useCallback((city: string) => {
    fetch(`${API}/api/listings?city=${encodeURIComponent(city)}&limit=50&offset=0`)
      .then((r) => r.json())
      .then((data: Listing[]) => setListings(data))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(() => setHealth('ok'))
      .catch(() => setHealth('down'))

    fetch(`${API}/api/preferences`)
      .then((r) => r.json())
      .then((prefs: Preference[]) => {
        setPreferences(prefs)
        if (prefs[0]?.city) {
          fetchManagers(prefs[0].city)
          fetchListings(prefs[0].city)
        }
      })
      .catch(() => {})

    fetchRuns()
  }, [fetchManagers, fetchRuns, fetchListings])

  const addEvent = useCallback(
    (message: string, type: DiscoveryEvent['type'] = 'info') => {
      setEvents((prev) => [
        ...prev,
        { id: Date.now(), message, type, timestamp: new Date().toLocaleTimeString() },
      ])
    },
    [],
  )

  const levelToType = (level: RunLog['level']): DiscoveryEvent['type'] => {
    if (level === 'success') return 'success'
    if (level === 'error') return 'error'
    if (level === 'warning') return 'warning'
    if (level === 'debug') return 'info'
    return 'info'
  }

  const startPolling = useCallback(
    (runId: string, city: string) => {
      seenLogIdsRef.current = new Set()
      pollIntervalRef.current = setInterval(async () => {
        try {
          const resp = await fetch(`${API}/api/discovery/runs/${runId}`)
          if (!resp.ok) return
          const run: DiscoveryRun = await resp.json()

          const newLogs = run.logs.filter((l) => !seenLogIdsRef.current.has(l.id))
          newLogs.forEach((l) => seenLogIdsRef.current.add(l.id))

          if (newLogs.length > 0) {
            const now = Date.now()
            setEvents((prev) => [
              ...prev,
              ...newLogs.map((log, i) => ({
                id: now + i,
                message: `[${log.component}] ${log.message}`,
                type: levelToType(log.level),
                timestamp: new Date(log.timestamp).toLocaleTimeString(),
              })),
            ])
          }

          if (run.status !== 'running') {
            stopPolling()
            setRunning(false)
            fetchRuns()
            fetchManagers(city)
            fetchListings(city)
          }
        } catch {
          // transient network error — keep polling
        }
      }, 2000)
    },
    [stopPolling, fetchRuns, fetchManagers, fetchListings],
  )

  const runDiscovery = async () => {
    if (preferences.length === 0) {
      addEvent('No preferences configured. Go to Preferences first.', 'error')
      return
    }

    const pref = preferences[0]
    if (!pref.has_openrouter_api_key) {
      addEvent('No OpenRouter API key configured. Go to Preferences to add one.', 'error')
      return
    }

    stopPolling()
    setRunning(true)
    setEvents([])
    addEvent(`Starting discovery for "${pref.city}"…`, 'info')

    try {
      const resp = await fetch(`${API}/api/discovery/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city: pref.city, preference_id: pref.id }),
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }))
        addEvent(`Discovery failed: ${err.detail || resp.statusText}`, 'error')
        setRunning(false)
        return
      }

      const data: DiscoveryRun = await resp.json()
      startPolling(data.id, pref.city)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      addEvent(`Network error: ${msg}`, 'error')
      setRunning(false)
    }
  }

  const handleCancel = () => {
    stopPolling()
    setRunning(false)
    addEvent('Discovery polling stopped. Backend run may still be in progress.', 'warning')
    fetchRuns()
  }

  const scrapeListings = async () => {
    const activePref = preferences[0]
    if (!activePref) return
    setScraping(true)
    addEvent(`Scraping listings for property managers in ${activePref.city}…`, 'info')
    try {
      const resp = await fetch(
        `${API}/api/discovery/cities/${encodeURIComponent(activePref.city)}/scrape`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ preference_id: activePref.id }),
        },
      )
      if (resp.ok) {
        const result: ScrapeResult = await resp.json()
        addEvent(
          `Scraped ${result.managers_scraped} managers → ${result.listings_extracted} listings extracted, ${result.listings_scored} scored`,
          result.listings_extracted > 0 ? 'success' : 'warning',
        )
        fetchListings(activePref.city)
      } else {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }))
        addEvent(`Scrape failed: ${err.detail || resp.statusText}`, 'error')
      }
    } catch (e: unknown) {
      addEvent(`Scrape error: ${e instanceof Error ? e.message : String(e)}`, 'error')
    }
    setScraping(false)
  }

  const toggleSaved = async (listingId: string, currentSaved: boolean) => {
    setListings((prev) =>
      prev.map((l) => (l.id === listingId ? { ...l, saved: !currentSaved } : l)),
    )
    try {
      await fetch(`${API}/api/listings/${listingId}/save`, { method: 'POST' })
    } catch {
      setListings((prev) =>
        prev.map((l) => (l.id === listingId ? { ...l, saved: currentSaved } : l)),
      )
    }
  }

  const pref = preferences[0]

  return (
    <>
      <Header />
      <main className="flex-1">
        <Container className="pt-12 pb-20">
          <div className="mx-auto max-w-3xl">

            {/* Dashboard header */}
            <div className="mb-10">
              <p className="text-xs font-medium tracking-widest text-slate-400 uppercase dark:text-slate-500">
                Dashboard
              </p>
              <h1 className="mt-1 font-display text-3xl font-medium tracking-tight text-slate-900 dark:text-slate-100">
                {pref ? `Finding rentals in ${pref.city}` : 'Get started'}
              </h1>
              {pref?.description ? (
                <p className="mt-2 max-w-xl text-base text-slate-500 line-clamp-2 dark:text-slate-400">
                  {pref.description}
                </p>
              ) : (
                <p className="mt-2 text-base text-slate-500 dark:text-slate-400">
                  <a href="/preferences" className="text-blue-600 hover:underline dark:text-blue-400">
                    Configure your preferences
                  </a>{' '}
                  to run your first discovery.
                </p>
              )}
            </div>

            {/* Status strip */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatusCard
                label="Backend"
                value={
                  health === 'ok' ? 'Connected' : health === 'down' ? 'Offline' : 'Checking…'
                }
                indicator={health}
              />
              <StatusCard label="Search city" value={pref?.city ?? 'Not set'} muted={!pref} />
              <StatusCard
                label="API key"
                value={
                  pref?.has_openrouter_api_key
                    ? `••••${pref.openrouter_key_last4 ?? ''}`
                    : 'Not configured'
                }
                muted={!pref?.has_openrouter_api_key}
              />
            </div>

            {/* Run action */}
            <div className="mt-10 flex items-center justify-center gap-x-3">
              <Button
                color="blue"
                onClick={runDiscovery}
                disabled={running || health !== 'ok'}
                className="px-8"
              >
                {running ? (
                  <>
                    <Spinner />
                    Running discovery…
                  </>
                ) : (
                  'Run discovery'
                )}
              </Button>
              {running && (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                >
                  Stop waiting
                </button>
              )}
            </div>

            {/* House building animation — shown while running */}
            {running && (
              <div className="mt-10 overflow-hidden rounded-2xl border border-slate-200 bg-white px-5 py-8 dark:border-slate-800 dark:bg-slate-950">
                <HouseBuildingAnimation />
              </div>
            )}

            {/* Discovery log */}
            <div className={clsx('overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800', running ? 'mt-4' : 'mt-10')}>
              <div className="border-b border-slate-200 bg-slate-50 px-5 py-3 dark:border-slate-800 dark:bg-slate-900">
                <span className="text-xs font-medium tracking-widest text-slate-400 uppercase dark:text-slate-500">
                  Discovery log
                </span>
              </div>
              <div className="min-h-28 bg-white px-5 py-4 dark:bg-slate-950">
                {events.length === 0 ? (
                  <p className="text-sm text-slate-400 dark:text-slate-600">
                    Output will appear here when you run a discovery.
                  </p>
                ) : (
                  <div className="space-y-1.5 font-mono text-sm">
                    {events.map((evt) => (
                      <div
                        key={evt.id}
                        className={clsx(
                          'flex items-start gap-x-3',
                          evt.type === 'error' && 'text-red-600 dark:text-red-400',
                          evt.type === 'success' && 'text-green-600 dark:text-green-400',
                          evt.type === 'info' && 'text-slate-600 dark:text-slate-300',
                          evt.type === 'progress' && 'text-blue-600 dark:text-blue-400',
                          evt.type === 'warning' && 'text-amber-600 dark:text-amber-400',
                        )}
                      >
                        <span className="shrink-0 tabular-nums text-slate-400 dark:text-slate-600">
                          {evt.timestamp}
                        </span>
                        <span>
                          {evt.message}
                          {evt.type === 'warning' && (
                            <a href="/preferences" className="ml-2 underline hover:no-underline">
                              → Go to Preferences
                            </a>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Discovered property managers */}
            {managers.length > 0 && (
              <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
                <div className="border-b border-slate-200 bg-slate-50 px-5 py-3 dark:border-slate-800 dark:bg-slate-900">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium tracking-widest text-slate-400 uppercase dark:text-slate-500">
                      Property managers
                    </span>
                    <div className="flex items-center gap-x-3">
                      <span className="text-xs text-slate-400 dark:text-slate-600">
                        {managers.length} found in {pref?.city}
                      </span>
                      <button
                        type="button"
                        onClick={scrapeListings}
                        disabled={scraping || running}
                        className="flex items-center gap-x-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed dark:bg-blue-500 dark:hover:bg-blue-600"
                      >
                        {scraping ? (
                          <>
                            <Spinner />
                            Scraping…
                          </>
                        ) : (
                          'Scrape listings'
                        )}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-950">
                  {managers.map((mgr) => (
                    <div key={mgr.id} className="flex items-center justify-between gap-x-4 px-5 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
                          {mgr.name}
                        </p>
                        {mgr.website && (
                          <a
                            href={mgr.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="truncate text-xs text-blue-600 hover:underline dark:text-blue-400"
                          >
                            {mgr.website.replace(/^https?:\/\//, '')}
                          </a>
                        )}
                      </div>
                      {mgr.validated && (
                        <span className="shrink-0 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
                          validated
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Listings */}
            {listings.length > 0 && (
              <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
                <div className="border-b border-slate-200 bg-slate-50 px-5 py-3 dark:border-slate-800 dark:bg-slate-900">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium tracking-widest text-slate-400 uppercase dark:text-slate-500">
                      Listings
                    </span>
                    <span className="text-xs text-slate-400 dark:text-slate-600">
                      {listings.length} found
                    </span>
                  </div>
                </div>
                <div className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-950">
                  {listings.map((listing) => (
                    <ListingCard
                      key={listing.id}
                      listing={listing}
                      onToggleSaved={toggleSaved}
                    />
                  ))}
                </div>
              </div>
            )}

            {managers.length > 0 && listings.length === 0 && !scraping && (
              <div className="mt-6 rounded-2xl border-2 border-dashed border-slate-200 px-8 py-8 text-center dark:border-slate-700">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">No listings yet</p>
                <p className="mt-1 text-sm text-slate-400 dark:text-slate-500">
                  Hit <strong>Scrape listings</strong> above to extract listings from discovered property managers.
                </p>
              </div>
            )}

            {/* Run history */}
            {runs.length > 0 ? (
              <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
                <div className="border-b border-slate-200 bg-slate-50 px-5 py-3 dark:border-slate-800 dark:bg-slate-900">
                  <span className="text-xs font-medium tracking-widest text-slate-400 uppercase dark:text-slate-500">
                    Run history
                  </span>
                </div>
                <div className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-950">
                  {runs.slice(0, 5).map((run) => (
                    <RunHistoryRow
                      key={run.id}
                      run={run}
                      expanded={expandedRun === run.id}
                      onToggle={() => setExpandedRun(expandedRun === run.id ? null : run.id)}
                    />
                  ))}
                </div>
              </div>
            ) : pref && !running ? (
              <div className="mt-6 rounded-2xl border-2 border-dashed border-slate-200 px-8 py-10 text-center dark:border-slate-700">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">No runs yet</p>
                <p className="mt-1 text-sm text-slate-400 dark:text-slate-500">
                  Hit <strong>Run discovery</strong> above to find property managers in {pref.city}.
                </p>
              </div>
            ) : null}

          </div>
        </Container>
      </main>
      <Footer />
    </>
  )
}

function StatusCard({
  label,
  value,
  indicator,
  muted,
}: {
  label: string
  value: string
  indicator?: 'ok' | 'down' | 'checking'
  muted?: boolean
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-xs font-medium tracking-widest text-slate-400 uppercase dark:text-slate-500">
        {label}
      </p>
      <div className="mt-2 flex items-center gap-x-2">
        {indicator && (
          <span
            className={clsx(
              'h-2 w-2 shrink-0 rounded-full',
              indicator === 'ok' && 'bg-green-500',
              indicator === 'down' && 'bg-red-500',
              indicator === 'checking' && 'bg-amber-400 motion-safe:animate-pulse',
            )}
            aria-hidden="true"
          />
        )}
        <p
          className={clsx(
            'text-base font-semibold',
            muted
              ? 'text-slate-400 dark:text-slate-600'
              : 'text-slate-900 dark:text-slate-100',
          )}
        >
          {value}
        </p>
      </div>
    </div>
  )
}

function Spinner() {
  return (
    <svg
      className="-ml-1 mr-2 h-4 w-4 motion-safe:animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color =
    score >= 0.7
      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
      : score >= 0.4
        ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
        : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  return (
    <span className={clsx('shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums', color)}>
      {pct}%
    </span>
  )
}

function ListingCard({
  listing,
  onToggleSaved,
}: {
  listing: Listing
  onToggleSaved: (id: string, currentSaved: boolean) => void
}) {
  const petsLabel: Record<string, string> = {
    allowed_with_small_dog: 'Small dogs ok',
    cats_only: 'Cats only',
    none_allowed: 'No pets',
    unknown: '',
  }

  return (
    <div className="px-5 py-4">
      <div className="flex items-start justify-between gap-x-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {listing.score != null && <ScoreBadge score={listing.score} />}
            <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
              {listing.address}
            </p>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500 dark:text-slate-400">
            {listing.price > 0 && (
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                ${listing.price.toLocaleString()}/mo
              </span>
            )}
            {listing.bedrooms > 0 && (
              <span>{listing.bedrooms} bd</span>
            )}
            {listing.bathrooms > 0 && (
              <span>{listing.bathrooms} ba</span>
            )}
            {listing.sqft && (
              <span>{listing.sqft.toLocaleString()} sqft</span>
            )}
            {listing.pets_policy && petsLabel[listing.pets_policy] && (
              <span>{petsLabel[listing.pets_policy]}</span>
            )}
          </div>
          {listing.score_explanation && (
            <p className="mt-1.5 text-xs text-slate-400 line-clamp-2 dark:text-slate-500">
              {listing.score_explanation}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-x-2">
          {listing.url && (
            <a
              href={listing.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:underline dark:text-blue-400"
            >
              View
            </a>
          )}
          <button
            type="button"
            onClick={() => onToggleSaved(listing.id, listing.saved)}
            aria-label={listing.saved ? 'Unsave listing' : 'Save listing'}
            className={clsx(
              'rounded-lg px-2.5 py-1 text-xs font-medium transition-colors',
              listing.saved
                ? 'bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-400 dark:hover:bg-blue-900/60'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700',
            )}
          >
            {listing.saved ? 'Saved' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

function RunHistoryRow({
  run,
  expanded,
  onToggle,
}: {
  run: DiscoveryRun
  expanded: boolean
  onToggle: () => void
}) {
  const statusColors = {
    success: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    error: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    running: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  }

  const date = new Date(run.started_at)
  const timeStr = date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })

  return (
    <div>
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-5 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-900"
      >
        <div className="flex items-center gap-x-3">
          <span
            className={clsx(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              statusColors[run.status],
            )}
          >
            {run.status}
          </span>
          <span className="text-sm text-slate-700 dark:text-slate-300">{run.city}</span>
          {run.managers_found != null && (
            <span className="text-xs text-slate-400 dark:text-slate-600">
              {run.managers_found} managers
            </span>
          )}
        </div>
        <div className="flex items-center gap-x-3">
          <span className="text-xs text-slate-400 dark:text-slate-600">{timeStr}</span>
          <svg
            className={clsx(
              'h-4 w-4 text-slate-400 motion-safe:transition-transform',
              expanded && 'rotate-180',
            )}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>
      {expanded && run.logs.length > 0 && (
        <div className="border-t border-slate-100 bg-slate-50 px-5 py-3 dark:border-slate-800 dark:bg-slate-900">
          <div className="space-y-1 font-mono text-xs">
            {run.logs.map((log) => (
              <div
                key={log.id}
                className={clsx(
                  'flex gap-x-3',
                  log.level === 'error' && 'text-red-600 dark:text-red-400',
                  log.level === 'success' && 'text-green-600 dark:text-green-400',
                  log.level === 'warning' && 'text-amber-600 dark:text-amber-400',
                  log.level === 'debug' && 'text-slate-400 dark:text-slate-600',
                  (log.level === 'info' || !log.level) && 'text-slate-600 dark:text-slate-300',
                )}
              >
                <span className="shrink-0 text-slate-400 dark:text-slate-600">
                  [{log.component}]
                </span>
                <span>{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
