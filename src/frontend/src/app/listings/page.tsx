'use client'

import dynamic from 'next/dynamic'
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import clsx from 'clsx'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { Container } from '@/components/Container'
import { safeHttpUrl } from '@/lib/url'
import type { RunListingResult, SearchRun } from '@/client/search-runs'
import { fetchSearchRun, fetchSearchRunResults } from '@/client/search-runs'
import { FilterReasonList } from '@/components/runs/FilterReasonList'

const ListingMiniMap = dynamic(
  () => import('@/components/listings/ListingMiniMap').then((m) => m.ListingMiniMap),
  { ssr: false, loading: () => <div className="h-[5.5rem] w-[7.5rem] rounded-lg bg-slate-100 dark:bg-slate-800" /> },
)

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const CATEGORIES = [
  { key: 'great_match', label: 'Great matches' },
  { key: 'worth_a_look', label: 'Worth a look' },
  { key: 'near_miss', label: 'Near misses' },
  { key: 'filtered_out', label: 'Filtered out' },
] as const

const PETS_FILTER = [
  { value: '', label: 'Any pet policy' },
  { value: 'unknown', label: 'Unknown' },
  { value: 'allowed_with_small_dog', label: 'Pets (small dog+)' },
  { value: 'cats_only', label: 'Cats only' },
  { value: 'none_allowed', label: 'No pets' },
] as const

export type ListingDTO = {
  id: string
  address: string
  price: number
  bedrooms: number | null
  bathrooms: number | null
  sqft: number | null
  pets_policy: string
  url: string | null
  source: string
  score: number | null
  score_explanation: string | null
  validation_passed: boolean
  extraction_timestamp: string
  photos?: string[]
  latitude?: number | null
  longitude?: number | null
}

type ViewMode = 'table' | 'cards'

type SortKey = 'price' | 'bedrooms' | 'score' | 'address' | 'sqft'
type SortDir = 'asc' | 'desc'

function petLabel(policy: string): string {
  switch (policy) {
    case 'allowed_with_small_dog':
      return 'Pets OK'
    case 'cats_only':
      return 'Cats only'
    case 'none_allowed':
      return 'No pets'
    default:
      return '—'
  }
}

function scoreLabel(score: number | null): string {
  if (score == null) return '—'
  if (score <= 1) return `${Math.round(score * 100)}%`
  return `${Math.round(score)}/100`
}

