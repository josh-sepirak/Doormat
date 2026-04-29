'use client'

import { ActiveRunProvider } from '@/components/runs/ActiveRunProvider'
import { ActiveRunStrip } from '@/components/runs/ActiveRunStrip'

export function AppChrome({ children }: { children: React.ReactNode }) {
  return (
    <ActiveRunProvider>
      <ActiveRunStrip />
      {children}
    </ActiveRunProvider>
  )
}
