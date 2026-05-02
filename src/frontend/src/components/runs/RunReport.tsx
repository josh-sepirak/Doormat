/*
 * Run report UI — accessibility & theming notes:
 * - Prefer semantic sections and headings; primary actions use visible focus rings (ring-blue-500).
 * - Technical details use a native button + aria-expanded / aria-controls for the disclosure pattern.
 * - Dark mode: paired slate backgrounds/borders and blue-600 accent per app shell.
 * - Responsive: layout should stay usable around 375px width (see spec 005 SC-008).
 * - Reduced motion: prefer CSS that respects prefers-reduced-motion where animations exist.
 * - AnimatedCounter uses rAF-based easing; flash animation highlights new feed items.
 */

'use client'

import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'

import type { SearchRun, SearchRunEvent } from '@/client/search-runs'
import { fetchSearchRun, fetchSearchRunEvents, stopSearchRun } from '@/client/search-runs'
import { AnimatedCounter } from '@/components/runs/AnimatedCounter'
import { RunControls } from '@/components/runs/RunControls'
import { RunFilterControls } from '@/components/runs/RunFilterControls'
import { RunSuggestions } from '@/components/runs/RunSuggestions'
import { RunTechnicalDetails } from '@/components/runs/RunTechnicalDetails'

type RunReportProps = {
  runId: string
}

const TERMINAL = new Set(['success', 'error', 'cancelled'])

const STAGE_ORDER = ['discovery', 'scraping', 'scoring', 'done'] as const
type Stage = (typeof STAGE_ORDER)[number]

function stageIndex(stage: string | null | undefined): number {
  if (!stage) return -1
  const s = stage.toLowerCase()
  if (s === 'extracting') return 1
  return STAGE_ORDER.indexOf(s as Stage)
}

function relativeTime(ts: string, now: number): string {
  const diff = Math.floor((now - new Date(ts).getTime()) / 1000)
  if (diff < 5) return 'just now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s
  return `${s.slice(0, max - 1)}…`
}

/** Second-line detail from sanitized server payload (no secrets expected). */
function eventPayloadDetail(payloadJson: string | null | undefined): string | null {
  if (!payloadJson?.trim()) return null
  try {
    const p = JSON.parse(payloadJson) as Record<string, unknown>
    const parts: string[] = []
    if (typeof p.url === 'string') parts.push(truncate(p.url, 96))
    if (typeof p.pm === 'string') parts.push(String(p.pm))
    if (typeof p.property_manager === 'string') parts.push(String(p.property_manager))
    if (typeof p.count === 'number') parts.push(`count ${p.count}`)
    if (typeof p.total === 'number' && typeof p.done === 'number') {
      parts.push(`progress ${p.done}/${p.total}`)
    }
    return parts.length > 0 ? parts.join(' · ') : null
  } catch {
    return null
  }
}

function eventBadge(eventType: string): string {
  if (eventType.includes('error'))
    return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
  if (eventType.includes('warning'))
    return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
  if (eventType.includes('listing_skipped') || eventType.includes('skipped'))
    return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-200'
  if (eventType === 'stage_completed' || eventType === 'run_completed')
    return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
  if (eventType === 'listing_found')
    return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
  if (eventType === 'listing_scored')
    return 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300'
  if (eventType === 'stage_started')
    return 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
  return 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
}