function mapsLink(l: ListingDTO) {
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(l.address)}`
}

function listingsQueryFromSearchParams(sp: URLSearchParams): string {
  const q = new URLSearchParams()
  const keys = [
    'city',
    'min_price',
    'max_price',
    'min_bedrooms',
    'max_bedrooms',
    'min_bathrooms',
    'max_bathrooms',
    'pets_policy',
    'min_score',
    'limit',
    'offset',
  ] as const
  for (const k of keys) {
    const v = sp.get(k)
    if (v !== null && v.trim() !== '') q.set(k, v)
  }
  if (!q.has('limit')) q.set('limit', '200')
  return q.toString()
}

function listingMatchesClientFilters(l: ListingDTO, sp: URLSearchParams): boolean {
  const minP = sp.get('min_price')
  const maxP = sp.get('max_price')
  const minB = sp.get('min_bedrooms')
  const maxB = sp.get('max_bedrooms')
  const minBa = sp.get('min_bathrooms')
  const maxBa = sp.get('max_bathrooms')
  const pets = sp.get('pets_policy')
  const minS = sp.get('min_score')
  if (minP && l.price < Number(minP)) return false
  if (maxP && l.price > Number(maxP)) return false
  if (minB && (l.bedrooms == null || l.bedrooms < Number(minB))) return false
  if (maxB && (l.bedrooms == null || l.bedrooms > Number(maxB))) return false
  if (minBa && (l.bathrooms == null || l.bathrooms < Number(minBa))) return false
  if (maxBa && (l.bathrooms == null || l.bathrooms > Number(maxBa))) return false
  if (pets && l.pets_policy !== pets) return false
  if (minS && l.score != null && l.score < Number(minS)) return false
  return true
}

function sortListings(rows: ListingDTO[], key: SortKey, dir: SortDir): ListingDTO[] {
  const mul = dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const va = a[key]
    const vb = b[key]
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    if (typeof va === 'string' && typeof vb === 'string') return va.localeCompare(vb) * mul
    return (Number(va) - Number(vb)) * mul
  })
}

function ListingsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const runId = searchParams.get('run')
  const categoryParam = searchParams.get('category') ?? 'great_match'
  const view: ViewMode = searchParams.get('view') === 'cards' ? 'cards' : 'table'

  const [listings, setListings] = useState<ListingDTO[]>([])
  const [loading, setLoading] = useState(true)
  const [run, setRun] = useState<SearchRun | null>(null)
  const [runResults, setRunResults] = useState<RunListingResult[]>([])
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  const [runLoading, setRunLoading] = useState(false)
  const [coordPatch, setCoordPatch] = useState<Record<string, { lat: number; lon: number }>>({})
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const [filterDraft, setFilterDraft] = useState({
    city: '',
    min_price: '',
    max_price: '',
    min_bedrooms: '',
    max_bedrooms: '',
    min_bathrooms: '',
    max_bathrooms: '',
    pets_policy: '',
    min_score: '',
  })

  const activeCategory = CATEGORIES.some((c) => c.key === categoryParam)
    ? categoryParam
    : 'great_match'

  const syncDraftFromUrl = useCallback(() => {
    setFilterDraft({
      city: searchParams.get('city') ?? '',
      min_price: searchParams.get('min_price') ?? '',
      max_price: searchParams.get('max_price') ?? '',
      min_bedrooms: searchParams.get('min_bedrooms') ?? '',
      max_bedrooms: searchParams.get('max_bedrooms') ?? '',
      min_bathrooms: searchParams.get('min_bathrooms') ?? '',
      max_bathrooms: searchParams.get('max_bathrooms') ?? '',
      pets_policy: searchParams.get('pets_policy') ?? '',
      min_score: searchParams.get('min_score') ?? '',
    })
  }, [searchParams])

  useEffect(() => {
    syncDraftFromUrl()
  }, [syncDraftFromUrl])

  const loadAllListings = useCallback(() => {
    const qs = listingsQueryFromSearchParams(searchParams)
    setLoading(true)
    fetch(`${API}/api/listings?${qs}`)
      .then((r) => r.json())
      .then((data) => setListings(data.listings || data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [searchParams])

  useEffect(() => {
    if (runId) return
    loadAllListings()
  }, [runId, loadAllListings])

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    const boot = setTimeout(() => {
      if (!cancelled) setRunLoading(true)
    }, 0)
    const load = async () => {
      try {
        const [rRun, rListings, rRes] = await Promise.all([
          fetchSearchRun(runId),
          fetch(`${API}/api/listings?limit=300`).then((x) => x.json()),
          fetchSearchRunResults(runId, { category: activeCategory, limit: 200 }),
        ])
        if (cancelled) return
        setRun(rRun)
        const raw = rListings.listings || rListings || []
        setListings(Array.isArray(raw) ? raw : [])
        setRunResults(rRes)
      } catch {
        if (!cancelled) {
          setRun(null)
          setRunResults([])
        }
      } finally {
        if (!cancelled) setRunLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
      clearTimeout(boot)
    }
  }, [runId, activeCategory])

  const listingById = useMemo(() => new Map(listings.map((l) => [l.id, l])), [listings])

  const withCoords = useCallback(
    (l: ListingDTO): ListingDTO => {
      const p = coordPatch[l.id]
      if (!p) return l
      return { ...l, latitude: p.lat, longitude: p.lon }
    },
    [coordPatch],
  )

  const availableSources = useMemo(() => {
    const seen = new Set<string>()
    listings.forEach((l) => seen.add(l.source || 'pm_direct'))
    return Array.from(seen).sort()
  }, [listings])

  const filteredResults = useMemo(() => {
    let rr = runResults
    if (sourceFilter !== 'all') {
      rr = rr.filter((r) => {
        const listing = listingById.get(r.listing_id)
        return (listing?.source || 'pm_direct') === sourceFilter
      })
    }
    return rr.filter((r) => {
      const listing = listingById.get(r.listing_id)
      if (!listing) return true
      return listingMatchesClientFilters(listing, searchParams)
    })
  }, [runResults, sourceFilter, listingById, searchParams])

  const sortedGlobalListings = useMemo(() => {
    const filtered = listings.filter((l) => listingMatchesClientFilters(l, searchParams))
    return sortListings(filtered.map(withCoords), sortKey, sortDir)
  }, [listings, searchParams, sortKey, sortDir, withCoords])

  const setCategory = (key: string) => {
    if (!runId) return
    const u = new URLSearchParams(searchParams.toString())
    u.set('run', runId)
    u.set('category', key)
    router.replace(`/listings?${u.toString()}`)
  }

  const setView = (v: ViewMode) => {
    const u = new URLSearchParams(searchParams.toString())
    if (v === 'table') u.delete('view')
    else u.set('view', v)
    router.replace(`/listings?${u.toString()}`)
  }

  const applyFilters = (e: React.FormEvent) => {
    e.preventDefault()
    const u = new URLSearchParams(searchParams.toString())
    const fields: (keyof typeof filterDraft)[] = [
      'city',
      'min_price',
      'max_price',
      'min_bedrooms',
      'max_bedrooms',
      'min_bathrooms',
      'max_bathrooms',
      'pets_policy',
      'min_score',
    ]
    for (const f of fields) {
      const v = filterDraft[f].trim()
      if (v) u.set(f, v)
      else u.delete(f)
    }
    if (runId) u.set('run', runId)
    if (runId) u.set('category', activeCategory)
    router.replace(`/listings?${u.toString()}`)
  }

  const clearFilters = () => {
    const u = new URLSearchParams()
    if (runId) {
      u.set('run', runId)
      u.set('category', activeCategory)
    }
    if (view === 'cards') u.set('view', 'cards')
    router.replace(u.toString() ? `/listings?${u.toString()}` : '/listings')
  }

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(key)
      setSortDir(key === 'address' ? 'asc' : 'desc')
    }
  }

  const geocodeOne = async (listingId: string) => {
    const r = await fetch(`${API}/api/listings/${encodeURIComponent(listingId)}/geocode`, {
      method: 'POST',
    })
    if (!r.ok) return
    const j = (await r.json()) as ListingDTO
    if (j.latitude != null && j.longitude != null) {
      setCoordPatch((prev) => ({
        ...prev,
        [listingId]: { lat: j.latitude as number, lon: j.longitude as number },
      }))
    }
  }

  return (
    <>
      <Header />
      <main className="flex-1">
        <Container className="py-16">
          <div className="mx-auto max-w-6xl">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h1 className="font-display text-3xl font-medium tracking-tight text-slate-900 dark:text-slate-100">
                  Listings
                </h1>
                <p className="mt-2 text-lg text-slate-600 dark:text-slate-400">
                  Extracted and scored rental listings.
                </p>
              </div>
              <div className="flex gap-2 rounded-full border border-slate-200 p-1 dark:border-slate-700" role="group" aria-label="Layout">
                <button
                  type="button"
                  onClick={() => setView('table')}
                  className={clsx(
                    'rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
                    view === 'table'
                      ? 'bg-blue-600 text-white dark:bg-blue-500'
                      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
                  )}
                >
                  Table
                </button>
                <button
                  type="button"
                  onClick={() => setView('cards')}
                  className={clsx(
                    'rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
                    view === 'cards'
                      ? 'bg-blue-600 text-white dark:bg-blue-500'
                      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
                  )}
                >
                  Cards
                </button>
              </div>
            </div>

            <details className="mt-8 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-slate-700 dark:bg-slate-900/40">
              <summary className="cursor-pointer text-sm font-medium text-slate-800 dark:text-slate-200">
                Filters
              </summary>
              <form className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" onSubmit={applyFilters}>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
                  City contains
                  <input
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
                    value={filterDraft.city}
                    onChange={(e) => setFilterDraft((d) => ({ ...d, city: e.target.value }))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
                  Min price
                  <input
                    type="number"
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
                    value={filterDraft.min_price}
                    onChange={(e) => setFilterDraft((d) => ({ ...d, min_price: e.target.value }))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
                  Max price
                  <input
                    type="number"
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
                    value={filterDraft.max_price}
                    onChange={(e) => setFilterDraft((d) => ({ ...d, max_price: e.target.value }))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
                  Min score (0–1)
                  <input
                    type="number"
                    step="0.05"
                    min={0}
                    max={1}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
                    value={filterDraft.min_score}
                    onChange={(e) => setFilterDraft((d) => ({ ...d, min_score: e.target.value }))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
                  Beds min
                  <input
                    type="number"
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
                    value={filterDraft.min_bedrooms}
                    onChange={(e) => setFilterDraft((d) => ({ ...d, min_bedrooms: e.target.value }))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
                  Beds max
                  <input
                    type="number"
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
                    value={filterDraft.max_bedrooms}
                    onChange={(e) => setFilterDraft((d) => ({ ...d, max_bedrooms: e.target.value }))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
                  Baths min
                  <input
                    type="number"
                    step="0.5"
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
                    value={filterDraft.min_bathrooms}
                    onChange={(e) => setFilterDraft((d) => ({ ...d, min_bathrooms: e.target.value }))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
                  Baths max
                  <input
                    type="number"
                    step="0.5"
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
                    value={filterDraft.max_bathrooms}
                    onChange={(e) => setFilterDraft((d) => ({ ...d, max_bathrooms: e.target.value }))}
                  />
                </label>
                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 sm:col-span-2">
                  Pet policy
                  <select
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800"
                    value={filterDraft.pets_policy}
                    onChange={(e) => setFilterDraft((d) => ({ ...d, pets_policy: e.target.value }))}
                  >
                    {PETS_FILTER.map((o) => (
                      <option key={o.value || 'any'} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex flex-wrap items-end gap-2 sm:col-span-2 lg:col-span-4">
                  <button
                    type="submit"
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
                  >
                    Apply filters
                  </button>
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    Clear filters
                  </button>
                </div>
              </form>
            </details>

            {runId ? (
              <div className="mt-8 space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-slate-600 dark:text-slate-300">
                    Showing results for{' '}
                    {run ? (
                      <>
                        <span className="font-medium">{run.city}</span>
                        <Link
                          href={`/runs/${runId}`}
                          className="ml-2 text-blue-600 hover:underline dark:text-blue-400"
                        >
                          Open run report
                        </Link>
                      </>
                    ) : (
                      'this run'
                    )}
                  </p>
                  <Link href="/listings" className="text-sm text-slate-500 hover:underline dark:text-slate-400">
                    Clear run filter
                  </Link>
                </div>

                <div className="flex flex-wrap gap-2" role="tablist" aria-label="Result category">
                  {CATEGORIES.map((c) => (
                    <button
                      key={c.key}
                      type="button"
                      role="tab"
                      aria-selected={activeCategory === c.key}
                      onClick={() => setCategory(c.key)}
                      className={clsx(
                        'rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
                        activeCategory === c.key
                          ? 'bg-blue-600 text-white dark:bg-blue-500'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700',
                      )}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>

                {availableSources.length > 1 && (
                  <div className="flex flex-wrap gap-2" role="tablist" aria-label="Source filter">
                    {['all', ...availableSources].map((s) => (
                      <button
                        key={s}
                        type="button"
                        role="tab"
                        aria-selected={sourceFilter === s}
                        onClick={() => setSourceFilter(s)}
                        className={clsx(
                          'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                          sourceFilter === s
                            ? 'bg-slate-700 text-white dark:bg-slate-300 dark:text-slate-900'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700',
                        )}
                      >
                        {s === 'all'
                          ? 'All sources'
                          : s === 'pm_direct'
                            ? 'Property sites'
                            : s.charAt(0).toUpperCase() + s.slice(1)}
                      </button>
                    ))}
                  </div>
                )}

                {runLoading ? (
                  <p className="text-slate-500">Loading run results…</p>
                ) : filteredResults.length === 0 ? (
                  <p className="text-sm text-slate-500">No listings in this category for the current revision.</p>
                ) : view === 'table' ? (
                  <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                    <table className="min-w-full divide-y divide-slate-200 text-left text-sm dark:divide-slate-700">
                      <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-900/95">
                        <tr>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            Map
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            Photo
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            <SortButton label="Address" active={sortKey === 'address'} onClick={() => toggleSort('address')} />
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            <SortButton label="Price" active={sortKey === 'price'} onClick={() => toggleSort('price')} />
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            Beds
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            Baths
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            <SortButton label="Sqft" active={sortKey === 'sqft'} onClick={() => toggleSort('sqft')} />
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            Pets
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            <SortButton label="Score" active={sortKey === 'score'} onClick={() => toggleSort('score')} />
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            Category
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            Source
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            Link
                          </th>
                          <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                            Notes
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {sortRunRows(filteredResults, listingById, coordPatch, sortKey, sortDir).map(({ rr, listing }) => (
                          <RunTableRow
                            key={rr.id}
                            result={rr}
                            listing={listing}
                            merged={listing ? withCoords(listing) : undefined}
                            onGeocode={() => listing && geocodeOne(listing.id)}
                            mapsLink={listing ? mapsLink(listing) : '#'}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                    {filteredResults.map((rr) => (
                      <RunResultCard
                        key={rr.id}
                        result={rr}
                        listing={listingById.get(rr.listing_id)}
                        merged={(() => {
                          const l = listingById.get(rr.listing_id)
                          return l ? withCoords(l) : undefined
                        })()}
                        onGeocode={() => {
                          const l = listingById.get(rr.listing_id)
                          if (l) void geocodeOne(l.id)
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            ) : loading ? (
              <div className="mt-16 text-center text-slate-500">Loading listings…</div>
            ) : sortedGlobalListings.length === 0 ? (
              <div className="mt-16 rounded-2xl border-2 border-dashed border-slate-200 p-12 text-center dark:border-slate-700">
                <p className="text-lg font-medium text-slate-900 dark:text-slate-100">No listings match</p>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                  Adjust filters or run a discovery from the{' '}
                  <Link href="/" className="text-blue-600 hover:underline dark:text-blue-400">
                    Dashboard
                  </Link>
                  .
                </p>
              </div>
            ) : view === 'table' ? (
              <div className="mt-10 overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                <table className="min-w-full divide-y divide-slate-200 text-left text-sm dark:divide-slate-700">
                  <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-900/95">
                    <tr>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        Map
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        Photo
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        <SortButton label="Address" active={sortKey === 'address'} onClick={() => toggleSort('address')} />
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        <SortButton label="Price" active={sortKey === 'price'} onClick={() => toggleSort('price')} />
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        Beds
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        Baths
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        <SortButton label="Sqft" active={sortKey === 'sqft'} onClick={() => toggleSort('sqft')} />
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        Pets
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        <SortButton label="Score" active={sortKey === 'score'} onClick={() => toggleSort('score')} />
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        Source
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium text-slate-600 dark:text-slate-300">
                        Link
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {sortedGlobalListings.map((listing) => (
                      <GlobalTableRow
                        key={listing.id}
                        listing={listing}
                        onGeocode={() => geocodeOne(listing.id)}
                        mapsLink={mapsLink(listing)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {sortedGlobalListings.map((listing) => (
                  <ListingCard key={listing.id} listing={listing} onGeocode={() => geocodeOne(listing.id)} />
                ))}
              </div>
            )}
          </div>
        </Container>
      </main>
      <Footer />
    </>
  )
}

function SortButton({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'inline-flex items-center gap-1 font-medium',
        active ? 'text-blue-600 dark:text-blue-400' : 'text-slate-600 dark:text-slate-300',
      )}
    >
      {label}
      {active ? <span className="text-xs opacity-70">↕</span> : null}
    </button>
  )
}

function sortRunRows(
  results: RunListingResult[],
  byId: Map<string, ListingDTO>,
  coordPatch: Record<string, { lat: number; lon: number }>,
  key: SortKey,
  dir: SortDir,
): { rr: RunListingResult; listing: ListingDTO | undefined }[] {
  const merged = results.map((rr) => {
    const listing = byId.get(rr.listing_id)
    const p = coordPatch[rr.listing_id]
    const adj =
      listing && p ? { ...listing, latitude: p.lat, longitude: p.lon } : listing
    return { rr, listing: adj }
  })
  const mul = dir === 'asc' ? 1 : -1
  return merged.sort((a, b) => {
    const la = a.listing
    const lb = b.listing
    if (key === 'score') {
      const sa = a.rr.score ?? la?.score ?? null
      const sb = b.rr.score ?? lb?.score ?? null
      if (sa == null && sb == null) return 0
      if (sa == null) return 1
      if (sb == null) return -1
      return (Number(sa) - Number(sb)) * mul
    }
    if (!la || !lb) return 0
    const va = la[key]
    const vb = lb[key]
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    if (typeof va === 'string' && typeof vb === 'string') return va.localeCompare(vb) * mul
    return (Number(va) - Number(vb)) * mul
  })
}

function thumbSrc(listing: ListingDTO | undefined): string | null {
  if (!listing?.photos?.length) return null
  return safeHttpUrl(listing.photos[0]) ?? null
}

function MapCell({
  listing,
  onGeocode,
  mapsLink,
}: {
  listing: ListingDTO | undefined
  onGeocode: () => void
  mapsLink: string
}) {
  if (!listing) {
    return <span className="text-slate-400">—</span>
  }
  const lat = listing.latitude ?? undefined
  const lon = listing.longitude ?? undefined
  if (lat != null && lon != null) {
    return <ListingMiniMap latitude={lat} longitude={lon} />
  }
  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={onGeocode}
        className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-blue-600 hover:bg-slate-50 dark:border-slate-600 dark:text-blue-400 dark:hover:bg-slate-800"
      >
        Locate
      </button>
      <a
        href={mapsLink}
        target="_blank"
        rel="noopener noreferrer"
        className="text-center text-[10px] text-slate-500 underline dark:text-slate-400"
      >
        Open map
      </a>
    </div>
  )
}

function GlobalTableRow({
  listing,
  onGeocode,
  mapsLink,
}: {
  listing: ListingDTO
  onGeocode: () => void
  mapsLink: string
}) {
  const src = thumbSrc(listing)
  const url = safeHttpUrl(listing.url)
  return (
    <tr className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40">
      <td className="px-3 py-2 align-top">
        <MapCell listing={listing} onGeocode={onGeocode} mapsLink={mapsLink} />
      </td>
      <td className="px-3 py-2 align-top">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="" className="h-14 w-20 rounded-lg object-cover" loading="lazy" />
        ) : (
          <div className="h-14 w-20 rounded-lg bg-slate-100 dark:bg-slate-800" />
        )}
      </td>
      <td className="px-3 py-2 align-top font-medium text-slate-900 dark:text-slate-100">{listing.address}</td>
      <td className="px-3 py-2 align-top tabular-nums">${listing.price.toLocaleString()}</td>
      <td className="px-3 py-2 align-top tabular-nums">{listing.bedrooms ?? '—'}</td>
      <td className="px-3 py-2 align-top tabular-nums">{listing.bathrooms ?? '—'}</td>
      <td className="px-3 py-2 align-top tabular-nums">{listing.sqft != null ? listing.sqft.toLocaleString() : '—'}</td>
      <td className="px-3 py-2 align-top text-xs">{petLabel(listing.pets_policy)}</td>
      <td className="px-3 py-2 align-top text-xs">{scoreLabel(listing.score)}</td>
      <td className="px-3 py-2 align-top text-xs text-slate-500">{listing.source || 'pm_direct'}</td>
      <td className="px-3 py-2 align-top">
        {url ? (
          <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline dark:text-blue-400">
            View
          </a>
        ) : (
          '—'
        )}
      </td>
    </tr>
  )
}

function RunTableRow({
  result,
  listing,
  merged,
  onGeocode,
  mapsLink,
}: {
  result: RunListingResult
  listing: ListingDTO | undefined
  merged: ListingDTO | undefined
  onGeocode: () => void
  mapsLink: string
}) {
  const src = thumbSrc(merged ?? listing)
  const url = safeHttpUrl(merged?.url ?? listing?.url)
  const score = result.score ?? merged?.score ?? listing?.score ?? null
  return (
    <tr className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40">
      <td className="px-3 py-2 align-top">
        <MapCell listing={merged ?? listing} onGeocode={onGeocode} mapsLink={mapsLink} />
      </td>
      <td className="px-3 py-2 align-top">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="" className="h-14 w-20 rounded-lg object-cover" loading="lazy" />
        ) : (
          <div className="h-14 w-20 rounded-lg bg-slate-100 dark:bg-slate-800" />
        )}
      </td>
      <td className="px-3 py-2 align-top font-medium text-slate-900 dark:text-slate-100">
        {merged?.address ?? listing?.address ?? `Listing ${result.listing_id.slice(0, 8)}…`}
      </td>
      <td className="px-3 py-2 align-top tabular-nums">
        {merged?.price != null ? `$${merged.price.toLocaleString()}` : '—'}
      </td>
      <td className="px-3 py-2 align-top tabular-nums">{merged?.bedrooms ?? listing?.bedrooms ?? '—'}</td>
      <td className="px-3 py-2 align-top tabular-nums">{merged?.bathrooms ?? listing?.bathrooms ?? '—'}</td>
      <td className="px-3 py-2 align-top tabular-nums">
        {merged?.sqft != null || listing?.sqft != null
          ? (merged?.sqft ?? listing?.sqft)!.toLocaleString()
          : '—'}
      </td>
      <td className="px-3 py-2 align-top text-xs">{petLabel(merged?.pets_policy ?? listing?.pets_policy ?? 'unknown')}</td>
      <td className="px-3 py-2 align-top text-xs">{scoreLabel(score)}</td>
      <td className="px-3 py-2 align-top text-xs capitalize text-slate-600 dark:text-slate-300">
        {result.category.replace(/_/g, ' ')}
      </td>
      <td className="px-3 py-2 align-top text-xs">{merged?.source ?? listing?.source ?? '—'}</td>
      <td className="px-3 py-2 align-top">
        {url ? (
          <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline dark:text-blue-400">
            View
          </a>
        ) : (
          '—'
        )}
      </td>
      <td className="max-w-[14rem] px-3 py-2 align-top text-xs text-slate-600 dark:text-slate-300">
        {result.explanation ? <p className="mb-1 text-slate-700 dark:text-slate-200">{result.explanation}</p> : null}
        <FilterReasonList reasonsJson={result.filter_reasons_json} />
      </td>
    </tr>
  )
}

function RunResultCard({
  result,
  listing,
  merged,
  onGeocode,
}: {
  result: RunListingResult
  listing: ListingDTO | undefined
  merged?: ListingDTO
  onGeocode: () => void
}) {
  const row = merged ?? listing
  const sourceUrl = row ? safeHttpUrl(row.url) : null
  const src = thumbSrc(row)
  const maps = row ? `https://www.openstreetmap.org/search?query=${encodeURIComponent(row.address)}` : '#'
  return (
    <div className="rounded-2xl border border-slate-200 p-6 dark:border-slate-800">
      <div className="flex gap-4">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="" className="h-24 w-32 shrink-0 rounded-xl object-cover" loading="lazy" />
        ) : (
          <div className="h-24 w-32 shrink-0 rounded-xl bg-slate-100 dark:bg-slate-800" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
            {result.category.replace(/_/g, ' ')}
          </p>
          <h3 className="mt-1 font-display text-base font-medium text-slate-900 dark:text-slate-100">
            {row?.address ?? `Listing ${result.listing_id.slice(0, 8)}…`}
          </h3>
          {row ? (
            <div className="mt-2 flex flex-wrap gap-3 text-sm text-slate-600 dark:text-slate-400">
              <span className="font-semibold text-slate-900 dark:text-slate-100">${row.price.toLocaleString()}/mo</span>
              {row.bedrooms !== null && <span>{row.bedrooms} BR</span>}
              {row.bathrooms !== null && <span>{row.bathrooms} BA</span>}
              {row.sqft !== null && <span>{row.sqft.toLocaleString()} sqft</span>}
              <span className="text-xs">{petLabel(row.pets_policy)}</span>
            </div>
          ) : null}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {row && row.latitude != null && row.longitude != null ? (
          <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700">
            <ListingMiniMap latitude={row.latitude} longitude={row.longitude} />
          </div>
        ) : (
          <button
            type="button"
            onClick={onGeocode}
            className="rounded-lg border border-slate-200 px-3 py-1 text-xs text-blue-600 dark:border-slate-600 dark:text-blue-400"
          >
            Locate on map
          </button>
        )}
        <a
          href={maps}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-slate-500 underline dark:text-slate-400"
        >
          Open in OpenStreetMap
        </a>
      </div>
      {result.score != null ? (
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Score: {scoreLabel(result.score)}</p>
      ) : null}
      {result.explanation ? (
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{result.explanation}</p>
      ) : null}
      <FilterReasonList reasonsJson={result.filter_reasons_json} />
      {sourceUrl ? (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-block text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          View source
        </a>
      ) : null}
    </div>
  )
}

