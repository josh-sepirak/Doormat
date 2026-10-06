/**
 * Return the input only when it is an absolute http(s) URL, otherwise null.
 * Listing data comes from scraped pages, so a value is never trusted as a link
 * or image source until it passes this check (blocks javascript: and data: URLs).
 */
export function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : null
  } catch {
    return null
  }
}
