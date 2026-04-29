'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import clsx from 'clsx'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { Container } from '@/components/Container'
import { safeHttpUrl } from '@/lib/url'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Listing {
  id: string
  address: string
  price: number
  bedrooms: number | null
  bathrooms: number | null
  sqft: number | null
  pets_policy: string
  url: string | null
  score: number | null
  score_explanation: string | null
  validation_passed: boolean
  extraction_timestamp: string
}
export default function ListingsPage() {
  const [listings, setListings] = useState<Listing[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/api/listings`)
      .then((r) => r.json())
      .then((data) => setListings(data.listings || data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <Header />
      <main className="flex-1">
        <Container className="py-16">
          <div className="mx-auto max-w-5xl">
            <h1 className="font-display text-3xl font-medium tracking-tight text-slate-900 dark:text-slate-100">
              Listings
            </h1>
            <p className="mt-2 text-lg text-slate-600 dark:text-slate-400">
              Extracted and scored rental listings.
            </p>

            {loading ? (
              <div className="mt-16 text-center text-slate-500">
                Loading listings…
              </div>
            ) : listings.length === 0 ? (
              <div className="mt-16 rounded-2xl border-2 border-dashed border-slate-200 p-12 text-center">
                <p className="text-lg font-medium text-slate-900">
                  No listings yet
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  Run a discovery from the{' '}
                  <Link href="/" className="text-blue-600 hover:underline">
                    Dashboard
                  </Link>{' '}
                  to start finding listings.
                </p>
              </div>
            ) : (
              <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {listings.map((listing) => (
                  <ListingCard key={listing.id} listing={listing} />
                ))}
              </div>
            )}
          </div>
        </Container>
      </main>
      <Footer />
    </>
  )
}
function ListingCard({ listing }: { listing: Listing }) {
  const sourceUrl = safeHttpUrl(listing.url)
  return (
    <div className="group relative rounded-2xl border border-slate-200 p-6 transition-shadow hover:shadow-lg">
      {/* Score badge */}
      {listing.score !== null && (
        <div
          className={clsx(
            'absolute top-4 right-4 rounded-full px-2.5 py-0.5 text-xs font-semibold',
            listing.score >= 80
              ? 'bg-green-100 text-green-800'
              : listing.score >= 50
                ? 'bg-yellow-100 text-yellow-800'
                : 'bg-red-100 text-red-800',
          )}
        >
          {listing.score}/100
        </div>
      )}

      <h3 className="font-display text-base font-medium text-slate-900 pr-16">
        {listing.address}
      </h3>

      <div className="mt-4 flex flex-wrap gap-3 text-sm text-slate-600">
        <span className="font-semibold text-slate-900">
          ${listing.price.toLocaleString()}/mo
        </span>
        {listing.bedrooms !== null && <span>{listing.bedrooms}BR</span>}
        {listing.bathrooms !== null && <span>{listing.bathrooms}BA</span>}
        {listing.sqft !== null && (
          <span>{listing.sqft.toLocaleString()} sqft</span>
        )}
      </div>

      {listing.pets_policy && listing.pets_policy !== 'unknown' && (
        <div className="mt-2 text-xs text-slate-500">
          Pets: {listing.pets_policy}
        </div>
      )}

      {listing.score_explanation && (
        <p className="mt-3 text-sm text-slate-500 line-clamp-2">
          {listing.score_explanation}
        </p>
      )}

      <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
        <span>{new Date(listing.extraction_timestamp).toLocaleDateString()}</span>
        {sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            View source
          </a>
        ) : (
          <span className="text-slate-400">Source unavailable</span>
        )}
      </div>
    </div>
  )
}
