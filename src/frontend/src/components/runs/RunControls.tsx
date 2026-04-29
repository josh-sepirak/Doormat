'use client'

import { useState } from 'react'
import clsx from 'clsx'

import type { SearchRun } from '@/client/search-runs'

type RunControlsProps = {
  run: SearchRun
  onStop: () => Promise<void>
  compact?: boolean
}

const TERMINAL = new Set(['success', 'error', 'cancelled'])

export function RunControls({ run, onStop, compact }: RunControlsProps) {
  const [pending, setPending] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const terminal = TERMINAL.has(run.status)
  const stopping =
    !terminal && (run.cancel_requested || run.status === 'cancel_requested')

  const handleStop = async () => {
    setLocalError(null)
    setPending(true)
    try {
      await onStop()
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : 'Stop failed')
    } finally {
      setPending(false)
    }
  }

  if (terminal) {
    const label =
      run.status === 'cancelled'
        ? 'Cancelled'
        : run.status === 'error'
          ? 'Ended with error'
          : 'Finished'
    return (
      <span
        className={clsx(
          'text-xs font-medium',
          run.status === 'cancelled' && 'text-amber-700 dark:text-amber-400',
          run.status === 'error' && 'text-red-600 dark:text-red-400',
          run.status === 'success' && 'text-slate-500 dark:text-slate-400',
        )}
      >
        {label}
      </span>
    )
  }

  if (stopping) {
    return (
      <span className="text-xs font-medium text-slate-600 dark:text-slate-300" aria-live="polite">
        Stopping…
      </span>
    )
  }

  return (
    <div className={clsx('flex flex-col items-end gap-1', compact && 'items-stretch')}>
      <button
        type="button"
        onClick={() => void handleStop()}
        disabled={pending}
        className={clsx(
          'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-800 shadow-sm hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800',
          compact && 'w-full text-center',
        )}
      >
        {pending ? 'Stopping…' : 'Stop run'}
      </button>
      {localError ? (
        <span className="text-xs text-red-600 dark:text-red-400" role="alert">
          {localError}
        </span>
      ) : null}
    </div>
  )
}
