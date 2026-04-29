'use client'

import { useState, useEffect } from 'react'
import clsx from 'clsx'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { Container } from '@/components/Container'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const SKELETON_HEIGHTS = [24, 46, 34, 62, 28, 72, 40, 55, 30, 68, 38, 50, 26, 64, 44, 58, 32, 70, 36, 52]

interface CostSummary {
  total_cost_usd: number
  total_calls: number
  total_tokens: number
  avg_cost_per_call: number
  cache_hit_rate: number
  budget_limit_usd: number
  budget_remaining_usd: number
  budget_exceeded: boolean
}

interface CostGrouped {
  group: string
  cost_usd: number
  call_count: number
  tokens_total: number
}

interface CostTimeseries {
  date: string
  cost_usd: number
  call_count: number
  tokens_total: number
}

function fmtCost(usd: number): string {
  if (usd === 0) return '$0.00'
  if (usd >= 1) return `$${usd.toFixed(2)}`
  if (usd >= 0.01) return `$${usd.toFixed(3)}`
  return `$${usd.toFixed(4)}`
}

function fmtCostFine(usd: number): string {
  if (usd === 0) return '$0.0000'
  if (usd >= 0.0001) return `$${usd.toFixed(4)}`
  return '< $0.0001'
}

export default function CostsPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null)
  const [byComponent, setByComponent] = useState<CostGrouped[]>([])
  const [byModel, setByModel] = useState<CostGrouped[]>([])
  const [timeseries, setTimeseries] = useState<CostTimeseries[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchJson = async <T,>(path: string): Promise<T> => {
      const r = await fetch(`${API}${path}`)
      if (!r.ok) throw new Error(`Cost API returned ${r.status}`)
      return r.json() as Promise<T>
    }

    Promise.all([
      fetchJson<CostSummary>('/api/costs/summary'),
      fetchJson<CostGrouped[]>('/api/costs/by-component'),
      fetchJson<CostGrouped[]>('/api/costs/by-model'),
      fetchJson<CostTimeseries[]>('/api/costs/timeseries?days=30'),
    ])
      .then(([sum, comp, model, ts]) => {
        setError(null)
        setSummary(sum)
        setByComponent(comp)
        setByModel(model)
        setTimeseries(ts)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Could not load cost data')
      })
      .finally(() => setLoading(false))
  }, [])

  const maxDayCost = Math.max(...timeseries.map((d) => d.cost_usd), 0.0001)
  const maxGroupCost = Math.max(
    ...byComponent.map((e) => e.cost_usd),
    ...byModel.map((e) => e.cost_usd),
    0.0001,
  )
  const budgetPct = summary
    ? Math.min((summary.total_cost_usd / summary.budget_limit_usd) * 100, 100)
    : 0

  return (
    <>
      <Header />
      <main className="flex-1">
        <Container className="pb-20 pt-12">
          <div className="mx-auto max-w-4xl">

            {/* Page header */}
            <div className="mb-10">
              <p className="text-xs font-medium uppercase tracking-widest text-slate-400 dark:text-slate-500">
                Costs
              </p>
              <h1 className="mt-1 font-display text-3xl font-medium tracking-tight text-slate-900 dark:text-slate-100">
                AI spending
              </h1>
            </div>

            {error && (
              <div
                role="alert"
                className="mb-8 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300"
              >
                {error}. Check that the backend is running and migrations are applied.
              </div>
            )}

            {/* Spend overview */}
            {loading ? (
              <div className="space-y-3">
                <div className="h-10 w-28 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
                <div className="h-4 w-56 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
                <div className="mt-5 h-2 w-full animate-pulse rounded-full bg-slate-100 dark:bg-slate-800" />
              </div>
            ) : summary ? (
              <div>
                <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
                  <span
                    className={clsx(
                      'font-display text-4xl font-semibold tabular-nums tracking-tight',
                      summary.budget_exceeded
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-slate-900 dark:text-slate-100',
                    )}
                  >
                    {fmtCost(summary.total_cost_usd)}
                  </span>
                  <span className="text-sm text-slate-500 dark:text-slate-400">
                    spent this month
                    {summary.budget_exceeded && (
                      <span className="ml-2 font-medium text-red-600 dark:text-red-400">
                        · budget exceeded
                      </span>
                    )}
                  </span>
                </div>

                <div className="mt-3 flex flex-wrap gap-x-6 gap-y-0.5 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">
                    <span className="font-medium text-slate-700 dark:text-slate-300">
                      {summary.total_calls.toLocaleString()}
                    </span>{' '}
                    API calls
                  </span>
                  <span className="text-slate-500 dark:text-slate-400">
                    <span className="font-medium text-slate-700 dark:text-slate-300">
                      {fmtCostFine(summary.avg_cost_per_call)}
                    </span>{' '}
                    avg / call
                  </span>
                  {summary.total_tokens > 0 && (
                    <span className="text-slate-500 dark:text-slate-400">
                      <span className="font-medium text-slate-700 dark:text-slate-300">
                        {summary.total_tokens.toLocaleString()}
                      </span>{' '}
                      tokens
                    </span>
                  )}
                </div>

                <div className="mt-5">
                  <div className="flex items-center justify-between text-xs text-slate-400 dark:text-slate-500">
                    <span>Budget</span>
                    <span>
                      {fmtCost(summary.budget_remaining_usd)} of {fmtCost(summary.budget_limit_usd)} remaining
                      {' '}· {budgetPct.toFixed(1)}% used
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700/60">
                    <div
                      className={clsx(
                        'h-full rounded-full transition-all duration-500',
                        summary.budget_exceeded
                          ? 'bg-red-500'
                          : 'bg-blue-500 dark:bg-blue-400',
                      )}
                      style={{ width: `${budgetPct}%` }}
                    />
                  </div>
                </div>
              </div>
            ) : null}

            {/* Daily chart */}
            <div className="mt-14">
              <p className="text-xs font-medium uppercase tracking-widest text-slate-400 dark:text-slate-500">
                Daily spend, last 30 days
              </p>

              <div className="mt-4 rounded-xl border border-slate-200 bg-white px-4 pb-3 pt-4 dark:border-slate-700/50 dark:bg-slate-900/40">
                <div className="flex h-36 items-end gap-px">
                  {loading ? (
                    SKELETON_HEIGHTS.map((h, i) => (
                      <div
                        key={i}
                        className="flex-1 animate-pulse rounded-t bg-slate-100 dark:bg-slate-800"
                        style={{ height: `${h}%` }}
                      />
                    ))
                  ) : timeseries.length > 0 ? (
                    timeseries.map((day) => {
                      const h = Math.max(
                        (day.cost_usd / maxDayCost) * 100,
                        day.cost_usd > 0 ? 5 : 0,
                      )
                      return (
                        <div key={day.date} className="group relative flex-1 self-end">
                          {h > 0 ? (
                            <button
                              type="button"
                              aria-label={`${day.date}: ${fmtCostFine(day.cost_usd)}, ${day.call_count} calls`}
                              className="w-full rounded-t bg-blue-400 transition-colors hover:bg-blue-600 dark:bg-blue-500 dark:hover:bg-blue-400"
                              style={{ height: `${h}%`, display: 'block' }}
                            />
                          ) : (
                            <div className="w-full rounded-t" style={{ height: '2px', background: 'transparent' }} />
                          )}
                          <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs leading-snug text-slate-100 shadow-lg group-hover:block dark:bg-slate-700">
                            <span className="font-medium">{day.date}</span>
                            <br />
                            {fmtCostFine(day.cost_usd)} · {day.call_count} calls
                          </div>
                        </div>
                      )
                    })
                  ) : (
                    <div className="flex w-full items-center justify-center text-sm text-slate-400 dark:text-slate-500">
                      No data yet
                    </div>
                  )}
                </div>
                {!loading && timeseries.length > 0 && (
                  <div className="mt-2 flex justify-between text-xs text-slate-400 dark:text-slate-500">
                    <span>{timeseries[0]?.date}</span>
                    <span>{timeseries[timeseries.length - 1]?.date}</span>
                  </div>
                )}
              </div>

              {/* Last 7 days table */}
              {!loading && timeseries.filter((d) => d.call_count > 0).length > 0 && (
                <div className="mt-3">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr>
                        <th scope="col" className="pb-2 pr-8 text-xs font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">
                          Date
                        </th>
                        <th scope="col" className="pb-2 pr-8 text-xs font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">
                          Spend
                        </th>
                        <th scope="col" className="pb-2 text-xs font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">
                          Calls
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {[...timeseries].reverse().slice(0, 7).map((day) => (
                        <tr key={day.date}>
                          <td className="py-2 pr-8 tabular-nums text-slate-500 dark:text-slate-400">
                            {day.date}
                          </td>
                          <td className="py-2 pr-8 tabular-nums font-medium text-slate-900 dark:text-slate-100">
                            {fmtCostFine(day.cost_usd)}
                          </td>
                          <td className="py-2 tabular-nums text-slate-500 dark:text-slate-400">
                            {day.call_count}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Breakdowns */}
            {!loading && (byComponent.length > 0 || byModel.length > 0) && (
              <div className="mt-14 grid gap-10 sm:grid-cols-2">
                <BreakdownSection title="By component" entries={byComponent} maxCost={maxGroupCost} />
                <BreakdownSection title="By model" entries={byModel} maxCost={maxGroupCost} />
              </div>
            )}

          </div>
        </Container>
      </main>
      <Footer />
    </>
  )
}

function BreakdownSection({
  title,
  entries,
  maxCost,
}: {
  title: string
  entries: CostGrouped[]
  maxCost: number
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-widest text-slate-400 dark:text-slate-500">
        {title}
      </p>
      {entries.length === 0 ? (
        <p className="mt-4 text-sm text-slate-400 dark:text-slate-500">No data yet.</p>
      ) : (
        <div className="mt-4 space-y-5">
          {entries.map((entry) => {
            const barPct = maxCost > 0 ? (entry.cost_usd / maxCost) * 100 : 0
            return (
              <div key={entry.group}>
                <div className="flex items-baseline justify-between gap-x-3">
                  <span className="truncate text-sm font-medium capitalize text-slate-800 dark:text-slate-200">
                    {entry.group}
                  </span>
                  <span className="shrink-0 tabular-nums text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {fmtCost(entry.cost_usd)}
                  </span>
                </div>
                <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    className="h-full rounded-full bg-blue-500 dark:bg-blue-400"
                    style={{ width: `${barPct}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                  {entry.call_count} calls · {entry.tokens_total.toLocaleString()} tokens
                </p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
