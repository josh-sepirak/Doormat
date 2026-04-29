'use client'

import clsx from 'clsx'

import type { SearchRun, SearchRunSuggestion } from '@/client/search-runs'

type RunSuggestionsProps = {
  run: SearchRun
  suggestions: SearchRunSuggestion[]
}

export function RunSuggestions({ run, suggestions }: RunSuggestionsProps) {
  if (suggestions.length === 0) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        No filter suggestions yet — results will refine as the run progresses.
      </p>
    )
  }

  return (
    <div>
      <p
        className={clsx(
          'mb-3 text-xs font-medium tracking-wide uppercase',
          run.suggestions_early_signal
            ? 'text-amber-700 dark:text-amber-400'
            : 'text-slate-500 dark:text-slate-400',
        )}
      >
        {run.suggestions_early_signal ? 'Early signal (may shift as listings arrive)' : 'Final for this run'}
      </p>
      <ul className="space-y-3">
        {suggestions.map((s, idx) => (
          <li
            key={`${s.kind}-${idx}`}
            className="rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-200"
          >
            <span className="font-medium">{s.message}</span>
            {s.count > 0 ? (
              <span className="ml-2 tabular-nums text-slate-500 dark:text-slate-400">({s.count})</span>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-slate-500 dark:text-slate-500">
        Suggestions are computed from your filters and listing data — no extra model calls.
      </p>
    </div>
  )
}
