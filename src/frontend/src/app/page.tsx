'use client'

import { useState, useEffect, useCallback } from 'react'
import clsx from 'clsx'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Preference {
  id: string
  description: string
  city: string
  api_provider: string
  openrouter_api_key: string | null
  apify_api_token: string | null
}

interface DiscoveryEvent {
  id: number
  message: string
  type: 'info' | 'success' | 'error' | 'progress'
  timestamp: string
}

export default function Dashboard() {
  const [preferences, setPreferences] = useState<Preference[]>([])
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<DiscoveryEvent[]>([])
  const [health, setHealth] = useState<'ok' | 'down' | 'checking'>('checking')

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(() => setHealth('ok'))
      .catch(() => setHealth('down'))

    fetch(`${API}/api/preferences`)
      .then((r) => r.json())
      .then(setPreferences)
      .catch(() => {})
  }, [])

  const addEvent = useCallback(
    (message: string, type: DiscoveryEvent['type'] = 'info') => {
      setEvents((prev) => [
        ...prev,
        {
          id: Date.now(),
          message,
          type,
          timestamp: new Date().toLocaleTimeString(),
        },
      ])
    },
    [],
  )

  const runDiscovery = async () => {
    if (preferences.length === 0) {
      addEvent('No preferences configured. Go to Preferences first.', 'error')
      return
    }

    const pref = preferences[0]
    if (!pref.openrouter_api_key) {
      addEvent(
        'No OpenRouter API key configured. Go to Preferences to add one.',
        'error',
      )
      return
    }

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
      } else {
        const data = await resp.json()
        addEvent(
          `Discovery complete! Found ${data.managers_found ?? '?'} property managers.`,
          'success',
        )
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      addEvent(`Network error: ${msg}`, 'error')
    } finally {
      setRunning(false)
    }
  }

  const activePreference = preferences[0]

  return (
    <>
      <Header />
      <main className="flex-1">
        {/* Hero section */}
        <Container className="pt-20 pb-16 text-center lg:pt-32">
          <h1 className="mx-auto max-w-4xl font-display text-5xl font-medium tracking-tight text-slate-900 sm:text-7xl">
            Find rentals{' '}
            <span className="relative whitespace-nowrap text-blue-600">
              <svg
                aria-hidden="true"
                viewBox="0 0 418 42"
                className="absolute top-2/3 left-0 h-[0.58em] w-full fill-blue-300/70"
                preserveAspectRatio="none"
              >
                <path d="M203.371.916c-26.013-2.078-76.686 1.963-124.73 9.946L67.3 12.749C35.421 18.062 18.2 21.766 6.004 25.934 1.244 27.561.828 27.778.874 28.61c.07 1.214.828 1.121 9.595-1.176 9.072-2.377 17.15-3.92 39.246-7.496C123.565 7.986 157.869 4.492 195.942 5.046c7.461.108 19.25 1.696 19.17 2.582-.107 1.183-7.874 4.31-25.75 10.366-21.992 7.45-35.43 12.534-36.701 13.884-2.173 2.308-.202 4.407 4.442 4.734 2.654.187 3.263.157 15.593-.78 35.401-2.686 57.944-3.488 88.365-3.143 46.327.526 75.721 2.23 130.788 7.584 19.787 1.924 20.814 1.98 24.557 1.332l.066-.011c1.201-.203 1.53-1.825.399-2.335-2.911-1.31-4.893-1.604-22.048-3.261-57.509-5.556-87.871-7.36-132.059-7.842-23.239-.254-33.617-.116-50.627.674-11.629.54-42.371 2.494-46.696 2.967-2.359.259 8.133-3.625 26.504-9.81 23.239-7.825 27.934-10.149 28.304-14.005.417-4.348-3.529-6-16.878-7.066Z" />
              </svg>
              <span className="relative">with AI</span>
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg tracking-tight text-slate-700">
            Doormat discovers property managers, extracts listings, and scores
            them against your preferences — autonomously.
          </p>
        </Container>

        {/* Status + Discovery panel */}
        <Container className="pb-16">
          <div className="mx-auto max-w-3xl">
            {/* Status cards */}
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 p-6">
                <div className="text-sm font-medium text-slate-500">
                  Backend
                </div>
                <div className="mt-2 flex items-center gap-x-2">
                  <span
                    className={clsx(
                      'h-3 w-3 rounded-full',
                      health === 'ok' && 'bg-green-500',
                      health === 'down' && 'bg-red-500',
                      health === 'checking' && 'animate-pulse bg-yellow-400',
                    )}
                  />
                  <span className="text-lg font-semibold text-slate-900">
                    {health === 'ok'
                      ? 'Connected'
                      : health === 'down'
                        ? 'Offline'
                        : 'Checking…'}
                  </span>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 p-6">
                <div className="text-sm font-medium text-slate-500">
                  Search City
                </div>
                <div className="mt-2 text-lg font-semibold text-slate-900">
                  {activePreference?.city || 'Not set'}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 p-6">
                <div className="text-sm font-medium text-slate-500">
                  API Key
                </div>
                <div className="mt-2 text-lg font-semibold text-slate-900">
                  {activePreference?.openrouter_api_key
                    ? '••••' +
                      activePreference.openrouter_api_key.slice(-4)
                    : 'Not configured'}
                </div>
              </div>
            </div>

            {/* Run Discovery button */}
            <div className="mt-10 text-center">
              <Button
                color="blue"
                onClick={runDiscovery}
                disabled={running || health !== 'ok'}
                className="px-8 py-3 text-base"
              >
                {running ? (
                  <>
                    <svg
                      className="-ml-1 mr-3 h-5 w-5 animate-spin text-white"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
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
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Running Discovery…
                  </>
                ) : (
                  '🔍 Run Discovery'
                )}
              </Button>
              {!activePreference && (
                <p className="mt-3 text-sm text-slate-500">
                  <a
                    href="/preferences"
                    className="text-blue-600 hover:underline"
                  >
                    Configure your preferences
                  </a>{' '}
                  before running a discovery.
                </p>
              )}
            </div>

            {/* Discovery log */}
            {events.length > 0 && (
              <div className="mt-10 rounded-2xl border border-slate-200 bg-slate-50 p-6">
                <h3 className="font-display text-sm font-medium text-slate-900">
                  Discovery Log
                </h3>
                <div className="mt-4 space-y-2 font-mono text-sm">
                  {events.map((evt) => (
                    <div
                      key={evt.id}
                      className={clsx(
                        'flex items-start gap-x-2',
                        evt.type === 'error' && 'text-red-600',
                        evt.type === 'success' && 'text-green-600',
                        evt.type === 'info' && 'text-slate-600',
                        evt.type === 'progress' && 'text-blue-600',
                      )}
                    >
                      <span className="shrink-0 text-slate-400">
                        [{evt.timestamp}]
                      </span>
                      <span>{evt.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Container>
      </main>
      <Footer />
    </>
  )
}

