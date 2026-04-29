import { Page, Locator } from '@playwright/test'

export class DashboardPage {
  readonly page: Page
  readonly runDiscoveryBtn: Locator
  readonly discoveryLog: Locator
  readonly propertyManagersSection: Locator
  readonly listingsSection: Locator
  readonly runHistorySection: Locator
  readonly scrapeListingsBtn: Locator

  constructor(page: Page) {
    this.page = page
    this.runDiscoveryBtn = page.getByRole('button', { name: /Run discovery/i })
    this.discoveryLog = page.getByText('Discovery log')
    this.propertyManagersSection = page.getByText('Property managers')
    this.listingsSection = page.getByText('Listings').first()
    this.runHistorySection = page.getByText('Run history')
    this.scrapeListingsBtn = page.getByRole('button', { name: /Scrape listings/i })
  }

  async goto() {
    await this.page.goto('/')
  }

  statusCard(label: string) {
    return this.page.locator('div').filter({ hasText: label }).first()
  }
}
