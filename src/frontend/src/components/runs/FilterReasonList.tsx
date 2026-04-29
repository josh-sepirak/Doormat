'use client'

export type FilterReason = {
  filter_code?: string
  label?: string
  expected?: string
  actual?: string
  severity?: string
  suggestion?: string
}

type FilterReasonListProps = {
  reasonsJson: string | null
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

export function FilterReasonList({ reasonsJson }: FilterReasonListProps) {
  const reasons = parseFilterReasons(reasonsJson)
  if (reasons.length === 0) {
    return null
  }

  return (
    <ul className="mt-2 space-y-2 border-l-2 border-slate-200 pl-3 text-xs dark:border-slate-700">
      {reasons.map((r, i) => (
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
  )
}
