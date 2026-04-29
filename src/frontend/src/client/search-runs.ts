/**
 * Thin fetch helpers for search-run polling and mutations.
 * Generated SDK lives alongside this file; these wrappers keep stable names
 * and enforce cache behavior for live UI.
 */

import type {
  RunListingResultOut,
  SearchRunActiveEnvelope,
  SearchRunCreate,
  SearchRunEventOut,
  SearchRunResponse,
} from './types.gen'

export type SearchRun = SearchRunResponse
export type SearchRunEvent = SearchRunEventOut
export type RunListingResult = RunListingResultOut
export type { SearchRunSuggestion } from './types.gen'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/** Avoid stale snapshots when polling run detail and events. */
const noStore: RequestInit = {
  cache: 'no-store',
  headers: { 'Cache-Control': 'no-cache' },
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json() as Promise<T>
}

export async function fetchSearchRun(runId: string): Promise<SearchRun> {
  const res = await fetch(`${API}/api/search-runs/${encodeURIComponent(runId)}`, noStore)
  return readJson(res)
}

export async function fetchSearchRunEvents(
  runId: string,
  params: { afterSequence: number; limit?: number },
): Promise<SearchRunEvent[]> {
  const sp = new URLSearchParams()
  sp.set('after_sequence', String(params.afterSequence))
  if (params.limit != null) sp.set('limit', String(params.limit))
  const res = await fetch(
    `${API}/api/search-runs/${encodeURIComponent(runId)}/events?${sp}`,
    noStore,
  )
  return readJson(res)
}

export async function fetchActiveSearchRun(): Promise<SearchRunActiveEnvelope> {
  const res = await fetch(`${API}/api/search-runs/active`, noStore)
  return readJson(res)
}

export async function stopSearchRun(runId: string): Promise<void> {
  const res = await fetch(`${API}/api/search-runs/${encodeURIComponent(runId)}/stop`, {
    method: 'POST',
    ...noStore,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
}

export async function createSearchRun(body: SearchRunCreate): Promise<SearchRun> {
  const res = await fetch(`${API}/api/search-runs`, {
    method: 'POST',
    ...noStore,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache',
    },
    body: JSON.stringify(body),
  })
  return readJson(res)
}

export async function fetchSearchRunResults(
  runId: string,
  opts: { category: string; limit?: number; offset?: number },
): Promise<RunListingResult[]> {
  const sp = new URLSearchParams()
  sp.set('category', opts.category)
  if (opts.limit != null) sp.set('limit', String(opts.limit))
  if (opts.offset != null) sp.set('offset', String(opts.offset))
  const res = await fetch(
    `${API}/api/search-runs/${encodeURIComponent(runId)}/results?${sp}`,
    noStore,
  )
  return readJson(res)
}

export async function patchSearchRunFilters(
  runId: string,
  patch: Record<string, unknown>,
): Promise<SearchRun> {
  const res = await fetch(`${API}/api/search-runs/${encodeURIComponent(runId)}/filters`, {
    method: 'PATCH',
    ...noStore,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache',
    },
    body: JSON.stringify(patch),
  })
  return readJson(res)
}
