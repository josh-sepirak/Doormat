/**
 * Unified API client wrapper for Doormat frontend.
 * Automatically resolves API base URL and attaches Authorization: Bearer <token>
 * from NEXT_PUBLIC_AUTH_BEARER_TOKEN or localStorage ('doormat_auth_token').
 */

export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function getAuthToken(): string | null {
  if (typeof window !== 'undefined') {
    try {
      const stored = window.localStorage.getItem('doormat_auth_token')
      if (stored) return stored
    } catch {
      // localStorage may be disabled or restricted in private browsing
    }
  }
  return process.env.NEXT_PUBLIC_AUTH_BEARER_TOKEN || null
}

export function setAuthToken(token: string | null): void {
  if (typeof window !== 'undefined') {
    try {
      if (token) {
        window.localStorage.setItem('doormat_auth_token', token)
      } else {
        window.localStorage.removeItem('doormat_auth_token')
      }
    } catch {
      // ignore storage access errors
    }
  }
}

export async function apiFetch(
  input: string | URL | Request,
  init?: RequestInit,
): Promise<Response> {
  let url: string | URL | Request = input
  if (typeof input === 'string') {
    if (input.startsWith('/')) {
      url = `${API_BASE_URL}${input}`
    } else if (!input.startsWith('http://') && !input.startsWith('https://')) {
      url = `${API_BASE_URL}/${input}`
    }
  }

  const token = getAuthToken()
  const headers = new Headers(init?.headers || {})

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  return fetch(url, {
    ...init,
    headers,
  })
}

export async function apiJson<T>(
  input: string | URL | Request,
  init?: RequestInit,
): Promise<T> {
  const res = await apiFetch(input, init)
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorBody.detail || `API request failed with status ${res.status}`)
  }
  return res.json() as Promise<T>
}