function ListingCard({
  listing,
  onGeocode,
}: {
  listing: ListingDTO
  onGeocode: () => void
}) {
  const sourceUrl = safeHttpUrl(listing.url)
  const src = thumbSrc(listing)
  const maps = mapsLink(listing)
  return (
    <div className="group relative rounded-2xl border border-slate-200 p-6 transition-shadow hover:shadow-lg dark:border-slate-800">
      {listing.score !== null && (
        <div
          className={clsx(
            'absolute top-4 right-4 rounded-full px-2.5 py-0.5 text-xs font-semibold',
            listing.score >= 0.8 || (listing.score >= 80 && listing.score <= 100)
              ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
              : listing.score >= 0.5 || listing.score >= 50
                ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200'
                : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
          )}
        >
          {scoreLabel(listing.score)}
        </div>
      )}

      <div className="flex gap-4">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="" className="h-28 w-40 shrink-0 rounded-xl object-cover" loading="lazy" />
        ) : (
          <div className="h-28 w-40 shrink-0 rounded-xl bg-slate-100 dark:bg-slate-800" />
        )}
        <div className="min-w-0 flex-1 pr-14">
          <h3 className="font-display text-base font-medium text-slate-900 dark:text-slate-100">{listing.address}</h3>
          <div className="mt-2 flex flex-wrap gap-3 text-sm text-slate-600 dark:text-slate-400">
            <span className="font-semibold text-slate-900 dark:text-slate-100">${listing.price.toLocaleString()}/mo</span>
            {listing.bedrooms !== null && <span>{listing.bedrooms} BR</span>}
            {listing.bathrooms !== null && <span>{listing.bathrooms} BA</span>}
            {listing.sqft !== null && <span>{listing.sqft.toLocaleString()} sqft</span>}
            <span className="text-xs">{petLabel(listing.pets_policy)}</span>
          </div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        {listing.latitude != null && listing.longitude != null ? (
          <ListingMiniMap latitude={listing.latitude} longitude={listing.longitude} />
        ) : (
          <button
            type="button"
            onClick={onGeocode}
            className="rounded-lg border border-slate-200 px-3 py-1 text-xs text-blue-600 dark:border-slate-600 dark:text-blue-400"
          >
            Locate on map
          </button>
        )}
        <a
          href={maps}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-slate-500 underline dark:text-slate-400"
        >
          Open in OpenStreetMap
        </a>
      </div>

      {listing.score_explanation && (
        <p className="mt-3 line-clamp-2 text-sm text-slate-500 dark:text-slate-400">{listing.score_explanation}</p>
      )}

      <div className="mt-4 flex items-center justify-between text-xs text-slate-400 dark:text-slate-500">
        <span className="flex items-center gap-2">
          <span>{new Date(listing.extraction_timestamp).toLocaleDateString()}</span>
          {listing.source && listing.source !== 'pm_direct' && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              {listing.source}
            </span>
          )}
        </span>
        {sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline dark:text-blue-400"
          >
            View source
          </a>
        ) : (
          <span>Source unavailable</span>
        )}
      </div>
    </div>
  )
}

export default function ListingsPage() {
  return (
    <Suspense
      fallback={
        <>
          <Header />
          <main className="flex-1">
            <Container className="py-16">
              <p className="text-slate-500">Loading…</p>
            </Container>
          </main>
          <Footer />
        </>
      }
    >
      <ListingsContent />
    </Suspense>
  )
}
