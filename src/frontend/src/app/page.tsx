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
        { id: Date.now(), message, type, timestamp: new Date().toLocaleTimeString() },
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
      addEvent('No OpenRouter API key configured. Go to Preferences to add one.', 'error')
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
          `Discovery complete. Found ${data.managers_found ?? '?'} property managers.`,
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
                  pref?.openrouter_api_key
                    ? '••••' + pref.openrouter_api_key.slice(-4)
                    : 'Not configured'
                }
                muted={!pref?.openrouter_api_key}
              />
            </div>

            {/* Run action */}
            <div className="mt-10 flex justify-center">
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
            </div>

            {/* Discovery log */}
            <div className="mt-10 overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
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
                        )}
                      >
                        <span className="shrink-0 tabular-nums text-slate-400 dark:text-slate-600">
                          {evt.timestamp}
                        </span>
                        <span>{evt.message}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

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
              indicator === 'checking' && 'animate-pulse bg-amber-400',
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
      className="-ml-1 mr-2 h-4 w-4 animate-spin"
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