export function RunReport({ runId }: RunReportProps) {
  const [run, setRun] = useState<SearchRun | null>(null)
  const [events, setEvents] = useState<SearchRunEvent[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [freshIds, setFreshIds] = useState<Set<string>>(new Set())
  const [now, setNow] = useState(() => Date.now())
  const lastSeq = useRef(-1)
  const prevRunIdRef = useRef<string | null>(null)
  const runRef = useRef(run)
  runRef.current = run
  const debouncedRefreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Tick for relative timestamps
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 5000)
    return () => clearInterval(id)
  }, [])

  const refreshRun = useCallback(async () => {
    try {
      const r = await fetchSearchRun(runId)
      setRun(r)
      setLoadError(null)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Failed to load run')
    }
  }, [runId])

  const scheduleDebouncedRunRefresh = useCallback(() => {
    if (debouncedRefreshTimer.current) clearTimeout(debouncedRefreshTimer.current)
    debouncedRefreshTimer.current = setTimeout(() => {
      debouncedRefreshTimer.current = null
      void refreshRun()
    }, 400)
  }, [refreshRun])

  const pollEvents = useCallback(async () => {
    try {
      const batch = await fetchSearchRunEvents(runId, {
        afterSequence: lastSeq.current,
        limit: 200,
      })
      if (batch.length === 0) return
      lastSeq.current = Math.max(lastSeq.current, ...batch.map((e) => e.sequence))

      setEvents((prev) => {
        const merged = [...prev]
        const seen = new Set(merged.map((e) => e.id))
        const newIds = new Set<string>()
        for (const e of batch) {
          if (!seen.has(e.id)) {
            merged.push(e)
            seen.add(e.id)
            newIds.add(e.id)
          }
        }
        merged.sort((a, b) => a.sequence - b.sequence)

        if (newIds.size > 0) {
          queueMicrotask(() => {
            scheduleDebouncedRunRefresh()
            setFreshIds((prev) => new Set([...prev, ...newIds]))
            setTimeout(() => {
              setFreshIds((prev) => {
                const next = new Set(prev)
                newIds.forEach((id) => next.delete(id))
                return next
              })
            }, 2500)
          })
        }

        return merged
      })
    } catch {
      // transient — next tick retries
    }
  }, [runId, scheduleDebouncedRunRefresh])

  useEffect(() => {
    const prev = prevRunIdRef.current
    prevRunIdRef.current = runId
    if (prev !== null && prev !== runId) {
      lastSeq.current = -1
      setEvents([])
    }
  }, [runId])

  useEffect(() => {
    let runTimer: ReturnType<typeof setInterval> | undefined
    let evTimer: ReturnType<typeof setInterval> | undefined

    const clearTimers = () => {
      if (runTimer != null) clearInterval(runTimer)
      if (evTimer != null) clearInterval(evTimer)
    }

    const start = () => {
      clearTimers()
      const r = runRef.current
      const terminal = r != null && TERMINAL.has(r.status)
      if (terminal) {
        void refreshRun()
        void pollEvents()
        return
      }
      void pollEvents()
      void refreshRun()
      evTimer = setInterval(() => void pollEvents(), 1000)
      runTimer = setInterval(() => void refreshRun(), 1750)
    }

    start()

    return () => {
      clearTimers()
      if (debouncedRefreshTimer.current) {
        clearTimeout(debouncedRefreshTimer.current)
        debouncedRefreshTimer.current = null
      }
    }
  }, [refreshRun, pollEvents, run?.id, run?.status])

  const handleStop = async () => {
    await stopSearchRun(runId)
    await refreshRun()
  }

  if (loadError && !run) {
    return (
      <p className="text-sm text-red-600 dark:text-red-400" role="alert">
        {loadError}
      </p>
    )
  }

  if (!run) {
    return <p className="text-sm text-slate-500">Loading run…</p>
  }

  const userEvents = events.filter((e) => e.visibility === 'user')
  const warnings = userEvents.filter(
    (e) => e.event_type.includes('warning') || e.event_type.includes('error'),
  )
  const terminal = TERMINAL.has(run.status)

  // Latest found listing for the highlight card
  const latestFind = [...userEvents]
    .reverse()
    .find((e) => e.event_type === 'listing_found')

  // Stage breadcrumb
  const currentStageIdx = terminal
    ? STAGE_ORDER.length - 1
    : stageIndex(run.current_stage)

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium tracking-widest text-slate-400 uppercase dark:text-slate-500">
            Search run
          </p>
          <h1 className="font-display text-2xl font-medium text-slate-900 dark:text-slate-100">
            {run.city}
          </h1>
          {terminal ? (
            <p className="mt-1 text-sm capitalize text-slate-500 dark:text-slate-400">
              {run.status}
            </p>
          ) : null}
          <p className="mt-2">
            <Link
              href={`/listings?run=${run.id}&category=great_match`}
              className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
            >
              Browse listings by category
            </Link>
          </p>
        </div>
        <RunControls run={run} onStop={handleStop} />
      </header>

      {/* Stage breadcrumb */}
      <StageIndicator currentIndex={currentStageIdx} terminal={terminal} />

      <section aria-labelledby="counters-heading">
        <h2 id="counters-heading" className="sr-only">
          Run counters
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Counter label="Sources" value={run.sources_checked} />
          <Counter label="Managers" value={run.managers_validated} />
          <Counter label="Listings seen" value={run.listings_seen} />
          <Counter label="Extraction attempts" value={run.extraction_attempts ?? 0} />
          <Counter label="Cost (USD)" value={run.cost_usd_so_far} decimals={3} />
          <Counter label="Great matches" value={run.great_matches} accent="green" />
          <Counter label="Worth a look" value={run.worth_a_look} accent="blue" />
          <Counter label="Near misses" value={run.near_misses} accent="amber" />
          <Counter label="Filtered out" value={run.filtered_out} />
        </div>
      </section>

      {/* Latest find highlight card */}
      {latestFind ? (
        <div className="flex items-start gap-3 rounded-2xl border border-green-200 bg-green-50/70 px-4 py-3 dark:border-green-900/40 dark:bg-green-950/20">
          <span className="mt-0.5 text-green-500 dark:text-green-400" aria-hidden>✓</span>
          <div className="min-w-0">
            <p className="text-xs font-medium text-green-700 dark:text-green-400">Latest find</p>
            <p className="truncate text-sm text-green-900 dark:text-green-200">{latestFind.message}</p>
          </div>
          <span className="ml-auto shrink-0 text-xs text-green-600/60 dark:text-green-500/50">
            {relativeTime(latestFind.timestamp, now)}
          </span>
        </div>
      ) : null}

      {/* Live activity feed */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
        <h2 className="font-display text-lg font-medium text-slate-900 dark:text-slate-100">
          Live activity
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Real-time updates as the agent works.
        </p>
        <ul className="mt-4 max-h-80 space-y-1.5 overflow-y-auto text-sm">
          {userEvents.length === 0 ? (
            <li className="text-slate-400 dark:text-slate-600">Waiting for activity…</li>
          ) : (
            userEvents
              .slice(-50)
              .reverse()
              .map((e) => {
                const payloadLine = eventPayloadDetail(e.payload_json)
                return (
                  <li
                    key={e.id}
                    className={clsx(
                      'flex items-start gap-2 rounded-lg px-2 py-1 transition-colors duration-700',
                      freshIds.has(e.id)
                        ? 'bg-blue-50 dark:bg-blue-950/30'
                        : 'hover:bg-slate-50 dark:hover:bg-slate-900/40',
                    )}
                  >
                    <span
                      className={clsx(
                        'mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                        eventBadge(e.event_type),
                      )}
                    >
                      {e.event_type.replace(/_/g, ' ')}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-slate-800 dark:text-slate-100">{e.message}</p>
                      {payloadLine ? (
                        <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-500">
                          {payloadLine}
                        </p>
                      ) : null}
                    </div>
                    <span className="shrink-0 text-xs text-slate-400 dark:text-slate-600">
                      {relativeTime(e.timestamp, now)}
                    </span>
                  </li>
                )
              })
          )}
        </ul>
      </section>

      {warnings.length > 0 ? (
        <section
          className="rounded-2xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-900/50 dark:bg-amber-950/30"
          aria-label="Warnings"
        >
          <h2 className="font-display text-lg font-medium text-amber-900 dark:text-amber-100">
            Warnings
          </h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-900/90 dark:text-amber-100/90">
            {warnings.map((e) => (
              <li key={e.id}>{e.message}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950">
        <h2 className="font-display text-lg font-medium text-slate-900 dark:text-slate-100">
          Filter suggestions
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Based on how listings matched your filters — useful nudges, not guarantees.
        </p>
        <div className="mt-4">
          <RunSuggestions run={run} suggestions={run.suggestions} />
        </div>
      </section>

      <RunFilterControls run={run} onPatched={setRun} />

      {terminal ? (
        <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
          Final state: <span className="capitalize">{run.status}</span>
          {run.finished_at ? (
            <span className="text-slate-400">
              {' '}
              · {new Date(run.finished_at).toLocaleString()}
            </span>
          ) : null}
        </p>
      ) : null}

      <RunTechnicalDetails events={events} />
    </div>
  )
}

// ─── Stage breadcrumb ─────────────────────────────────────────────────────────

function StageIndicator({
  currentIndex,
  terminal,
}: {
  currentIndex: number
  terminal: boolean
}) {
  return (
    <nav aria-label="Run stages" className="flex items-center gap-1 text-xs">
      {STAGE_ORDER.map((stage, i) => {
        const done = terminal ? true : i < currentIndex
        const active = !terminal && i === currentIndex
        const pending = !terminal && i > currentIndex

        return (
          <div key={stage} className="flex items-center gap-1">
            {i > 0 && (
              <div
                className={clsx(
                  'h-px w-6 sm:w-10',
                  done || active ? 'bg-blue-400 dark:bg-blue-600' : 'bg-slate-200 dark:bg-slate-800',
                )}
              />
            )}
            <div className="flex items-center gap-1">
              <span
                className={clsx(
                  'flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold',
                  done && 'bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400',
                  active &&
                    'bg-blue-600 text-white shadow-sm shadow-blue-600/40 animate-pulse',
                  pending && 'bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-600',
                )}
              >
                {done ? '✓' : i + 1}
              </span>
              <span
                className={clsx(
                  'capitalize',
                  active && 'font-semibold text-blue-700 dark:text-blue-400',
                  done && 'text-slate-500 dark:text-slate-400',
                  pending && 'text-slate-400 dark:text-slate-600',
                )}
              >
                {stage}
              </span>
            </div>
          </div>
        )
      })}
    </nav>
  )
}

// ─── Counter tile ─────────────────────────────────────────────────────────────

function Counter({
  label,
  value,
  decimals,
  accent,
}: {
  label: string
  value: number
  decimals?: number
  accent?: 'green' | 'amber' | 'blue'
}) {
  const prev = useRef<number | null>(null)
  const [valuePulse, setValuePulse] = useState(false)

  useEffect(() => {
    if (prev.current === null) {
      prev.current = value
      return
    }
    if (prev.current !== value) {
      prev.current = value
      setValuePulse(true)
      const t = setTimeout(() => setValuePulse(false), 420)
      return () => clearTimeout(t)
    }
  }, [value])

  return (
    <div
      className={clsx(
        'rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 transition-[box-shadow,background-color] duration-300 dark:border-slate-800 dark:bg-slate-900/60',
        accent === 'green' &&
          'border-green-200 bg-green-50/80 dark:border-green-900/40 dark:bg-green-950/20',
        accent === 'amber' &&
          'border-amber-200 bg-amber-50/80 dark:border-amber-900/40 dark:bg-amber-950/20',
        accent === 'blue' &&
          'border-blue-200 bg-blue-50/80 dark:border-blue-900/40 dark:bg-blue-950/20',
        valuePulse &&
          'ring-2 ring-blue-500/35 ring-offset-2 ring-offset-slate-50 dark:ring-blue-400/30 dark:ring-offset-slate-950',
      )}
    >
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
      <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
        <AnimatedCounter value={value} decimals={decimals} />
      </p>
    </div>
  )
}
