import { test, expect } from '@playwright/test'
import { MOCK_LISTINGS, MOCK_RUN_RESULTS } from './fixtures/api-mocks'

test.describe('End-to-end Onboarding Wizard Flow', () => {
  test('walks through 4-step wizard, saves preference, triggers run, navigates to run report and listings', async ({
    page,
  }) => {
    let capturedPreferencePayload: Record<string, unknown> | null = null
    let capturedSearchRunPayload: Record<string, unknown> | null = null
    let capturedOpenRouterTestKey: string | null = null

    // Base endpoints
    await page.route('**/health', (route) => route.fulfill({ json: { status: 'ok' } }))
    await page.route('**/api/config', (route) =>
      route.fulfill({
        json: {
          has_openrouter_key: false,
          openrouter_key_last4: null,
          has_apify_token: false,
          apify_token_last4: null,
        },
      }),
    )

    // Initial state: no preferences configured
    await page.route('**/api/preferences', (route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({ json: [] })
      } else if (route.request().method() === 'POST') {
        capturedPreferencePayload = route.request().postDataJSON()
        route.fulfill({
          status: 201,
          json: {
            id: 'pref-wizard-123',
            city: 'Austin, TX',
            description: capturedPreferencePayload?.description,
            has_openrouter_api_key: true,
            openrouter_key_last4: '7890',
            has_apify_api_token: false,
            apify_token_last4: null,
            api_provider: 'openrouter',
          },
        })
      }
    })

    // OpenRouter models endpoint for connection test
    await page.route('**/api/openrouter/models', (route) => {
      const data = route.request().postDataJSON()
      capturedOpenRouterTestKey = data?.key
      route.fulfill({
        status: 200,
        json: [
          {
            id: 'openai/gpt-4o-mini',
            name: 'GPT-4o Mini',
            provider: 'Openai',
            context_length: 128000,
            prompt_price: 0.15,
            completion_price: 0.6,
          },
        ],
      })
    })

    // Search run creation
    await page.route('**/api/search-runs', (route) => {
      if (route.request().method() === 'POST') {
        capturedSearchRunPayload = route.request().postDataJSON()
        route.fulfill({
          status: 201,
          json: {
            id: 'run-wizard-999',
            city: 'Austin, TX',
            status: 'running',
            current_stage: 'discovery',
            sources_checked: 2,
            managers_validated: 1,
            listings_seen: 5,
            extraction_attempts: 4,
            cost_usd_so_far: 0.042,
            great_matches: 2,
            worth_a_look: 1,
            near_misses: 0,
            filtered_out: 2,
            created_at: new Date().toISOString(),
          },
        })
      }
    })

    // Search run detail polling
    await page.route('**/api/search-runs/run-wizard-999', (route) => {
      route.fulfill({
        json: {
          id: 'run-wizard-999',
          city: 'Austin, TX',
          status: 'running',
          current_stage: 'discovery',
          sources_checked: 2,
          managers_validated: 1,
          listings_seen: 5,
          extraction_attempts: 4,
          cost_usd_so_far: 0.042,
          great_matches: 2,
          worth_a_look: 1,
          near_misses: 0,
          filtered_out: 2,
          created_at: new Date().toISOString(),
        },
      })
    })

    // Search run events
    await page.route(/\/api\/search-runs\/run-wizard-999\/events/, (route) => {
      route.fulfill({
        json: [
          {
            id: 'evt-1',
            sequence: 1,
            event_type: 'stage_started',
            stage: 'discovery',
            message: 'Discovering property managers in Austin, TX',
            visibility: 'user',
            timestamp: new Date().toISOString(),
          },
          {
            id: 'evt-2',
            sequence: 2,
            event_type: 'listing_found',
            stage: 'scraping',
            message: 'Found listing at 123 Congress Ave',
            visibility: 'user',
            timestamp: new Date().toISOString(),
          },
        ],
      })
    })

    // Search run results and listings
    await page.route(/\/api\/search-runs\/run-wizard-999\/results/, (route) => {
      route.fulfill({ json: MOCK_RUN_RESULTS })
    })

    await page.route(/\/api\/listings(?:\?.*)?$/, (route) => {
      route.fulfill({ json: { listings: MOCK_LISTINGS, total: 2 } })
    })

    // ─── 1. Initial Page Load (Step 1) ───
    await page.goto('/')

    await expect(page.getByText('Your Dream Rental')).toBeVisible()
    await expect(page.getByText('Tell Doormat what you want in your next home.')).toBeVisible()

    // Step 1: Input city, bedrooms, bathrooms, pets, lifestyle note
    const cityInput = page.getByPlaceholder('e.g. Austin, TX or San Francisco, CA')
    await cityInput.fill('Austin, TX')

    await page.getByRole('button', { name: '2 BR' }).click()
    await page.getByRole('button', { name: '2 BA' }).click()
    await page.getByRole('button', { name: /Dog Friendly/i }).click()

    await page.getByRole('button', { name: /\+ Quiet street near transit/i }).click()

    // Continue to Step 2
    await page.getByRole('button', { name: /Continue to AI Setup/i }).click()

    // ─── 2. Step 2: AI Brain Connection ───
    await expect(page.getByText('Connect AI Intelligence')).toBeVisible()
    await expect(page.getByText(/How Doormat Evaluates Listings/i)).toBeVisible()

    const keyInput = page.getByPlaceholder('sk-or-v1-...')
    await keyInput.fill('sk-or-v1-testkey1234567890')

    await page.getByRole('button', { name: 'Test Key' }).click()
    await expect(page.getByText('Key verified! Connected to OpenRouter.')).toBeVisible()
    expect(capturedOpenRouterTestKey).toBe('sk-or-v1-testkey1234567890')

    // Continue to Step 3
    await page.getByRole('button', { name: /Continue to Sources/i }).click()

    // ─── 3. Step 3: Rental Sources ───
    await expect(page.getByText('Choose Your Rental Sources')).toBeVisible()
    await expect(page.getByText('Craigslist Regional Search')).toBeVisible()
    await expect(page.getByText('Direct Property Management Sites')).toBeVisible()

    // Continue to Step 4
    await page.getByRole('button', { name: /Review & Launch/i }).click()

    // ─── 4. Step 4: Review & Launch ───
    await expect(page.getByText('Ready to Launch Your Search')).toBeVisible()
    await expect(page.getByText('Search Summary')).toBeVisible()
    await expect(page.getByText('2 BR, 2 BA')).toBeVisible()
    await expect(page.getByText(/Dogs allowed/i)).toBeVisible()

    // Launch Search
    const startButton = page.getByRole('button', { name: /Start Searching Now/i })
    await expect(startButton).toBeVisible()
    await startButton.click()

    // ─── 5. Verify API Payloads ───
    await expect.poll(() => capturedPreferencePayload).not.toBeNull()
    expect(capturedPreferencePayload?.city).toBe('Austin, TX')
    expect(capturedPreferencePayload?.openrouter_api_key).toBe('sk-or-v1-testkey1234567890')
    expect(String(capturedPreferencePayload?.description)).toContain('2-bedroom')
    expect(String(capturedPreferencePayload?.description)).toContain('dog-friendly')

    await expect.poll(() => capturedSearchRunPayload).not.toBeNull()
    expect(capturedSearchRunPayload?.city).toBe('Austin, TX')
    expect(capturedSearchRunPayload?.preference_id).toBe('pref-wizard-123')

    // ─── 6. Transition to Live Run Report ───
    await expect(page).toHaveURL(/\/runs\/run-wizard-999/)
    await expect(page.getByRole('heading', { level: 1, name: 'Austin, TX' })).toBeVisible()

    // Check humanized live progress banner
    await expect(
      page.getByText(/Discovering local property managers in Austin, TX/i),
    ).toBeVisible()

    // Check humanized counters
    const countersRegion = page.getByRole('region', { name: /Run counters/i })
    await expect(countersRegion.getByText('AI Inspected')).toBeVisible()
    await expect(countersRegion.getByText('Listings Found')).toBeVisible()
    await expect(countersRegion.getByText('Property Managers')).toBeVisible()

    // ─── 7. Transition to Listings View ───
    const browseLink = page.getByRole('link', { name: /Browse listings by category/i })
    await expect(browseLink).toBeVisible()
    await browseLink.click()

    await expect(page).toHaveURL(/\/listings\?run=run-wizard-999&category=great_match/)
    await expect(page.getByText(/Showing results for/i)).toBeVisible()
    await expect(page.getByRole('link', { name: 'Open run report' })).toBeVisible()

    // Check Match Badge and Cards
    await expect(page.getByText('123 Congress Ave, Austin, TX 78701')).toBeVisible()
    await expect(page.getByText(/\$2,200\/mo/)).toBeVisible()
    await expect(page.getByText(/2\s*BR/)).toBeVisible()
    await expect(page.getByText(/1\s*BA/).first()).toBeVisible()
    await expect(page.getByText('78% Match')).toBeVisible()
    await expect(page.getByRole('link', { name: /Apply \/ View on Source/i }).first()).toBeVisible()
  })
})
