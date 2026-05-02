'use client'

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  deleteTrustedSource,
  fetchTrustedSources,
  testTrustedSource,
  type TrustedSource,
} from '@/client/trusted-sources'
import { AddCraigslistRegionModal } from '@/components/sources/AddCraigslistRegionModal'
import { AddPropertyManagerModal } from '@/components/sources/AddPropertyManagerModal'
import { Button } from '@/components/Button'
import { Container } from '@/components/Container'
import { Footer } from '@/components/Footer'
import { Header } from '@/components/Header'

export function SourcesPageClient() {
  const searchParams = useSearchParams()
  const [rows, setRows] = useState<TrustedSource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [clOpen, setClOpen] = useState(false)
  const [pmOpen, setPmOpen] = useState(false)
  const [clMountKey, setClMountKey] = useState(0)
  const [pmMountKey, setPmMountKey] = useState(0)
  const [prefillCity, setPrefillCity] = useState('')
  const [prefillState, setPrefillState] = useState('CA')
  const [testStatus, setTestStatus] = useState<Record<string, string>>({})

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchTrustedSources()
      setRows(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const open = searchParams.get('addRegion')
    const city = searchParams.get('city') || ''
    const st = searchParams.get('state') || 'CA'
    if (open === '1') {
      setPrefillCity(city)
      setPrefillState(st)
      setClMountKey((k) => k + 1)
      setClOpen(true)
    }
  }, [searchParams])

  const clRows = rows.filter((r) => r.kind === 'craigslist_region')
  const pmRows = rows.filter((r) => r.kind === 'property_manager')

  async function onTest(id: string) {
    setTestStatus((m) => ({ ...m, [id]: '…' }))
    try {
      const r = await testTrustedSource(id)
      setTestStatus((m) => ({
        ...m,
        [id]: r.ok ? `OK (${r.status_code ?? '—'})` : r.detail || 'Failed',
      }))
    } catch (e) {
      setTestStatus((m) => ({ ...m, [id]: e instanceof Error ? e.message : 'Error' }))
    }
  }

  async function onRemove(id: string) {
    if (!confirm('Remove this trusted source?')) return
    await deleteTrustedSource(id)
    await load()
  }

  return (
    <>
      <Header />
      <main className="py-12">
        <Container>
          <div className="max-w-3xl">
            <h1 className="font-display text-3xl font-bold text-slate-900 dark:text-white">Trusted sources</h1>
            <p className="mt-2 text-slate-600 dark:text-slate-400">
              Pin Craigslist regions and local property-manager sites. Runs use these automatically — see{' '}
              <Link href="/preferences" className="text-blue-600 underline dark:text-blue-400">
                Preferences
              </Link>{' '}
              for which platforms are enabled.
            </p>

            {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
            {loading ? <p className="mt-6 text-sm text-slate-500">Loading…</p> : null}

            <section className="mt-10">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Craigslist regions</h2>
                <Button
                  type="button"
                  color="blue"
                  onClick={() => {
                    setClMountKey((k) => k + 1)
                    setClOpen(true)
                  }}
                >
                  Add region
                </Button>
              </div>
              {clRows.length === 0 && !loading ? (
                <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                  No regions yet. Add one so Lancaster, CA maps to Inland Empire (not lancaster.craigslist.org in
                  Pennsylvania).
                </p>
              ) : (
                <ul className="mt-4 divide-y divide-slate-200 dark:divide-slate-700">
                  {clRows.map((r) => (
                    <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                      <div>
                        <div className="font-medium text-slate-900 dark:text-white">{r.label}</div>
                        <a
                          href={r.url}
                          className="text-blue-600 hover:underline dark:text-blue-400"
                          target="_blank"
                          rel="noreferrer"
                        >
                          {r.url}
                        </a>
                        {r.city ? (
                          <div className="text-xs text-slate-500 dark:text-slate-400">City: {r.city}</div>
                        ) : null}
                      </div>
                      <div className="flex gap-2">
                        <span className="text-xs text-slate-500">{testStatus[r.id] ?? ''}</span>
                        <Button type="button" onClick={() => void onTest(r.id)}>
                          Test
                        </Button>
                        <Button type="button" onClick={() => void onRemove(r.id)}>
                          Remove
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="mt-12">
              <div className="flex items-center justify-between gap-4">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Property managers</h2>
                <Button
                  type="button"
                  color="blue"
                  onClick={() => {
                    setPmMountKey((k) => k + 1)
                    setPmOpen(true)
                  }}
                >
                  Add listings URL
                </Button>
              </div>
              {pmRows.length === 0 && !loading ? (
                <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                  Paste a public listings page. We validate it is reachable, then include it in the next scrape run for
                  that city.
                </p>
              ) : (
                <ul className="mt-4 divide-y divide-slate-200 dark:divide-slate-700">
                  {pmRows.map((r) => (
                    <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                      <div>
                        <div className="font-medium text-slate-900 dark:text-white">{r.label}</div>
                        <a
                          href={r.url}
                          className="text-blue-600 hover:underline dark:text-blue-400"
                          target="_blank"
                          rel="noreferrer"
                        >
                          {r.url}
                        </a>
                        {r.city ? (
                          <div className="text-xs text-slate-500 dark:text-slate-400">City: {r.city}</div>
                        ) : null}
                      </div>
                      <div className="flex gap-2">
                        <span className="text-xs text-slate-500">{testStatus[r.id] ?? ''}</span>
                        <Button type="button" onClick={() => void onTest(r.id)}>
                          Test
                        </Button>
                        <Button type="button" onClick={() => void onRemove(r.id)}>
                          Remove
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </Container>
      </main>
      <Footer />

      <AddCraigslistRegionModal
        key={`cl-${clMountKey}`}
        open={clOpen}
        onClose={() => setClOpen(false)}
        onSaved={() => void load()}
        initialCity={prefillCity}
        initialState={prefillState}
      />
      <AddPropertyManagerModal
        key={`pm-${pmMountKey}`}
        open={pmOpen}
        onClose={() => setPmOpen(false)}
        onSaved={() => void load()}
      />
    </>
  )
}
