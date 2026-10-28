'use client'

import clsx from 'clsx'

export type FilterReason = {
  filter_code?: string
  label?: string
  expected?: string
  actual?: string
  severity?: string
  suggestion?: string
  verdict?: 'confirmed' | 'likely_compromise' | 'not_possible' | 'unclear'
  evidence?: string
  photo_index?: number | null
  confidence?: 'high' | 'medium' | 'low'
  is_visual?: boolean
}

type FilterReasonListProps = {
  reasonsJson: string | null
  onPhotoClick?: (photoIndex: number) => void
}
export function parseFilterReasons(raw: string | null): FilterReason[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw) as unknown
    return Array.isArray(v) ? (v as FilterReason[]) : []
  } catch {
    return []
  }
}

export function FilterReasonList({ reasonsJson, onPhotoClick }: FilterReasonListProps) {
  const reasons = parseFilterReasons(reasonsJson)
  if (reasons.length === 0) {
    return null
  }

  const visualReasons = reasons.filter((r) => r.is_visual || r.verdict != null)
  const standardReasons = reasons.filter((r) => !r.is_visual && r.verdict == null)

  return (
    <div className="space-y-3">
      {visualReasons.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-2">
          {visualReasons.map((vr, i) => {
            const isConfirmed = vr.verdict === 'confirmed'
            const isCompromise = vr.verdict === 'likely_compromise'
            const isNotPossible = vr.verdict === 'not_possible'

            return (
              <div
                key={`${vr.filter_code ?? 'v'}-${i}`}
                className={clsx(
                  'flex flex-col rounded-xl border p-2.5 text-xs transition-all shadow-xs',
                  isConfirmed
                    ? 'border-emerald-200 bg-emerald-50/90 text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200'
                    : isCompromise
                      ? 'border-amber-200 bg-amber-50/90 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200'
                      : isNotPossible
                        ? 'border-rose-200 bg-rose-50/90 text-rose-950 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200'
                        : 'border-slate-200 bg-slate-50 text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'
                )}
              >
                <div className="flex items-center gap-1.5 font-semibold">
                  <span aria-hidden="true">
                    {isConfirmed ? '🟢' : isCompromise ? '🟡' : isNotPossible ? '🔴' : '⚪'}
                  </span>
                  <span>{vr.label}</span>
                  {vr.photo_index != null && (
                    <button
                      type="button"
                      onClick={() => onPhotoClick?.(vr.photo_index!)}
                      className={clsx(
                        'ml-1 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide transition-opacity hover:opacity-80',
                        isConfirmed
                          ? 'bg-emerald-200/80 text-emerald-950 dark:bg-emerald-900 dark:text-emerald-100'
                          : isCompromise
                            ? 'bg-amber-200/80 text-amber-950 dark:bg-amber-900 dark:text-amber-100'
                            : 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-200'
                      )}
                    >
                      Photo {vr.photo_index}
                    </button>
                  )}
                </div>
                {vr.evidence && (
                  <p className="mt-1 text-[11px] leading-snug opacity-90">
                    {vr.evidence}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}

      {standardReasons.length > 0 && (
        <ul className="mt-2 space-y-2 border-l-2 border-slate-200 pl-3 text-xs dark:border-slate-700">
          {standardReasons.map((r, i) => (
            <li key={`${r.filter_code ?? 'r'}-${i}`}>
              {r.label ? (
                <p className="font-medium text-slate-800 dark:text-slate-200">{r.label}</p>
              ) : null}
              <p className="text-slate-600 dark:text-slate-400">
                {r.expected != null && <span>Expected {r.expected}</span>}
                {r.expected != null && r.actual != null && <span> · </span>}
                {r.actual != null && <span>got {r.actual}</span>}
              </p>
              {r.severity ? (
                <p className="mt-0.5 text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500">
                  {r.severity.replace(/_/g, ' ')}
                </p>
              ) : null}
              {r.suggestion ? (
                <p className="mt-1 text-slate-500 dark:text-slate-400">{r.suggestion}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
