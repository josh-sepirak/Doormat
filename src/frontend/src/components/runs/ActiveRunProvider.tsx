'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

import type { SearchRun } from '@/client/search-runs'
import { fetchActiveSearchRun, stopSearchRun } from '@/client/search-runs'

type ActiveRunContextValue = {
  run: SearchRun | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  stop: () => Promise<void>
}

const ActiveRunContext = createContext<ActiveRunContextValue | null>(null)

const POLL_MS = 3000

export function ActiveRunProvider({ children }: { children: React.ReactNode }) {
  const [run, setRun] = useState<SearchRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(async () => {
    try {
      const env = await fetchActiveSearchRun()
      setRun(env.active ? env.run : null)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const stop = useCallback(async () => {
    if (!run) return
    try {
      await stopSearchRun(run.id)
      await refresh()
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      throw e
    }
  }, [run, refresh])

  useEffect(() => {
    const boot = setTimeout(() => {
      void refresh()
    }, 0)
    timerRef.current = setInterval(() => {
      void refresh()
    }, POLL_MS)
    return () => {
      clearTimeout(boot)
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [refresh])

  const value = useMemo(
    () => ({
      run,
      loading,
      error,
      refresh,
      stop,
    }),
    [run, loading, error, refresh, stop],
  )

  return <ActiveRunContext.Provider value={value}>{children}</ActiveRunContext.Provider>
}

export function useActiveRun() {
  const ctx = useContext(ActiveRunContext)
  if (!ctx) {
    throw new Error('useActiveRun must be used within ActiveRunProvider')
  }
  return ctx
}
