// ─── Core entities ────────────────────────────────────────────
export interface Product {
  id: string
  name: string
  description: string | null
  price: number
  image_url: string | null
  is_available: boolean
  created_at: string
  updated_at: string
}

export type ProductCreate = Omit<Product, 'id' | 'created_at' | 'updated_at'>
export type ProductUpdate = Partial<ProductCreate>

export interface Promotion {
  id: string
  name: string
  type: 'percentage' | 'fixed' | 'bundle'
  value: string
  description_for_bot: string | null
  promo_code: string | null
  start_date: string
  end_date: string
  product_ids: string[] | null
  is_active: boolean
}

export type PromotionCreate = Omit<Promotion, 'id' | 'product_ids'> & { product_ids?: string[] | null }
export type PromotionUpdate = Partial<PromotionCreate>

export interface Prompt {
  id: string
  type: 'system' | 'greeting' | 'qualification' | 'presentation' | 'objections' | 'closing' | 'upsell'
  content: string
  updated_at: string
}

export interface FAQ {
  id: string
  question: string
  answer: string
  sort_order: number
}

export type FAQCreate = Omit<FAQ, 'id'>
export type FAQUpdate = Partial<FAQCreate>

export interface Conversation {
  id: string
  instagram_user_id: string
  instagram_username: string | null
  source: 'dm' | 'comment'
  status: 'active' | 'ended' | 'converted'
  funnel_stage: 'greeting' | 'qualification' | 'presentation' | 'objection' | 'closing' | 'payment' | 'completed'
  message_count: number
  ticket_id: string | null
  started_at: string
  ended_at: string | null
}

export interface Message {
  id: string
  conversation_id: string
  role: 'client' | 'bot'
  content: string
  media_url: string | null
  created_at: string
}

export interface Ticket {
  id: string
  ticket_number: number
  client_instagram: string
  client_name: string | null
  client_phone: string | null
  client_city: string | null
  client_address: string | null
  product_name: string
  product_quantity: number
  total_amount: number
  payment_method: 'transfer' | 'cash'
  payment_status: 'confirmed' | 'pending' | 'rejected'
  payment_screenshot_url: string | null
  payment_transaction_id: string | null
  payment_amount_verified: number | null
  order_status: 'new' | 'in_progress' | 'completed' | 'cancelled'
  notes: string | null
  telegram_message_id: number | null
  created_at: string
  updated_at: string
}

export interface Setting {
  id: string
  key: string
  value: string
  updated_at: string
}

// ─── Paginated ─────────────────────────────────────────────────
export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

export interface PaginatedMessages {
  items: Message[]
  total: number
}

// ─── Analytics ─────────────────────────────────────────────────
export interface DashboardStats {
  today_conversations: number
  today_orders: number
  conversion_rate: number
  today_revenue: number
}

export interface ChartData {
  labels: string[]
  conversations: number[]
  orders: number[]
}

export interface ProductAnalytics {
  product: string
  count: number
  revenue: number
}

// ─── Auth ──────────────────────────────────────────────────────
export interface AuthUser {
  id: string
  username: string
  email: string
  role: 'admin' | 'operator'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export interface UserCreate {
  username: string
  email: string
  password: string
  role: 'admin' | 'operator'
}

export interface UserUpdate {
  username?: string
  email?: string
  password?: string
  role?: 'admin' | 'operator'
  is_active?: boolean
}

// ─── Convenience aliases ──────────────────────────────────────
export type ConversationStatus = Conversation['status']
export type FunnelStage = Conversation['funnel_stage']
export type OrderStatus = Ticket['order_status']
export type PaymentStatus = Ticket['payment_status']
export type PromptType = Prompt['type']
