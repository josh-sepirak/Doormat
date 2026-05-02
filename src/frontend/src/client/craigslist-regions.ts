/**
 * Craigslist region suggestions from geocoded city + state.
 */

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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

export interface GeocodedPlace {
  lat: number
  lon: number
  display_name: string
}

export interface CraigslistSuggestion {
  subdomain: string
  label: string
  url: string
  distance_mi: number
}

export interface CraigslistRegionsResponse {
  geocoded: GeocodedPlace
  suggestions: CraigslistSuggestion[]
}

export async function fetchCraigslistRegions(city: string, state: string): Promise<CraigslistRegionsResponse> {
  const sp = new URLSearchParams()
  sp.set('city', city)
  sp.set('state', state)
  const res = await fetch(`${API}/api/craigslist/regions?${sp}`, noStore)
  return readJson(res)
}

export async function parseCraigslistRegionUrl(url: string): Promise<{
  subdomain: string
  label: string
  url: string
  valid: boolean
  error: string | null
}> {
  const res = await fetch(`${API}/api/craigslist/regions/parse`, {
    method: 'POST',
    ...noStore,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-cache',
    },
    body: JSON.stringify({ url }),
  })
  return readJson(res)
}
