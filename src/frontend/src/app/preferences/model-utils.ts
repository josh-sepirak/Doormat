export interface Preference {
  id: string
  description: string
  city: string
  api_provider: string
  has_openrouter_api_key: boolean
  openrouter_key_last4: string | null
  has_apify_api_token: boolean
  apify_token_last4: string | null
  fast_model: string | null
  smart_model: string | null
}

export interface ModelInfo {
  id: string
  name: string
  provider: string
  context_length: number
  prompt_price: number
  completion_price: number
}

export function getTier(price: number): 'Free' | 'Budget' | 'Standard' | 'Premium' {
  if (price === 0) return 'Free'
  if (price < 1) return 'Budget'
  if (price < 10) return 'Standard'
  return 'Premium'
}

export function fmtContext(ctx: number): string {
  if (!ctx) return '-'
  if (ctx >= 1_000_000) return `${(ctx / 1_000_000).toFixed(ctx % 1_000_000 === 0 ? 0 : 1)}M`
  if (ctx >= 1_000) return `${Math.round(ctx / 1000)}k`
  return String(ctx)
}

export function fmtPrice(price: number): string {
  if (price === 0) return 'Free'
  if (price < 0.01) return `$${price.toFixed(4)}`
  if (price < 1) return `$${price.toFixed(3)}`
  return `$${price.toFixed(2)}`
}

export const TIERS = ['All', 'Free', 'Budget', 'Standard', 'Premium'] as const
export type TierFilter = (typeof TIERS)[number]

export const CTX_FILTERS = ['Any', '<=32k', '32k-128k', '128k+', '1M+'] as const
export type CtxFilter = (typeof CTX_FILTERS)[number]

export const SORTS = ['Cheapest', 'Largest ctx', 'Name A-Z'] as const
export type SortBy = (typeof SORTS)[number]

export function matchesCtx(ctx: number, filter: CtxFilter): boolean {
  switch (filter) {
    case 'Any':
      return true
    case '<=32k':
      return ctx <= 32_000
    case '32k-128k':
      return ctx > 32_000 && ctx <= 128_000
    case '128k+':
      return ctx > 128_000 && ctx < 1_000_000
    case '1M+':
      return ctx >= 1_000_000
  }
}

export const tierColors: Record<string, string> = {
  Free: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  Budget: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  Standard: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  Premium: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
}

export const pill =
  'min-h-[36px] shrink-0 inline-flex items-center rounded-full px-3 py-1.5 text-xs font-medium transition-colors'
export const pillOn = 'bg-blue-600 text-white dark:bg-blue-500'
export const pillOff =
  'bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50 dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-600 dark:hover:bg-slate-600'

export const roleBtn =
  'min-h-[40px] rounded-md px-3 py-2 text-xs font-medium transition-colors'
export const roleBtnOn = 'bg-blue-600 text-white dark:bg-blue-500'
export const roleBtnOff =
  'bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50 dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-600'
