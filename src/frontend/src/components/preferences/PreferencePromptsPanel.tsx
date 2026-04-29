'use client'

import { useCallback, useEffect, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type PromptEntry = {
  key: string
  title: string
  description: string
  max_length: number
  placeholders: string[]
  default_text: string
  effective_text: string
  is_custom: boolean
}

type Envelope = { prompts: PromptEntry[] }

export function PreferencePromptsPanel({ preferenceId }: { preferenceId: string }) {
  const [data, setData] = useState<Envelope | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [busyAll, setBusyAll] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetch(`${API}/api/preferences/${encodeURIComponent(preferenceId)}/prompts`)
      if (!r.ok) throw new Error(r.statusText)
      const j = (await r.json()) as Envelope
      setData(j)
      const d: Record<string, string> = {}
      for (const p of j.prompts) d[p.key] = p.effective_text
      setDrafts(d)
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed to load prompts')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [preferenceId])

  useEffect(() => {
    void load()
  }, [load])

  const patch = async (body: Record<string, unknown>) => {
    const r = await fetch(`${API}/api/preferences/${encodeURIComponent(preferenceId)}/prompts`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      const detail = (j as { detail?: string }).detail || r.statusText
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    }
    const j = (await r.json()) as Envelope
    setData(j)
    const d: Record<string, string> = {}
    for (const p of j.prompts) d[p.key] = p.effective_text
    setDrafts(d)
  }

  const saveOne = async (key: string) => {
    setBusyKey(key)
    setErr(null)
    try {
      await patch({ overrides: { [key]: drafts[key] ?? '' } })
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setBusyKey(null)
    }
  }

  const resetOne = async (key: string) => {
    setBusyKey(key)
    setErr(null)
    try {
      await patch({ reset_keys: [key] })
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setBusyKey(null)
    }
  }

  const resetAll = async () => {
    setBusyAll(true)
    setErr(null)
    try {
      await patch({ reset_all: true })
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setBusyAll(false)
    }
  }

  if (loading) {
    return <p className="mt-8 text-sm text-slate-500">Loading prompt templates…</p>
  }
  if (!data?.prompts.length) {
    return err ? (
      <p className="mt-8 text-sm text-red-600 dark:text-red-400">{err}</p>
    ) : null
  }

  return (
    <section className="mt-12 border-t border-slate-200 pt-10 dark:border-slate-700">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-medium text-slate-900 dark:text-slate-100">
            Advanced: LLM prompts
          </h2>
          <p className="mt-1 max-w-xl text-sm text-slate-600 dark:text-slate-400">
            Shipped defaults live in the app code and are never overwritten. Your edits are stored only
            on this preference and apply when a preference is attached (scoring, discovery, extraction).
          </p>
        </div>
        <button
          type="button"
          onClick={() => void resetAll()}
          disabled={busyAll}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          {busyAll ? 'Resetting…' : 'Reset all to defaults'}
        </button>
      </div>

      {err && (
        <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-200">
          {err}
        </p>
      )}

      <div className="mt-6 space-y-3">
        {data.prompts.map((p) => (
          <details
            key={p.key}
            className="group rounded-xl border border-slate-200 bg-white open:shadow-sm dark:border-slate-700 dark:bg-slate-900/50"
          >
            <summary className="cursor-pointer list-none px-4 py-3 [&::-webkit-details-marker]:hidden">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium text-slate-900 dark:text-slate-100">{p.title}</span>
                {p.is_custom ? (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
                    Custom
                  </span>
                ) : (
                  <span className="text-xs text-slate-400">Default</span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{p.description}</p>
            </summary>
            <div className="space-y-3 border-t border-slate-100 px-4 py-4 dark:border-slate-800">
              {p.placeholders.length > 0 && (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Required placeholders: <code className="text-slate-700 dark:text-slate-300">{p.placeholders.join(', ')}</code>
                </p>
              )}
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                Max {p.max_length.toLocaleString()} characters
              </p>
              <textarea
                className="min-h-[8rem] w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                value={drafts[p.key] ?? ''}
                onChange={(e) => setDrafts((d) => ({ ...d, [p.key]: e.target.value }))}
                spellCheck={false}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busyKey === p.key}
                  onClick={() => void saveOne(p.key)}
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
                >
                  {busyKey === p.key ? 'Saving…' : 'Save this prompt'}
                </button>
                <button
                  type="button"
                  disabled={busyKey === p.key || !p.is_custom}
                  onClick={() => void resetOne(p.key)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  {busyKey === p.key ? '…' : 'Reset to default'}
                </button>
                <button
                  type="button"
                  onClick={() => setDrafts((d) => ({ ...d, [p.key]: p.default_text }))}
                  className="rounded-lg px-3 py-1.5 text-xs text-slate-500 underline hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                >
                  Fill with shipped default (preview)
                </button>
              </div>
            </div>
          </details>
        ))}
      </div>
    </section>
  )
}
