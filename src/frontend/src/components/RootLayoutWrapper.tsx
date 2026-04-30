'use client'

import { ReactNode } from 'react'
import { ActiveRunProvider } from '@/components/runs/ActiveRunProvider'
import { ActiveRunStrip } from '@/components/runs/ActiveRunStrip'

export function RootLayoutWrapper({ children }: { children: ReactNode }) {
  return (
    <ActiveRunProvider>
      <ActiveRunStrip />
      {children}
    </ActiveRunProvider>
  )
}
