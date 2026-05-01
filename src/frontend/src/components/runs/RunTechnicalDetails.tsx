'use client'

import { useId, useState } from 'react'
import clsx from 'clsx'

import type { SearchRunEvent } from '@/client/search-runs'

type RunTechnicalDetailsProps = {
  events: SearchRunEvent[]
}

function parsePayload(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null
  try {
    const v = JSON.parse(raw) as unknown
    return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null
  } catch {
    return null
  }
}

export function RunTechnicalDetails({ events }: RunTechnicalDetailsProps) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const devEvents = events.filter((e) => e.visibility === 'developer')

  if (devEvents.length === 0) {
    return null
  }

  return (
    <section className="mt-8 rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <button
        type="button"
        id={`${panelId}-btn`}
        aria-expanded={open}
        aria-controls={`${panelId}-panel`}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-2xl px-5 py-3 text-left text-sm font-medium text-slate-800 hover:bg-slate-50 dark:text-slate-100 dark:hover:bg-slate-900"
      >
        <span>Technical details</span>
        <span className="text-slate-400" aria-hidden="true">
          {open ? '−' : '+'}
        </span>
      </button>
      {open ? (
        <div
          id={`${panelId}-panel`}
          role="region"
          aria-labelledby={`${panelId}-btn`}
          className="border-t border-slate-100 px-5 py-4 dark:border-slate-800"
        >
          <ul className="space-y-3 font-mono text-xs text-slate-600 dark:text-slate-300">
            {devEvents.slice(-40).map((e) => {
              const payload = parsePayload(e.payload_json)
              return (
                <li key={e.id} className="break-words">
                  <span className="text-slate-400 dark:text-slate-500">#{e.sequence}</span>{' '}
                  <span className={clsx('font-semibold', e.event_type.includes('error') && 'text-red-600')}>
                    {e.event_type}
                  </span>
                  {payload ? (
                    <pre className="mt-1 max-h-40 overflow-auto rounded-lg bg-slate-50 p-2 text-[11px] dark:bg-slate-900">
                      {JSON.stringify(payload, null, 2)}
                    </pre>
                  ) : null}
                </li>
              )
            })}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
