/**
 * Trusted listing sources (Craigslist regions + property manager URLs).
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

export type TrustedSourceKind = 'craigslist_region' | 'property_manager'

export interface TrustedSource {
  id: string
  kind: TrustedSourceKind
  label: string
  url: string
  city: string | null
  linked_property_manager_id: string | null
  created_at: string
}

export async function fetchTrustedSources(params?: {
  kind?: TrustedSourceKind
  city?: string
}): Promise<TrustedSource[]> {
  const sp = new URLSearchParams()
  if (params?.kind) sp.set('kind', params.kind)
  if (params?.city) sp.set('city', params.city)
  const q = sp.toString()
  const res = await fetch(`${API}/api/trusted-sources${q ? `?${q}` : ''}`, noStore)
  return readJson(res)
}

export async function createTrustedSource(body: {
  kind: TrustedSourceKind
  label: string
  url: string
  city?: string | null
}): Promise<TrustedSource> {
  const res = await fetch(`${API}/api/trusted-sources`, {
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

export async function deleteTrustedSource(id: string): Promise<void> {
  const res = await fetch(`${API}/api/trusted-sources/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    ...noStore,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
}

export async function testTrustedSource(id: string): Promise<{
  ok: boolean
  status_code: number | null
  detail: string | null
}> {
  const res = await fetch(`${API}/api/trusted-sources/${encodeURIComponent(id)}/test`, {
    method: 'POST',
    ...noStore,
  })
  return readJson(res)
}
