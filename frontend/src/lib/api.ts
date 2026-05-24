import type {
  Product, ProductCreate, ProductUpdate,
  Promotion, PromotionCreate, PromotionUpdate,
  Prompt,
  FAQ, FAQCreate, FAQUpdate,
  Conversation, Message,
  Ticket,
  Setting,
  Paginated, PaginatedMessages,
  DashboardStats, ChartData, ProductAnalytics,
  AuthUser, TokenResponse, UserCreate, UserUpdate,
} from '../types'

const BASE = ((import.meta as unknown as { env: Record<string,string> }).env.VITE_API_URL ?? '').replace(/\/$/, '')

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = BASE ? `${BASE}/api/v1${path}` : `/api/v1${path}`

  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...(init.headers as Record<string, string>),
    },
  })

  if (res.status === 204) return null as T

  const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
  if (!res.ok) throw new Error(data.detail ?? `Error ${res.status}`)
  return data as T
}

// ─── Auth ───────────────────────────────────────────────────────
export const authApi = {
  login: (username: string, password: string) =>
    req<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  me: () => req<AuthUser>('/auth/me'),
  listUsers: () => req<AuthUser[]>('/auth/users'),
  createUser: (body: UserCreate) =>
    req<AuthUser>('/auth/users', { method: 'POST', body: JSON.stringify(body) }),
  updateUser: (id: string, body: UserUpdate) =>
    req<AuthUser>(`/auth/users/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteUser: (id: string) =>
    req<null>(`/auth/users/${id}`, { method: 'DELETE' }),
}

// ─── Products ──────────────────────────────────────────────────
export const productsApi = {
  list: () => req<Product[]>('/products'),
  create: (body: ProductCreate) =>
    req<Product>('/products', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: ProductUpdate) =>
    req<Product>(`/products/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id: string) =>
    req<null>(`/products/${id}`, { method: 'DELETE' }),
}

// ─── Promotions ────────────────────────────────────────────────
export const promotionsApi = {
  list: () => req<Promotion[]>('/promotions'),
  create: (body: PromotionCreate) =>
    req<Promotion>('/promotions', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: PromotionUpdate) =>
    req<Promotion>(`/promotions/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id: string) =>
    req<null>(`/promotions/${id}`, { method: 'DELETE' }),
}

// ─── Prompts ───────────────────────────────────────────────────
export const promptsApi = {
  list: () => req<Prompt[]>('/prompts'),
  update: (id: string, body: { content: string }) =>
    req<Prompt>(`/prompts/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
}

// ─── FAQ ───────────────────────────────────────────────────────
export const faqApi = {
  list: () => req<FAQ[]>('/faq'),
  create: (body: FAQCreate) =>
    req<FAQ>('/faq', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: FAQUpdate) =>
    req<FAQ>(`/faq/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id: string) =>
    req<null>(`/faq/${id}`, { method: 'DELETE' }),
}

// ─── Conversations ─────────────────────────────────────────────
export const conversationsApi = {
  list: (params: { status?: string; funnel_stage?: string; page?: number; per_page?: number }) => {
    const qs = new URLSearchParams()
    if (params.status) qs.set('status', params.status)
    if (params.funnel_stage) qs.set('funnel_stage', params.funnel_stage)
    if (params.page) qs.set('page', String(params.page))
    if (params.per_page) qs.set('per_page', String(params.per_page))
    return req<Paginated<Conversation>>(`/conversations?${qs}`)
  },
  get: (id: string) => req<Conversation>(`/conversations/${id}`),
  messages: (id: string) =>
    req<PaginatedMessages>(`/conversations/${id}/messages`),
}

// ─── Tickets ───────────────────────────────────────────────────
export const ticketsApi = {
  list: (params: { order_status?: string; page?: number; per_page?: number }) => {
    const qs = new URLSearchParams()
    if (params.order_status) qs.set('order_status', params.order_status)
    if (params.page) qs.set('page', String(params.page))
    if (params.per_page) qs.set('per_page', String(params.per_page))
    return req<Paginated<Ticket>>(`/tickets?${qs}`)
  },
  get: (id: string) => req<Ticket>(`/tickets/${id}`),
}

// ─── Settings ──────────────────────────────────────────────────
export const settingsApi = {
  list: () => req<Setting[]>('/settings'),
  update: (key: string, value: string) =>
    req<Setting>(`/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) }),
  batchUpdate: (settings: Record<string, string>) =>
    req<Setting[]>('/settings', { method: 'PUT', body: JSON.stringify({ settings }) }),
  testTelegram: () =>
    req<{ status: string }>('/settings/test-telegram', { method: 'POST' }),
}

// ─── Analytics ─────────────────────────────────────────────────
export const analyticsApi = {
  dashboard: () => req<DashboardStats>('/analytics/dashboard'),
  chart: (days = 30) => req<ChartData>(`/analytics/chart?days=${days}`),
  products: () => req<ProductAnalytics[]>('/analytics/products'),
}
