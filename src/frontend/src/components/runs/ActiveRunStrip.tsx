'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import clsx from 'clsx'

import { useActiveRun } from '@/components/runs/ActiveRunProvider'
import { RunControls } from '@/components/runs/RunControls'

function formatElapsed(startedAt: string): string {
  const start = new Date(startedAt).getTime()
  const sec = Math.max(0, Math.floor((Date.now() - start) / 1000))
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export function ActiveRunStrip() {
  const { run, loading, error, stop } = useActiveRun()
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!run) return
    const id = setInterval(() => setTick((t) => t + 1), 1000)
    return () => clearInterval(id)
  }, [run])

  const elapsed = run ? formatElapsed(run.started_at) : ''

  if (loading && !run) {
    return null
  }

  if (!run) {
    if (error) {
      return (
        <div
          className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-200"
          role="status"
        >
          Active run unavailable: {error}
        </div>
      )
    }
    return null
  }

  const cost = run.cost_usd_so_far.toFixed(3)

  return (
    <div
      className="border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900/80"
      role="region"
      aria-label="Active search run"
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-2 sm:px-6 lg:px-8">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-700 dark:text-slate-200">
          <span className="font-medium capitalize">{run.current_stage.replace(/_/g, ' ')}</span>
          <span className="text-slate-400 dark:text-slate-500" aria-hidden="true">
            ·
          </span>
          <span className="tabular-nums text-slate-600 dark:text-slate-300" title="Elapsed time">
            {elapsed}
          </span>
          <span className="text-slate-400 dark:text-slate-500" aria-hidden="true">
            ·
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            mgr {run.managers_validated} · listings {run.listings_seen} · great {run.great_matches}
          </span>
          <span className="text-slate-400 dark:text-slate-500" aria-hidden="true">
            ·
          </span>
          <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">${cost}</span>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Link
            href={`/runs/${run.id}`}
            className={clsx(
              'text-sm font-medium text-blue-600 hover:underline dark:text-blue-400',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-900',
            )}
          >
            Open report
          </Link>
          <RunControls run={run} onStop={stop} compact />
        </div>
      </div>
    </div>
  )
}
