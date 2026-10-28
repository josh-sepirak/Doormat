import { test, expect } from '@playwright/test'
import { mockBackendApis, MOCK_LISTINGS } from './fixtures/api-mocks'

test.describe('Multimodal visual criteria and physical filter badges', () => {
  test('renders plain-English verified badges with photo citations on listing card', async ({ page }) => {
    await mockBackendApis(page)

    const visualFilterReasons = JSON.stringify([
      {
        filter_code: 'visual_trampoline',
        label: 'Fits 12ft Trampoline',
        verdict: 'confirmed',
        evidence: 'Photo 2 shows a flat grassy backyard (~35ft wide) with no overhead tree canopy.',
        photo_index: 2,
        is_visual: true,
      },
      {
        filter_code: 'visual_dog_yard',
        label: 'Fenced Yard for Dogs',
        verdict: 'confirmed',
        evidence: 'Photo 3 shows secure 6ft perimeter fencing enclosing the lawn.',
        photo_index: 3,
        is_visual: true,
      },
    ])

    const mockRunResultsWithVisuals = [
      {
        id: 'rr-visual-1',
        run_id: 'run-1',
        listing_id: 'lst-1',
        revision: 1,
        category: 'great_match',
        score: 0.92,
        explanation: 'Great 2BR with large yard fitting your trampoline and dog.',
        filter_reasons_json: visualFilterReasons,
      },
    ]

    const mockListingsWithPhotos = [
      {
        ...MOCK_LISTINGS[0],
        photos: [
          'https://images.example.com/front-photo1.jpg',
          'https://images.example.com/backyard-photo2.jpg',
          'https://images.example.com/fenced-yard-photo3.jpg',
        ],
        filter_reasons_json: visualFilterReasons,
      },
    ]

    await page.route(/\/api\/search-runs\/run-1\/results/, (route) =>
      route.fulfill({ json: mockRunResultsWithVisuals }),
    )
    await page.route(/\/api\/listings(?:\?.*)?$/, (route) =>
      route.fulfill({ json: { listings: mockListingsWithPhotos, total: 1 } }),
    )

    await page.goto('/listings?run_id=run-1')

    // Verify green badge labels and photo citation tags
    await expect(page.getByText('Fits 12ft Trampoline')).toBeVisible()
    await expect(page.getByRole('button', { name: /photo 2/i })).toBeVisible()
    await expect(page.getByText('Fenced Yard for Dogs')).toBeVisible()
    await expect(page.getByRole('button', { name: /photo 3/i })).toBeVisible()

    // Verify evidence text
    await expect(
      page.getByText(/Photo 2 shows a flat grassy backyard/i),
    ).toBeVisible()

    // Clicking Photo 2 button updates the card's active photo to Photo 2
    const imgBefore = page.locator('img[loading="lazy"]').first()
    await expect(imgBefore).toHaveAttribute('src', 'https://images.example.com/front-photo1.jpg')

    await page.getByRole('button', { name: /photo 2/i }).click()

    const imgAfter = page.locator('img[loading="lazy"]').first()
    await expect(imgAfter).toHaveAttribute('src', 'https://images.example.com/backyard-photo2.jpg')
  })

  test('onboarding wizard displays physical wishlist chips and inserts into notes', async ({ page }) => {
    await mockBackendApis(page)
    // Return empty preferences so page displays OnboardingWizard
    await page.route('**/api/preferences', (route) => route.fulfill({ json: [] }))
    await page.goto('/')
    await expect(page.getByText('Physical & Visual Wishlist:')).toBeVisible()

    // Verify all 4 physical chips exist
    await expect(page.getByRole('button', { name: /\+ Room for 12ft trampoline/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /\+ Fenced yard for dogs/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /\+ In-unit laundry in photos/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /\+ Ground floor \/ private entry/i })).toBeVisible()

    // Clicking a chip appends to the textarea
    await page.getByRole('button', { name: /\+ Room for 12ft trampoline/i }).click()

    const textarea = page.locator('textarea')
    await expect(textarea).toHaveValue(/Room for 12ft trampoline/)
  })
})
