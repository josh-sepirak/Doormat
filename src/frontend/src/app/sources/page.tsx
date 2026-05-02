import { Suspense } from 'react'
import { SourcesPageClient } from './SourcesPageClient'

export default function SourcesPage() {
  return (
    <Suspense fallback={<p className="p-8 text-slate-500">Loading…</p>}>
      <SourcesPageClient />
    </Suspense>
  )
}
