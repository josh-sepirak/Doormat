'use client'

import { useState, useEffect } from 'react'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { Container } from '@/components/Container'
import { Button } from '@/components/Button'
import { TextField, SelectField } from '@/components/Fields'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Preference {
  id: string
  description: string
  city: string
  api_provider: string
  openrouter_api_key: string | null
  apify_api_token: string | null
}

export default function PreferencesPage() {
  const [preferences, setPreferences] = useState<Preference[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{
    text: string
    type: 'success' | 'error'
  } | null>(null)

  // Form state
  const [city, setCity] = useState('')
  const [description, setDescription] = useState('')
  const [apiProvider, setApiProvider] = useState('openrouter')
  const [openrouterKey, setOpenrouterKey] = useState('')
  const [apifyToken, setApifyToken] = useState('')

  useEffect(() => {
    fetch(`${API}/api/preferences`)
      .then((r) => r.json())
      .then((data: Preference[]) => {
        setPreferences(data)
        if (data.length > 0) {
          const p = data[0]
          setCity(p.city)
          setDescription(p.description)
          setApiProvider(p.api_provider)
          setOpenrouterKey(p.openrouter_api_key || '')
          setApifyToken(p.apify_api_token || '')
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)

    try {
      const body = {
        city,
        description,
        api_provider: apiProvider,
        openrouter_api_key: openrouterKey || null,
        apify_api_token: apifyToken || null,
      }

      let resp: Response
      if (preferences.length > 0) {
        // Update existing
        resp = await fetch(`${API}/api/preferences/${preferences[0].id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      } else {
        // Create new
        resp = await fetch(`${API}/api/preferences`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      }

      if (resp.ok) {
        const updated = await resp.json()
        setPreferences([updated])
        setMessage({ text: 'Preferences saved!', type: 'success' })
      } else {
        const err = await resp.json().catch(() => ({}))
        setMessage({
          text: `Failed: ${err.detail || resp.statusText}`,
          type: 'error',
        })
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setMessage({ text: `Error: ${msg}`, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <>
        <Header />
        <main className="flex flex-1 items-center justify-center">
          <p className="text-slate-500">Loading…</p>
        </main>
        <Footer />
      </>
    )
  }

  return (
    <>
      <Header />
      <main className="flex-1">
        <Container className="py-16">
          <div className="mx-auto max-w-2xl">
            <h1 className="font-display text-3xl font-medium tracking-tight text-slate-900">
              Preferences
            </h1>
            <p className="mt-2 text-lg text-slate-600">
              Configure your search criteria and API keys.
            </p>

            {message && (
              <div
                className={`mt-6 rounded-lg px-4 py-3 text-sm font-medium ${
                  message.type === 'success'
                    ? 'bg-green-50 text-green-800'
                    : 'bg-red-50 text-red-800'
                }`}
              >
                {message.text}
              </div>
            )}

            <form onSubmit={handleSave} className="mt-10 space-y-10">
              {/* Search Preferences */}
              <fieldset>
                <legend className="font-display text-xl font-medium text-slate-900">
                  Search Preferences
                </legend>
                <p className="mt-1 text-sm text-slate-500">
                  Describe what you're looking for in natural language.
                </p>
                <div className="mt-6 space-y-6">
                  <TextField
                    label="City"
                    name="city"
                    placeholder="e.g. Austin, TX"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    required
                  />
                  <div>
                    <label
                      htmlFor="description"
                      className="mb-3 block text-sm font-medium text-gray-700"
                    >
                      Description
                    </label>
                    <textarea
                      id="description"
                      name="description"
                      rows={4}
                      className="block w-full appearance-none rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:bg-white focus:outline-hidden focus:ring-blue-500 sm:text-sm"
                      placeholder="e.g. 2BR pet-friendly apartment under $2000 near downtown"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </fieldset>

              {/* API Configuration */}
              <fieldset>
                <legend className="font-display text-xl font-medium text-slate-900">
                  API Configuration
                </legend>
                <p className="mt-1 text-sm text-slate-500">
                  Configure your LLM provider and API keys. Keys are stored
                  locally.
                </p>
                <div className="mt-6 space-y-6">
                  <SelectField
                    label="API Provider"
                    name="api_provider"
                    value={apiProvider}
                    onChange={(e) => setApiProvider(e.target.value)}
                  >
                    <option value="openrouter">OpenRouter</option>
                    <option value="openai">OpenAI (Direct)</option>
                  </SelectField>
                  <TextField
                    label="OpenRouter API Key"
                    name="openrouter_api_key"
                    type="password"
                    placeholder="sk-or-v1-..."
                    value={openrouterKey}
                    onChange={(e) => setOpenrouterKey(e.target.value)}
                  />
                  <TextField
                    label="Apify API Token (optional)"
                    name="apify_api_token"
                    type="password"
                    placeholder="apify_api_..."
                    value={apifyToken}
                    onChange={(e) => setApifyToken(e.target.value)}
                  />
                </div>
              </fieldset>

              <div className="flex items-center justify-end gap-x-4">
                <Button type="submit" color="blue" disabled={saving}>
                  {saving ? 'Saving…' : 'Save Preferences'}
                </Button>
              </div>
            </form>
          </div>
        </Container>
      </main>
      <Footer />
    </>
  )
}
