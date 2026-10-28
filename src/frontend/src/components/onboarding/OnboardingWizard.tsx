'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import clsx from 'clsx'
import { Button } from '@/components/Button'
import { apiFetch } from '@/lib/api'
import { createSearchRun, type SearchRun } from '@/client/search-runs'

export interface OnboardingWizardProps {
  onCompleted?: (run: SearchRun) => void
  onCancel?: () => void
}

const CITY_SUGGESTIONS = [
  'San Francisco, CA',
  'Austin, TX',
  'Seattle, WA',
  'New York, NY',
  'Denver, CO',
  'Chicago, IL',
]

const PROMPT_IDEAS = [
  'Quiet street near transit with in-unit laundry and lots of natural light',
  'Pet-friendly 2BR near parks with off-street parking under budget',
  'Top floor with balcony or patio, dishwasher, and walkable to coffee shops',
]
const PHYSICAL_WISHLIST_CHIPS = [
  'Room for 12ft trampoline',
  'Fenced yard for dogs',
  'In-unit laundry in photos',
  'Ground floor / private entry',
]
type PetPolicyType = 'any' | 'dogs' | 'cats' | 'none'


export function OnboardingWizard({ onCompleted, onCancel }: OnboardingWizardProps) {
  const router = useRouter()
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1)

  // Step 1: Dream Home
  const [city, setCity] = useState('')
  const [maxRent, setMaxRent] = useState(2800)
  const [bedrooms, setBedrooms] = useState<string>('1')
  const [bathrooms, setBathrooms] = useState<string>('1')
  const [petPolicy, setPetPolicy] = useState<PetPolicyType>('any')
  const [lifestyleNotes, setLifestyleNotes] = useState('')

  // Step 2: AI Brain
  const [openrouterKey, setOpenrouterKey] = useState('')
  const [testingKey, setTestingKey] = useState(false)
  const [keyStatus, setKeyStatus] = useState<'idle' | 'valid' | 'invalid'>('idle')
  const [keyError, setKeyError] = useState<string | null>(null)

  // Step 3: Sources
  const [sourceCraigslist, setSourceCraigslist] = useState(true)
  const [sourcePms, setSourcePms] = useState(true)
  const [sourceApify, setSourceApify] = useState(false)
  const [apifyToken, setApifyToken] = useState('')

  // Step 4: Submission
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const handleTestKey = async () => {
    if (!openrouterKey.trim()) return
    setTestingKey(true)
    setKeyStatus('idle')
    setKeyError(null)
    try {
      const resp = await apiFetch('/api/openrouter/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: openrouterKey.trim(), curated: false }),
      })
      if (resp.ok) {
        setKeyStatus('valid')
      } else {
        const data = await resp.json().catch(() => ({}))
        setKeyStatus('invalid')
        setKeyError(data.detail || 'Invalid API key or unauthorized')
      }
    } catch (e) {
      setKeyStatus('invalid')
      setKeyError(e instanceof Error ? e.message : 'Connection failed')
    } finally {
      setTestingKey(false)
    }
  }

  const handleStartSearch = async () => {
    setSubmitting(true)
    setSubmitError(null)

    // Build synthesized description for scoring
    const bedDesc = bedrooms === '0' ? 'Studio' : `${bedrooms}-bedroom`
    const bathDesc = `${bathrooms}-bathroom`
    const petDesc =
      petPolicy === 'dogs'
        ? 'dog-friendly'
        : petPolicy === 'cats'
          ? 'cat-friendly'
          : petPolicy === 'none'
            ? 'no pets'
            : 'any pet policy'
    const fullDesc = `${bedDesc}, ${bathDesc} rental in ${city} under $${maxRent}/mo. Pet policy: ${petDesc}. ${lifestyleNotes}`.trim()

    const sources: string[] = []
    if (sourceCraigslist) sources.push('craigslist')
    if (sourcePms) sources.push('pm_direct')
    if (sourceApify && apifyToken) sources.push('apify')

    try {
      // 1. Save or update preference
      const prefResp = await apiFetch('/api/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          city: city.trim(),
          description: fullDesc,
          openrouter_api_key: openrouterKey.trim() || undefined,
          apify_api_token: apifyToken.trim() || undefined,
          sources_enabled: sources.length > 0 ? sources : ['craigslist'],
        }),
      })

      if (!prefResp.ok) {
        const err = await prefResp.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to save search preference')
      }
      const savedPref = await prefResp.json()

      // 2. Launch initial search run
      const run = await createSearchRun({
        city: city.trim(),
        preference_id: savedPref.id,
      })

      if (onCompleted) {
        onCompleted(run)
      } else {
        router.push(`/runs/${encodeURIComponent(run.id)}`)
      }
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to launch search')
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900 sm:p-10">
      {/* Step Header */}
      <div className="mb-8 border-b border-slate-100 pb-6 dark:border-slate-800">
        <div className="flex items-center justify-between">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
              Step {step} of 4
            </span>
            <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
              {step === 1 && 'Your Dream Rental'}
              {step === 2 && 'Connect AI Intelligence'}
              {step === 3 && 'Choose Your Rental Sources'}
              {step === 4 && 'Ready to Launch Your Search'}
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {step === 1 && 'Tell Doormat what you want in your next home.'}
              {step === 2 && 'Doormat reads listings with AI to inspect pet policies and floorplans.'}
              {step === 3 && 'Pick where Doormat should look for verified listings.'}
              {step === 4 && 'Double-check your criteria and launch autonomous discovery.'}
            </p>
          </div>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="text-sm font-medium text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              Exit
            </button>
          )}
        </div>

        {/* Step dots */}
        <div className="mt-6 flex items-center gap-2">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className={clsx(
                'h-2 flex-1 rounded-full transition-all duration-300',
                i <= step
                  ? 'bg-blue-600 dark:bg-blue-500'
                  : 'bg-slate-100 dark:bg-slate-800',
              )}
            />
          ))}
        </div>
      </div>

      {/* Step 1: Dream Home */}
      {step === 1 && (
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Which city are you moving to?
            </label>
            <input
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. Austin, TX or San Francisco, CA"
              className="mt-2 block w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            />
            {/* Quick city pills */}
            <div className="mt-2.5 flex flex-wrap gap-2">
              <span className="text-xs text-slate-400">Popular:</span>
              {CITY_SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setCity(s)}
                  className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Maximum Monthly Budget
              </label>
              <span className="text-lg font-bold text-blue-600 dark:text-blue-400">
                ${maxRent.toLocaleString()}/mo
              </span>
            </div>
            <input
              type="range"
              min={800}
              max={6000}
              step={50}
              value={maxRent}
              onChange={(e) => setMaxRent(Number(e.target.value))}
              className="mt-3 h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-blue-600 dark:bg-slate-700"
            />
            <div className="mt-2 flex justify-between text-xs text-slate-400">
              <span>$800</span>
              <span>$2,500</span>
              <span>$4,000</span>
              <span>$6,000+</span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Bedrooms
              </label>
              <div className="mt-2 flex gap-2">
                {[
                  { id: '0', label: 'Studio' },
                  { id: '1', label: '1 BR' },
                  { id: '2', label: '2 BR' },
                  { id: '3', label: '3+ BR' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setBedrooms(item.id)}
                    className={clsx(
                      'flex-1 rounded-xl py-2.5 text-xs font-semibold transition-all',
                      bedrooms === item.id
                        ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20'
                        : 'border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300',
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Bathrooms
              </label>
              <div className="mt-2 flex gap-2">
                {['1', '1.5', '2', '2+'].map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setBathrooms(item)}
                    className={clsx(
                      'flex-1 rounded-xl py-2.5 text-xs font-semibold transition-all',
                      bathrooms === item
                        ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20'
                        : 'border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300',
                    )}
                  >
                    {item} BA
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Pet Policy Requirements
            </label>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                { id: 'any', label: 'Any Policy', icon: '🏠' },
                { id: 'dogs', label: 'Dog Friendly', icon: '🐕' },
                { id: 'cats', label: 'Cats Only', icon: '🐈' },
                { id: 'none', label: 'No Pets', icon: '🚫' },
              ].map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setPetPolicy(p.id as PetPolicyType)}
                  className={clsx(
                    'flex flex-col items-center rounded-xl p-3 text-center transition-all',
                    petPolicy === p.id
                      ? 'border-2 border-blue-600 bg-blue-50/60 font-semibold text-blue-900 dark:border-blue-500 dark:bg-blue-950/40 dark:text-blue-100'
                      : 'border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300',
                  )}
                >
                  <span className="text-xl">{p.icon}</span>
                  <span className="mt-1 text-xs">{p.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Wishlist & Lifestyle Notes
            </label>
            <textarea
              rows={3}
              value={lifestyleNotes}
              onChange={(e) => setLifestyleNotes(e.target.value)}
              placeholder="e.g. Quiet neighborhood, in-unit laundry, dishwasher, walkable to parks and groceries..."
              className="mt-2 block w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            />
            <div className="mt-3 space-y-2">
              <div>
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  Physical & Visual Wishlist:
                </span>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {PHYSICAL_WISHLIST_CHIPS.map((chip, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setLifestyleNotes((prev) => (prev ? `${prev}, ${chip}` : chip))}
                      className="rounded-lg border border-emerald-200 bg-emerald-50/80 px-2.5 py-1 text-left text-xs font-medium text-emerald-800 transition-colors hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 dark:hover:bg-emerald-900/60"
                    >
                      + {chip}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <span className="text-xs text-slate-400">General ideas:</span>
                <div className="mt-1 flex flex-col gap-1.5 sm:flex-row">
                  {PROMPT_IDEAS.map((idea, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setLifestyleNotes((prev) => (prev ? `${prev}, ${idea}` : idea))}
                      className="truncate rounded-md bg-slate-100 px-2 py-1 text-left text-xs text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                    >
                      + {idea}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="pt-4">
            <Button
              type="button"
              className="w-full justify-center py-3 text-base"
              onClick={() => {
                if (!city.trim()) {
                  alert('Please enter a city to begin your search.')
                  return
                }
                setStep(2)
              }}
            >
              Continue to AI Setup →
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: AI Brain Connection */}
      {step === 2 && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-5 dark:border-blue-900/40 dark:bg-blue-950/20">
            <div className="flex items-start gap-3">
              <span className="text-2xl">🧠</span>
              <div>
                <h4 className="font-semibold text-blue-950 dark:text-blue-100">
                  How Doormat Evaluates Listings
                </h4>
                <p className="mt-1 text-xs leading-relaxed text-blue-800/80 dark:text-blue-300">
                  Doormat uses OpenRouter to evaluate rental listings directly with fast, low-cost AI models.
                  A complete scan across hundreds of local properties typically costs only <strong>$0.05 to $0.25</strong>.
                </p>
              </div>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                OpenRouter API Key
              </label>
              <a
                href="https://openrouter.ai/keys"
                target="_blank"
                rel="noreferrer"
                className="text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
              >
                Get OpenRouter Key (60 seconds) ↗
              </a>
            </div>
            <div className="mt-2 flex gap-2">
              <input
                type="password"
                value={openrouterKey}
                onChange={(e) => {
                  setOpenrouterKey(e.target.value)
                  setKeyStatus('idle')
                }}
                placeholder="sk-or-v1-..."
                className="block flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono text-sm text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
              <Button
                type="button"
                variant="outline"
                onClick={handleTestKey}
                disabled={testingKey || !openrouterKey.trim()}
                className="shrink-0"
              >
                {testingKey ? 'Testing…' : 'Test Key'}
              </Button>
            </div>

            {keyStatus === 'valid' && (
              <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                <span>✓</span> Key verified! Connected to OpenRouter.
              </p>
            )}
            {keyStatus === 'invalid' && (
              <p className="mt-2 text-xs font-medium text-red-600 dark:text-red-400">
                ✗ {keyError || 'Key verification failed. Check your token at openrouter.ai.'}
              </p>
            )}
            <p className="mt-2 text-xs text-slate-400">
              Keys are encrypted at rest with AES-256 before being stored in your local database.
            </p>
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setStep(1)}
              className="flex-1 justify-center py-3"
            >
              ← Back
            </Button>
            <Button
              type="button"
              onClick={() => setStep(3)}
              className="flex-1 justify-center py-3"
            >
              Continue to Sources →
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Rental Sources */}
      {step === 3 && (
        <div className="space-y-6">
          <div className="space-y-3">
            {/* Craigslist */}
            <label className="flex cursor-pointer items-start gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 transition-all hover:bg-slate-100/70 dark:border-slate-700 dark:bg-slate-800/60">
              <input
                type="checkbox"
                checked={sourceCraigslist}
                onChange={(e) => setSourceCraigslist(e.target.checked)}
                className="mt-1 h-5 w-5 rounded-md text-blue-600 focus:ring-blue-500"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900 dark:text-slate-100">
                    Craigslist Regional Search
                  </span>
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                    Free / Built-in
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Scans recent owner and property manager postings across your local Craigslist region.
                </p>
              </div>
            </label>

            {/* Direct Property Managers */}
            <label className="flex cursor-pointer items-start gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 transition-all hover:bg-slate-100/70 dark:border-slate-700 dark:bg-slate-800/60">
              <input
                type="checkbox"
                checked={sourcePms}
                onChange={(e) => setSourcePms(e.target.checked)}
                className="mt-1 h-5 w-5 rounded-md text-blue-600 focus:ring-blue-500"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900 dark:text-slate-100">
                    Direct Property Management Sites
                  </span>
                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                    High Quality
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Discovers and extracts listings directly from verified local management companies, bypassing intermediary fees.
                </p>
              </div>
            </label>

            {/* Apify Zillow/Facebook */}
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
              <label className="flex cursor-pointer items-start gap-4">
                <input
                  type="checkbox"
                  checked={sourceApify}
                  onChange={(e) => setSourceApify(e.target.checked)}
                  className="mt-1 h-5 w-5 rounded-md text-blue-600 focus:ring-blue-500"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">
                      Zillow & Facebook Rentals (via Apify)
                    </span>
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                      Optional
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Requires a free Apify account token. You can skip this now and enable it anytime in settings.
                  </p>
                </div>
              </label>

              {sourceApify && (
                <div className="mt-4 border-t border-slate-200 pt-3 dark:border-slate-700">
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                    Apify API Token
                  </label>
                  <input
                    type="password"
                    value={apifyToken}
                    onChange={(e) => setApifyToken(e.target.value)}
                    placeholder="apify_api_..."
                    className="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  />
                  <p className="mt-1 text-[11px] text-slate-400">
                    Get a free token with $5 monthly credit at <a href="https://apify.com" target="_blank" rel="noreferrer" className="underline">apify.com</a>.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setStep(2)}
              className="flex-1 justify-center py-3"
            >
              ← Back
            </Button>
            <Button
              type="button"
              onClick={() => setStep(4)}
              className="flex-1 justify-center py-3"
            >
              Review & Launch →
            </Button>
          </div>
        </div>
      )}

      {/* Step 4: Review & Launch */}
      {step === 4 && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-6 dark:border-slate-800 dark:bg-slate-900/60">
            <h3 className="font-display text-lg font-semibold text-slate-900 dark:text-slate-100">
              Search Summary
            </h3>
            <dl className="mt-4 divide-y divide-slate-200/60 text-sm dark:divide-slate-800">
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500 dark:text-slate-400">Target City</dt>
                <dd className="font-semibold text-slate-900 dark:text-slate-100">{city}</dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500 dark:text-slate-400">Monthly Budget</dt>
                <dd className="font-semibold text-emerald-600 dark:text-emerald-400">
                  Up to ${maxRent.toLocaleString()}/mo
                </dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500 dark:text-slate-400">Layout</dt>
                <dd className="font-semibold text-slate-900 dark:text-slate-100">
                  {bedrooms === '0' ? 'Studio' : `${bedrooms} BR`}, {bathrooms} BA
                </dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500 dark:text-slate-400">Pet Policy</dt>
                <dd className="font-semibold text-slate-900 dark:text-slate-100 capitalize">
                  {petPolicy === 'dogs' ? '🐕 Dogs allowed' : petPolicy === 'cats' ? '🐈 Cats only' : petPolicy}
                </dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500 dark:text-slate-400">Enabled Sources</dt>
                <dd className="font-semibold text-slate-900 dark:text-slate-100">
                  {[
                    sourceCraigslist && 'Craigslist',
                    sourcePms && 'Direct Management',
                    sourceApify && 'Zillow/FB',
                  ]
                    .filter(Boolean)
                    .join(', ')}
                </dd>
              </div>
              {lifestyleNotes && (
                <div className="py-2.5">
                  <dt className="text-slate-500 dark:text-slate-400">Wishlist & Notes</dt>
                  <dd className="mt-1 text-xs italic text-slate-700 dark:text-slate-300">
                    &ldquo;{lifestyleNotes}&rdquo;
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {submitError && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
              {submitError}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setStep(3)}
              disabled={submitting}
              className="flex-1 justify-center py-3.5"
            >
              ← Back
            </Button>
            <Button
              type="button"
              onClick={handleStartSearch}
              disabled={submitting}
              className="flex-2 justify-center py-3.5 text-base font-semibold shadow-lg shadow-blue-500/25"
            >
              {submitting ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Starting Search…
                </span>
              ) : (
                '🚀 Start Searching Now'
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
