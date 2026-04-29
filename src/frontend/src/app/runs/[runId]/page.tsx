'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'

import { Footer } from '@/components/Footer'
import { Header } from '@/components/Header'
import { Container } from '@/components/Container'
import { RunReport } from '@/components/runs/RunReport'

export default function RunDetailPage() {
  const params = useParams()
  const runId = typeof params.runId === 'string' ? params.runId : ''

  if (!runId) {
    return null
  }

  return (
    <>
      <Header />
      <main className="flex-1">
        <Container className="py-10">
          <div className="mb-6">
            <Link href="/" className="text-sm text-blue-600 hover:underline dark:text-blue-400">
              ← Back to dashboard
            </Link>
          </div>
          <RunReport runId={runId} />
        </Container>
      </main>
      <Footer />
    </>
  )
}
