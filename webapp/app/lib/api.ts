/**
 * API Client for Backend Communication
 * Connects Next.js WebApp to FastAPI backend
 * Production: Uses relative /api path (no CORS issues)
 */

import { buildWsUrl, setRuntimeWsBaseUrl } from "./wsUrl"
import { buildNgrokBypassHeaders, normalizeBaseUrl } from "./network"

// Use relative path - Next.js rewrites will proxy /api/* to backend
// Works for both localhost and Ngrok domain
let API_BASE = normalizeBaseUrl(process.env.NEXT_PUBLIC_API_BASE || "/api") || "/api"

function setApiBase(newBase?: string | null) {
  const normalized = normalizeBaseUrl(newBase) || "/api"
  if (API_BASE !== normalized) {
    console.log(`[api] Updating API_BASE -> ${normalized}`)
    API_BASE = normalized
  }
}

function getApiBase(): string {
  return API_BASE || "/api"
}

// API request timeout (30 seconds)
const API_TIMEOUT = 30000
// Max retry attempts
const MAX_RETRIES = 3
// Retry delay (ms)
const RETRY_DELAY = 1000

function mergeHeaders(headersInit?: HeadersInit): Headers {
  const baseHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    'Connection': 'keep-alive',
    ...buildNgrokBypassHeaders(),
  }

  const headers = new Headers(baseHeaders)

  if (!headersInit) {
    return headers
  }

  if (headersInit instanceof Headers) {
    headersInit.forEach((value, key) => headers.set(key, value))
    return headers
  }

  if (Array.isArray(headersInit)) {
    headersInit.forEach(([key, value]) => {
      headers.set(key, value)
    })
    return headers
  }

  Object.entries(headersInit).forEach(([key, value]) => {
    if (typeof value !== "undefined") {
      headers.set(key, value as string)
    }
  })

  return headers
}

/**
 * Enhanced fetch with timeout, retry logic and error handling
 */
async function apiFetch(url: string, options: RequestInit = {}, retries = MAX_RETRIES): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT)
  const { headers: optionHeaders, ...restOptions } = options
  const headers = mergeHeaders(optionHeaders)
  
  try {
    console.log(`[apiFetch] Requesting: ${url}`)
    const response = await fetch(url, {
      ...restOptions,
      signal: controller.signal,
      headers,
    })
    
    clearTimeout(timeoutId)
    
    console.log(`[apiFetch] Response status: ${response.status} for ${url}`)
    
    // Retry on 5xx errors or connection errors
    if (!response.ok && response.status >= 500 && retries > 0) {
      console.warn(`[apiFetch] Server error (${response.status}), retrying... (${retries} left)`)
      clearTimeout(timeoutId)
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY))
      return apiFetch(url, options, retries - 1)
    }
    
    return response
  } catch (error) {
    clearTimeout(timeoutId)
    
    const errorMsg = error instanceof Error ? error.message : String(error)
    console.error(`[apiFetch] Error for ${url}: ${errorMsg}`)
    
    // Retry on connection errors (ECONNREFUSED, etc.)
    if (retries > 0 && (error instanceof Error && 
        (error.message.includes('ECONNREFUSED') || 
         error.message.includes('fetch failed') ||
         error.message.includes('NetworkError')))) {
      console.warn(`[apiFetch] Connection error, retrying... (${retries} left)`)
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY))
      return apiFetch(url, options, retries - 1)
    }
    
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('API request timeout')
    }
    throw error
  }
}

// =========================================================
// CONFIG & RUNTIME SETUP
// =========================================================

/**
 * Configuration returned from backend /api/config
 * Contains runtime URLs that avoid hardcoded localhost/ngrok URLs
 */
export interface RuntimeConfig {
  apiBaseUrl: string
  wsBaseUrl: string
  timestamp: string
}

let runtimeConfig: RuntimeConfig | null = null

/**
 * Fetch runtime configuration from backend
 * This is called once on app startup to get actual server URLs
 * Solves Telegram iframe issues where environment variables don't work
 */
export async function fetchRuntimeConfig(): Promise<RuntimeConfig> {
  if (runtimeConfig) {
    console.log("✅ [fetchRuntimeConfig] Using cached runtime config")
    return runtimeConfig
  }

  try {
    const originParam = typeof window !== 'undefined' ? window.location.origin : null
    const runtimeApiBase = getApiBase()
    const configEndpoint = originParam 
      ? `${runtimeApiBase}/config?origin=${encodeURIComponent(originParam)}`
      : `${runtimeApiBase}/config`

    console.log("🔄 [fetchRuntimeConfig] Fetching runtime configuration...")
    console.log(`   📍 Current API_BASE: ${runtimeApiBase}`)
    console.log(`   📍 Window origin: ${originParam || 'N/A'}`)
    console.log(`   📍 Requesting: ${configEndpoint}`)
    
    const res = await apiFetch(configEndpoint)
    
    if (!res.ok) {
      const statusText = res.statusText || `HTTP ${res.status}`
      const errorBody = await res.text()
      console.error(`[fetchRuntimeConfig] Response not OK: ${statusText}`)
      console.error(`[fetchRuntimeConfig] Response body: ${errorBody}`)
      throw new Error(`Failed to fetch config: ${statusText}`)
    }
    
    runtimeConfig = await res.json()
    if (runtimeConfig?.apiBaseUrl) {
      setApiBase(runtimeConfig.apiBaseUrl)
    }
    if (runtimeConfig?.wsBaseUrl) {
      setRuntimeWsBaseUrl(runtimeConfig.wsBaseUrl)
    }
    if (runtimeConfig) {
      console.log("✅ [fetchRuntimeConfig] Config loaded successfully:", {
        apiBaseUrl: runtimeConfig.apiBaseUrl,
        wsBaseUrl: runtimeConfig.wsBaseUrl,
        timestamp: runtimeConfig.timestamp,
      })
      return runtimeConfig
    }
    throw new Error("Invalid config response - empty")
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    console.error("❌ [fetchRuntimeConfig] Failed:", errorMsg)
    console.error("   🔄 Falling back to default values")
    // Fallback to default API_BASE
    const fallbackApiBase = getApiBase()
    const fallbackWsBase = fallbackApiBase.replace(/^http/, "ws")
    runtimeConfig = {
      apiBaseUrl: fallbackApiBase,
      wsBaseUrl: fallbackWsBase,
      timestamp: new Date().toISOString(),
    }
    setRuntimeWsBaseUrl(runtimeConfig.wsBaseUrl)
    console.log("   ⚠️  Using fallback config:", runtimeConfig)
    return runtimeConfig
  }
}

/**
 * Get current runtime configuration
 * Ensures config is loaded first
 */
export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  if (!runtimeConfig) {
    return await fetchRuntimeConfig()
  }
  return runtimeConfig
}

// =========================================================
// TYPES
// =========================================================

export interface DatabaseUser {
  id: number
  telegram_id: number
  full_name: string
  username: string | null
  phone: string | null
  role: string
  operator_id?: number | null  
  language: string
  region: string | null
  address: string | null
  abonent_id: string | null
  is_blocked: boolean
  is_online?: boolean
  last_seen_at?: string | null
  created_at: string
  updated_at: string
}

export interface Order {
  id: number
  application_number: string
  region: string
  address: string
  status: string
  created_at: string
  updated_at: string
}

export interface ConnectionOrder extends Order {
  business_type: string
  tarif_id: number | null
}

export interface TechnicianOrder extends Order {
  business_type: string
  abonent_id?: string
  description?: string
  comments?: string
}

export interface SmartServiceOrder extends Order {
  category: string
  service_type: string
}

export interface OperatorOrder {
  id: number
  application_number: string
  region: string
  address: string
  abonent_id: string | null
  description: string | null
  comments: string | null
  media: string | null
  media_type: string | null
  status: string
  created_at: string
  updated_at: string
  client_name: string
  client_phone: string | null
  client_telegram_id: number
}

// =========================================================
// USER FUNCTIONS
// =========================================================

/**
 * Get user info by telegram_id
 */
export async function getUserInfo(telegramId: number): Promise<DatabaseUser | null> {
  try {
    const url = `${API_BASE}/user/info?telegram_id=${telegramId}`
    console.log(`🔍 [getUserInfo] Fetching user info for telegram_id: ${telegramId}`)
    console.log(`   📍 URL: ${url}`)
    
    const res = await apiFetch(url)
    
    console.log(`   📥 Response status: ${res.status}`)
    
    if (res.status === 404) {
      console.log(`   ⚠️ User ${telegramId} not found in database (404)`)
      return null
    }
    
    if (!res.ok) {
      let error
      try {
        error = await res.json()
      } catch {
        error = { message: `HTTP ${res.status}`, detail: await res.text() }
      }
      console.error(`❌ [getUserInfo] Failed to fetch user:`, error)
      return null
    }
    
    const user = await res.json()
    console.log(`✅ [getUserInfo] User found:`, user)
    return user
  } catch (error) {
    console.error("❌ [getUserInfo] Error fetching user info:", error)
    return null
  }
}

/**
 * Bootstrap user: get existing user or create new one
 * @param tg - Telegram user data
 * @returns DatabaseUser or null if creation failed
 */
export async function bootstrapUser(tg: {
  id: number
  first_name?: string
  last_name?: string
  username?: string
}): Promise<DatabaseUser | null> {
  try {
    console.log(`🔄 [bootstrapUser] Starting bootstrap for telegram_id: ${tg.id}`)
    console.log(`   User data: ${JSON.stringify(tg)}`)
    
    // Get initData from Telegram WebApp
    const initData = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData
    
    // 1) Try to get existing user via /me endpoint (if initData available)
    if (initData) {
      console.log(`   Step 1: Trying /me endpoint with initData...`)
      try {
        const user = await getAuthenticatedUser()
        if (user) {
          console.log(`✅ [bootstrapUser] User found via /me endpoint`)
          return user
        }
      } catch (error) {
        console.warn(`⚠️ [bootstrapUser] /me endpoint failed, falling back to bootstrap:`, error)
      }
    }
    
    // 2) Fallback: Try to get existing user via /info endpoint
    console.log(`   Step 2: Checking if user exists via /info...`)
    const existingUser = await getUserInfo(tg.id)
    if (existingUser) {
      console.log(`✅ [bootstrapUser] User ${tg.id} already exists in database`)
      console.log(`   User details:`, existingUser)
      return existingUser
    }
    
    // 3) User not found - create via bootstrap endpoint
    console.log(`   Step 3: User not found, creating new user via bootstrap...`)
    const fullName = [tg.first_name || "", tg.last_name || ""].filter(Boolean).join(" ").trim() || "User"
    
    const bootstrapUrl = `${API_BASE}/user/bootstrap`
    const bootstrapBody = {
      telegram_id: tg.id,
      first_name: tg.first_name || null,
      last_name: tg.last_name || null,
      username: tg.username || null,
    }
    
    console.log(`   📡 Sending POST to: ${bootstrapUrl}`)
    console.log(`   📤 Request body:`, bootstrapBody)
    
    // Include initData header if available
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }
    if (initData) {
      headers['X-Telegram-Init-Data'] = initData
    }
    
    const res = await apiFetch(bootstrapUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(bootstrapBody),
    })
    
    console.log(`   📥 Response status: ${res.status}`)
    
    if (!res.ok) {
      let error
      try {
        error = await res.json()
      } catch {
        error = { message: `HTTP ${res.status}`, detail: await res.text() }
      }
      console.error(`❌ [bootstrapUser] Failed to bootstrap user:`, error)
      return null
    }
    
    const newUser = await res.json()
    console.log(`✅ [bootstrapUser] User ${tg.id} created successfully`)
    console.log(`   User details:`, newUser)
    return newUser
  } catch (error) {
    console.error("❌ [bootstrapUser] Error bootstrapping user:", error)
    if (error instanceof Error) {
      console.error(`   Error message: ${error.message}`)
      console.error(`   Stack: ${error.stack}`)
    }
    return null
  }
}

/**
 * Get user orders (all types)
 */
export async function getUserOrders(telegramId: number): Promise<{
  connection: ConnectionOrder[]
  technician: TechnicianOrder[]
  smart: SmartServiceOrder[]
}> {
  try {
    const res = await apiFetch(`${API_BASE}/user/orders?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      console.error(`Failed to fetch orders: HTTP ${res.status}`)
      return { connection: [], technician: [], smart: [] }
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching user orders:", error)
    return { connection: [], technician: [], smart: [] }
  }
}

// =========================================================
// OPERATOR FUNCTIONS
// =========================================================

/**
 * Get operator orders
 */
export async function getOperatorOrders(telegramId: number): Promise<OperatorOrder[]> {
  try {
    const res = await apiFetch(`${API_BASE}/operator/orders?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      if (res.status === 403) {
        console.error("Not authorized as operator")
        return []
      }
      console.error(`Failed to fetch operator orders: HTTP ${res.status}`)
      return []
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching operator orders:", error)
    return []
  }
}

/**
 * Get operator orders count
 */
export async function getOperatorOrdersCount(telegramId: number): Promise<number> {
  try {
    const res = await apiFetch(`${API_BASE}/operator/orders/count?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      return 0
    }
    
    const data = await res.json()
    return data.count || 0
  } catch (error) {
    console.error("Error fetching operator orders count:", error)
    return 0
  }
}

/**
 * Update order status
 */
export async function updateOrderStatus(
  orderId: number,
  status: string,
  telegramId: number
): Promise<boolean> {
  try {
    const res = await apiFetch(
      `${API_BASE}/operator/orders/${orderId}/status?status=${status}&telegram_id=${telegramId}`,
      { method: "PUT" }
    )
    
    return res.ok
  } catch (error) {
    console.error("Error updating order status:", error)
    return false
  }
}

/**
 * Add order comment
 */
export async function addOrderComment(
  orderId: number,
  comment: string,
  telegramId: number
): Promise<boolean> {
  try {
    const res = await apiFetch(
      `${API_BASE}/operator/orders/${orderId}/comment?comment=${encodeURIComponent(comment)}&telegram_id=${telegramId}`,
      { method: "PUT" }
    )
    
    return res.ok
  } catch (error) {
    console.error("Error adding order comment:", error)
    return false
  }
}

// =========================================================
// CHAT TYPES
// =========================================================

export interface StaffChat {
  id: number
  sender_id: number
  receiver_id: number
  status: "active" | "inactive"
  created_at: string
  updated_at: string
  last_activity_at: string
  sender_name?: string
  receiver_name?: string
}

export interface Chat {
  id: number
  client_id: number
  operator_id: number | null
  status: "active" | "inactive"
  created_at: string
  updated_at: string
  last_activity_at: string
  last_client_activity_at?: string | null
  client_name: string
  client_telegram_id: number
  operator_name: string | null
}

export interface Message {
  id: number
  chat_id: number
  sender_id: number | null
  sender_type: "client" | "operator" | "system"
  operator_id: number | null
  message_text: string
  attachments: Record<string, any> | null
  created_at: string
  sender_name: string | null
  sender_telegram_id: number | null
  sender_role: string | null
}

export interface ClientInfo {
  id: number
  telegram_id: number
  full_name: string
  username: string | null
  phone: string | null
  role: string
  language: string
  region: number | null
  address: string | null
  abonent_id: string | null
  is_online?: boolean
  last_seen_at?: string | null
  total_chats: number
  active_chats: number
  created_at: string
  updated_at: string
}

// =========================================================
// CHAT FUNCTIONS
// =========================================================

/**
 * Get user role from database
 */
export async function getUserRole(telegramId: number): Promise<{ role: string; user_id: number } | null> {
  try {
    const res = await apiFetch(`${API_BASE}/user/role?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching user role:", error)
    return null
  }
}

/**
 * Get authenticated user info including role and operator_id
 * This is the main endpoint for role-based routing
 * 
 * 🔐 Uses Telegram WebApp initData from X-Telegram-Init-Data header
 * No query params needed - all auth info comes from validated initData
 */
export async function getAuthenticatedUser(): Promise<DatabaseUser | null> {
  try {
    // Get initData from Telegram WebApp
    const initData = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData
    
    if (!initData) {
      console.warn('[getAuthenticatedUser] No Telegram initData available')
      return null
    }
    
    const res = await apiFetch(`${API_BASE}/user/me`, {
      headers: {
        'X-Telegram-Init-Data': initData
      }
    })
    
    if (!res.ok) {
      if (res.status === 404) {
        console.log(`User not found`)
        return null
      }
      if (res.status === 401) {
        console.warn(`Unauthorized - invalid Telegram initData`)
        return null
      }
      console.error(`Failed to fetch authenticated user: HTTP ${res.status}`)
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching authenticated user:", error)
    return null
  }
}

/**
 * Update user presence status (online/offline)
 */
export async function updateUserStatus(telegramId: number, isOnline: boolean): Promise<boolean> {
  try {
    const res = await apiFetch(`${API_BASE}/user/me/status?telegram_id=${telegramId}`, {
      method: "POST",
      body: JSON.stringify({
        is_online: isOnline
      })
    })
    
    if (!res.ok) {
      console.error(`Failed to update user status: HTTP ${res.status}`)
      return false
    }
    
    return true
  } catch (error) {
    console.error("Error updating user status:", error)
    return false
  }
}

/**
 * Get chats for user
 */
export async function getChats(telegramId: number, status?: string): Promise<Chat[]> {
  try {
    let url = `${API_BASE}/chat/list?telegram_id=${telegramId}`
    if (status) {
      url += `&status=${status}`
    }
    
    const res = await apiFetch(url)
    
    if (!res.ok) {
      console.error(`Failed to fetch chats: HTTP ${res.status}`)
      return []
    }
    
    const data = await res.json()
    return data.chats || []
  } catch (error) {
    console.error("Error fetching chats:", error)
    return []
  }
}

/**
 * Get chat by ID
 */
export async function getChat(chatId: number): Promise<Chat | null> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/${chatId}`)
    
    if (!res.ok) {
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching chat:", error)
    return null
  }
}

/**
 * Create a new chat (or reactivate inactive chat)
 * Note: subject removed per new schema
 */
export async function createChat(
  clientId: number,
  operatorId?: number
): Promise<Chat | null> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/create`, {
      method: "POST",
      body: JSON.stringify({
        client_id: clientId,
        operator_id: operatorId || null,
      }),
    })
    
    if (!res.ok) {
      console.error(`Failed to create chat: HTTP ${res.status}`)
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error creating chat:", error)
    return null
  }
}

/**
 * Get messages for a chat with cursor-based pagination (preferred) or offset pagination (fallback)
 * Supports since_ts/since_id for syncing after reconnect
 * If allMessages=true, returns ALL messages in chronological order (for supervisors viewing full history)
 */
export async function getChatMessages(
  chatId: number, 
  limit: number = 100, 
  offset: number = 0,
  cursorTs?: string,
  cursorId?: number,
  sinceTs?: string,
  sinceId?: number,
  allMessages: boolean = false
): Promise<Message[]> {
  try {
    let url = `${API_BASE}/chat/${chatId}/messages?limit=${limit}`
    
    // If allMessages is true, return all messages (for supervisors)
    if (allMessages) {
      url += `&all_messages=true`
    } else {
      // Priority: since_ts/since_id (for sync) > cursor > offset
      if (sinceTs || sinceId) {
        // Use since_ts/since_id for syncing messages after reconnect
        if (sinceTs) {
          url += `&since_ts=${encodeURIComponent(sinceTs)}`
        }
        if (sinceId) {
          url += `&since_id=${sinceId}`
        }
      } else if (cursorTs && cursorId) {
        // Use cursor pagination (preferred)
        url += `&cursor_ts=${encodeURIComponent(cursorTs)}&cursor_id=${cursorId}`
      } else {
        // Use offset pagination (fallback)
        url += `&offset=${offset}`
      }
    }
    
    console.log(`[getChatMessages] Requesting: ${url}`, {
      chatId,
      limit,
      offset,
      allMessages,
      cursorTs,
      cursorId,
      sinceTs,
      sinceId
    })
    
    const res = await apiFetch(url)
    
    if (!res.ok) {
      const errorText = await res.text().catch(() => 'Unable to read error response')
      console.error(`[getChatMessages] ❌ Failed to fetch messages: HTTP ${res.status}`, {
        chatId,
        url,
        status: res.status,
        statusText: res.statusText,
        errorBody: errorText,
        allMessages
      })
      // Return empty array but log error clearly
      return []
    }
    
    const data = await res.json()
    const messages = data.messages || []
    
    if (messages.length === 0) {
      console.warn(`[getChatMessages] ⚠️ No messages returned for chat ${chatId}`, {
        chatId,
        url,
        responseData: data,
        allMessages
      })
    } else {
      console.log(`[getChatMessages] ✅ Success: Received ${messages.length} messages for chat ${chatId}`, {
        chatId,
        messageCount: messages.length,
        firstMessageId: messages.length > 0 ? messages[0].id : null,
        lastMessageId: messages.length > 0 ? messages[messages.length - 1].id : null,
        allMessages
      })
    }
    
    return messages
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    console.error(`[getChatMessages] ❌ Error fetching messages for chat ${chatId}:`, {
      chatId,
      error: errorMsg,
      stack: error instanceof Error ? error.stack : undefined,
      allMessages
    })
    // Return empty array on error to prevent UI crashes
    return []
  }
}

/**
 * Send a message
 */
export async function sendMessage(
  chatId: number,
  senderId: number,
  messageText: string,
  senderType: "client" | "operator" | "system",
  attachments?: Record<string, any>
): Promise<number | null> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/${chatId}/messages`, {
      method: "POST",
      body: JSON.stringify({
        chat_id: chatId,
        sender_id: senderId,
        message_text: messageText,
        sender_type: senderType,
        operator_id: senderType === "operator" ? senderId : null,
        attachments: attachments || null,
      }),
    })
    
    if (!res.ok) {
      console.error(`Failed to send message: HTTP ${res.status}`)
      return null
    }
    
    const data = await res.json()
    return data.message_id || null
  } catch (error) {
    console.error("Error sending message:", error)
    return null
  }
}

/**
 * Close a chat
 */
export async function closeChat(chatId: number): Promise<boolean> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/${chatId}/close`, {
      method: "PUT",
    })
    
    return res.ok
  } catch (error) {
    console.error("Error closing chat:", error)
    return false
  }
}

/**
 * Assign chat to operator (race-safe)
 * Returns true if successful, false if already assigned (409 Conflict)
 */
export async function assignChat(chatId: number, operatorId: number): Promise<{ success: boolean; error?: string }> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/${chatId}/assign`, {
      method: "PUT",
      body: JSON.stringify({
        operator_id: operatorId,
      }),
    })
    
    if (res.status === 409) {
      const data = await res.json().catch(() => ({}))
      return { success: false, error: data.detail || "Chat already assigned to another operator" }
    }
    
    return { success: res.ok }
  } catch (error) {
    console.error("Error assigning chat:", error)
    return { success: false, error: "Network error" }
  }
}

/**
 * Get client info for a chat
 */
export async function getClientInfo(chatId: number): Promise<ClientInfo | null> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/${chatId}/client-info`)
    
    if (!res.ok) {
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching client info:", error)
    return null
  }
}

/**
 * Get available clients (for operators)
 */
export async function getAvailableClients(limit: number = 50, offset: number = 0): Promise<ClientInfo[]> {
  try {
    const res = await apiFetch(`${API_BASE}/user/clients?limit=${limit}&offset=${offset}`)
    
    if (!res.ok) {
      return []
    }
    
    const data = await res.json()
    return data.clients || []
  } catch (error) {
    console.error("Error fetching clients:", error)
    return []
  }
}

/**
 * Mark inactive chats (background job endpoint)
 */
export async function markInactiveChats(): Promise<number> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/mark-inactive`, {
      method: "POST",
    })
    
    if (!res.ok) {
      console.error(`Failed to mark inactive chats: HTTP ${res.status}`)
      return 0
    }
    
    const data = await res.json()
    return data.chats_marked_inactive || 0
  } catch (error) {
    console.error("Error marking inactive chats:", error)
    return 0
  }
}

/**
 * Get supervisor inbox (chats without operator) with cursor pagination
 */
export async function getInbox(
  telegramId: number,
  limit: number = 20,
  cursorTs?: string,
  cursorId?: number
): Promise<{ chats: Chat[]; count: number }> {
  try {
    let url = `${API_BASE}/chat/inbox?telegram_id=${telegramId}&limit=${limit}`
    if (cursorTs) {
      url += `&cursor_ts=${encodeURIComponent(cursorTs)}`
    }
    if (cursorId) {
      url += `&cursor_id=${cursorId}`
    }
    
    const res = await apiFetch(url)
    
    if (!res.ok) {
      console.error(`Failed to fetch inbox: HTTP ${res.status}`)
      return { chats: [], count: 0 }
    }
    
    const data = await res.json()
    return { chats: data.chats || [], count: data.count || 0 }
  } catch (error) {
    console.error("Error fetching inbox:", error)
    return { chats: [], count: 0 }
  }
}

/**
 * Get supervisor active chats (assigned chats) with cursor pagination
 */
export async function getActiveChats(
  telegramId: number,
  limit: number = 20,
  cursorTs?: string,
  cursorId?: number
): Promise<{ chats: Chat[]; count: number }> {
  try {
    let url = `${API_BASE}/chat/active?telegram_id=${telegramId}&limit=${limit}`
    if (cursorTs) {
      url += `&cursor_ts=${encodeURIComponent(cursorTs)}`
    }
    if (cursorId) {
      url += `&cursor_id=${cursorId}`
    }
    
    const res = await apiFetch(url)
    
    if (!res.ok) {
      console.error(`Failed to fetch active chats: HTTP ${res.status}`)
      return { chats: [], count: 0 }
    }
    
    const data = await res.json()
    return { chats: data.chats || [], count: data.count || 0 }
  } catch (error) {
    console.error("Error fetching active chats:", error)
    return { chats: [], count: 0 }
  }
}

/**
 * Get operator's assigned chats with cursor pagination
 */
export async function getMyChats(
  telegramId: number,
  limit: number = 20,
  cursorTs?: string,
  cursorId?: number
): Promise<{ chats: Chat[]; count: number }> {
  try {
    let url = `${API_BASE}/chat/my?telegram_id=${telegramId}&limit=${limit}`
    if (cursorTs) {
      url += `&cursor_ts=${encodeURIComponent(cursorTs)}`
    }
    if (cursorId) {
      url += `&cursor_id=${cursorId}`
    }
    
    const res = await apiFetch(url)
    
    if (!res.ok) {
      console.error(`Failed to fetch operator chats: HTTP ${res.status}`)
      return { chats: [], count: 0 }
    }
    
    const data = await res.json()
    return { chats: data.chats || [], count: data.count || 0 }
  } catch (error) {
    console.error("Error fetching operator chats:", error)
    return { chats: [], count: 0 }
  }
}

/**
 * Get active chat statistics: inbox_count and operator_counts
 */
export interface ActiveChatStats {
  inbox_count: number
  operator_counts: Array<{ operator_id: number; cnt: number }>
}

export async function getActiveChatStats(): Promise<ActiveChatStats | null> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/stats/active`)
    
    if (!res.ok) {
      console.error(`Failed to fetch active chat stats: HTTP ${res.status}`)
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching active chat stats:", error)
    return null
  }
}

/**
 * Search clients
 */
export async function searchClients(query: string, limit: number = 20): Promise<ClientInfo[]> {
  try {
    const res = await apiFetch(`${API_BASE}/user/clients/search?q=${encodeURIComponent(query)}&limit=${limit}`)
    
    if (!res.ok) {
      return []
    }
    
    const data = await res.json()
    return data.clients || []
  } catch (error) {
    console.error("Error searching clients:", error)
    return []
  }
}

/**
 * Get client info by user ID
 */
export async function getClientInfoByUserId(userId: number): Promise<ClientInfo | null> {
  try {
    const res = await apiFetch(`${API_BASE}/user/client-info?user_id=${userId}`)
    
    if (!res.ok) {
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching client info:", error)
    return null
  }
}

/**
 * Get list of call center operators (for supervisors)
 */
export async function getOperators(limit: number = 100): Promise<ClientInfo[]> {
  try {
    const res = await apiFetch(`${API_BASE}/user/operators?limit=${limit}`)
    
    if (!res.ok) {
      return []
    }
    
    const data = await res.json()
    return data.operators || []
  } catch (error) {
    console.error("Error fetching operators:", error)
    return []
  }
}

/**
 * WebSocket connection for real-time chat
 */
export class ChatWebSocket {
  private ws: WebSocket | null = null
  private chatId: number
  private userId: number
  private telegramId: number
  private onMessage: (message: Message) => void
  private onTyping: (userId: number, isTyping: boolean) => void
  private onError: (error: Error) => void
  private onChatAssigned?: (chatId: number, operatorId: number) => void
  private onChatInactive?: (chatId: number) => void
  private onReconnect?: () => void
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private wasConnected = false
  private pingInterval: NodeJS.Timeout | null = null
  private lastPongTime: number = Date.now()

  constructor(
    chatId: number,
    telegramId: number,
    userId: number,
    onMessage: (message: Message) => void,
    onTyping: (userId: number, isTyping: boolean) => void,
    onError: (error: Error) => void,
    onChatAssigned?: (chatId: number, operatorId: number) => void,
    onChatInactive?: (chatId: number) => void,
    onReconnect?: () => void
  ) {
    this.chatId = chatId
    this.telegramId = telegramId
    this.userId = userId
    this.onMessage = onMessage
    this.onTyping = onTyping
    this.onError = onError
    this.onChatAssigned = onChatAssigned
    this.onChatInactive = onChatInactive
    this.onReconnect = onReconnect
  }

  private buildEndpoint(): string {
    return buildWsUrl(`/ws/chat?chat_id=${this.chatId}&telegram_id=${this.telegramId}`)
  }

  connect(): void {
    try {
      const wsEndpoint = this.buildEndpoint()

      if (!wsEndpoint) {
        console.error(`[ChatWebSocket] Failed to build WebSocket URL for chat ${this.chatId}`)
        this.onError(new Error("Failed to build WebSocket URL"))
        return
      }

      console.log(`[ChatWebSocket] Connecting WebSocket to: ${wsEndpoint}`, {
        chatId: this.chatId,
        telegramId: this.telegramId,
        userId: this.userId,
      })
      this.ws = new WebSocket(wsEndpoint)

      this.ws.onopen = () => {
        console.log(`[ChatWebSocket] WebSocket connected for chat ${this.chatId}, telegramId: ${this.telegramId}`)
        if (this.wasConnected && this.onReconnect) {
          console.log(`[ChatWebSocket] WebSocket reconnected for chat ${this.chatId} - triggering sync`)
          this.onReconnect()
        }
        this.wasConnected = true
        this.reconnectAttempts = 0

        if (this.pingInterval) {
          clearInterval(this.pingInterval)
        }
        this.pingInterval = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
              this.ws.send("ping")
              console.log(`[ChatWebSocket] Sent ping to chat ${this.chatId}`)
            } catch (error) {
              console.error(`[ChatWebSocket] Error sending ping: ${error}`)
            }
          }
        }, 10000)
      }

      this.ws.onmessage = (event) => {
        this.handleIncomingMessage(event.data)
      }

      this.ws.onerror = (error) => {
        console.error(`[ChatWebSocket] WebSocket error for chat ${this.chatId}, telegram ${this.telegramId}:`, error)
        console.error(`[ChatWebSocket] WebSocket URL was: ${wsEndpoint}`)
        console.error(`[ChatWebSocket] WebSocket error details:`, {
          chatId: this.chatId,
          telegramId: this.telegramId,
          userId: this.userId,
          readyState: this.ws?.readyState,
          url: wsEndpoint
        })
        if (this.onError) {
          this.onError(new Error(`WebSocket connection failed for chat ${this.chatId}`))
        }
      }

      this.ws.onclose = (event) => {
        console.log(`[ChatWebSocket] WebSocket disconnected for chat ${this.chatId}, telegram ${this.telegramId}`, {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        })
        if (event.code !== 1000) {
          this.attemptReconnect()
        }
      }
    } catch (error) {
      console.warn("[ChatWebSocket] Error creating WebSocket (will fallback to polling):", error)
    }
  }

  private handleIncomingMessage(raw: any): void {
    if (typeof raw === "string" && raw === "pong") {
      this.lastPongTime = Date.now()
      console.log(`[ChatWebSocket] Received pong for chat ${this.chatId}`)
      return
    }

    let data: any = raw
    if (typeof raw === "string") {
      try {
        data = JSON.parse(raw)
      } catch (error) {
        console.error(`[ChatWebSocket] Error parsing WebSocket payload for chat ${this.chatId}:`, error)
        return
      }
    }

    if (!data) return

    const eventType: string | undefined = data.event || data.type
    if (!eventType) {
      console.warn("[ChatWebSocket] Received payload without event/type", data)
      return
    }

    switch (eventType) {
      case "message.new":
      case "chat.message":
      case "new_message":
      case "message_sent": {
        const message = data.payload ?? data.message ?? data
        if (message) {
          this.onMessage(message as Message)
        }
        break
      }
      case "typing": {
        const payload = data.payload ?? data
        const typingUserId = payload?.user_id ?? payload?.sender_id ?? this.userId
        if (typeof payload?.is_typing !== "undefined") {
          this.onTyping(typingUserId, Boolean(payload.is_typing))
        }
        break
      }
      case "chat.assigned": {
        const payload = data.payload ?? data
        if (this.onChatAssigned && payload?.chat_id && payload?.operator_id) {
          this.onChatAssigned(payload.chat_id, payload.operator_id)
        }
        break
      }
      case "chat.inactive": {
        const payload = data.payload ?? data
        if (this.onChatInactive && payload?.chat_id) {
          this.onChatInactive(payload.chat_id)
        }
        break
      }
      case "initial_messages": {
        const payload = data.payload ?? data
        const messages = (payload?.messages || []) as Message[]
        messages.forEach((msg) => this.onMessage(msg))
        break
      }
      case "pong": {
        this.lastPongTime = Date.now()
        break
      }
      default:
        console.log(`[ChatWebSocket] Ignoring unsupported event '${eventType}' for chat ${this.chatId}`)
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      setTimeout(() => {
        console.log(`Attempting to reconnect WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
        this.connect()
      }, this.reconnectDelay * this.reconnectAttempts)
    } else {
      console.warn(`Failed to reconnect WebSocket after ${this.maxReconnectAttempts} attempts, falling back to polling`)
    }
  }

  // Legacy helpers retained for compatibility but no longer send data over WS.
  sendMessage(): void {
    console.warn("[ChatWebSocket] sendMessage is deprecated. Use REST API sendMessage instead.")
  }

  sendTyping(): void {
    console.warn("[ChatWebSocket] sendTyping is deprecated. Typing indicators use REST events.")
  }

  disconnect(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
  
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
  
  getReadyState(): number | null {
    return this.ws?.readyState ?? null
  }
}

/**
 * WebSocket connection for stats updates (operators and supervisors)
 * Tracks online/offline status
 */
export class StatsWebSocket {
  private ws: WebSocket | null = null
  private userId: number
  private onStatsUpdate?: (stats: ActiveChatStats) => void
  private onUserOnline?: (userId: number, role?: string) => void
  private onUserOffline?: (userId: number, role?: string) => void
  private onChatEvent?: (event: any) => void
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private pingInterval: NodeJS.Timeout | null = null

  constructor(
    userId: number,
    onStatsUpdate?: (stats: ActiveChatStats) => void,
    onUserOnline?: (userId: number, role?: string) => void,
    onUserOffline?: (userId: number, role?: string) => void,
    onChatEvent?: (event: any) => void
  ) {
    this.userId = userId
    this.onStatsUpdate = onStatsUpdate
    this.onUserOnline = onUserOnline
    this.onUserOffline = onUserOffline
    this.onChatEvent = onChatEvent
  }

  connect(): void {
    try {
      // Build WebSocket URL using unified helper
      const wsEndpoint = buildWsUrl(`/ws/stats?user_id=${this.userId}`)
      
      if (!wsEndpoint) {
        console.error(`[StatsWebSocket] Failed to build WebSocket URL for user ${this.userId}`, {
          NEXT_PUBLIC_API_ORIGIN: process.env.NEXT_PUBLIC_API_ORIGIN,
          NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL
        })
        return
      }
      
      console.log(`[StatsWebSocket] Connecting to: ${wsEndpoint}`, {
        userId: this.userId,
        env: {
          NEXT_PUBLIC_API_ORIGIN: process.env.NEXT_PUBLIC_API_ORIGIN,
          NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL
        }
      })
      this.ws = new WebSocket(wsEndpoint)

      this.ws.onopen = () => {
        console.log(`[StatsWebSocket] ✅ Connected for user ${this.userId}`, {
          readyState: this.ws?.readyState,
          url: wsEndpoint
        })
        this.reconnectAttempts = 0
        
        // Send ping every 30 seconds to keep connection alive
        this.pingInterval = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: "ping" }))
          }
        }, 30000)
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === "stats.initial" || data.type === "stats.changed") {
            if (this.onStatsUpdate) {
              this.onStatsUpdate({
                inbox_count: data.inbox_count,
                operator_counts: data.operator_counts
              })
            }
            // Handle initial online users list
            if (data.online_users && Array.isArray(data.online_users)) {
              data.online_users.forEach((uid: number) => {
                if (this.onUserOnline) {
                  this.onUserOnline(uid)
                }
              })
            }
          } else if (data.type === "user.online") {
            if (this.onUserOnline) {
              this.onUserOnline(data.user_id, data.role)
            }
          } else if (data.type === "user.offline") {
            if (this.onUserOffline) {
              this.onUserOffline(data.user_id, data.role)
            }
          } else if (data.type && data.type.startsWith("chat.")) {
            if (this.onChatEvent) {
              this.onChatEvent(data)
            }
          } else if (data.type === "pong") {
            // Keep-alive response
          }
        } catch (error) {
          console.error("[StatsWebSocket] Error parsing message:", error)
        }
      }

      this.ws.onerror = (error) => {
        console.error(`[StatsWebSocket] ❌ WebSocket error for user ${this.userId}:`, error, {
          readyState: this.ws?.readyState,
          url: wsEndpoint
        })
      }

      this.ws.onclose = (event) => {
        console.log(`[StatsWebSocket] 🔌 WebSocket closed for user ${this.userId}`, {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        })
        this.ws = null
        
        if (this.pingInterval) {
          clearInterval(this.pingInterval)
          this.pingInterval = null
        }
        
        // Attempt to reconnect
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++
          const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
          console.log(`[StatsWebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
          setTimeout(() => this.connect(), delay)
        }
      }
    } catch (error) {
      console.error(`[StatsWebSocket] Failed to connect:`, error)
    }
  }

  disconnect(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}

/**
 * WebSocket connection for real-time staff chat
 */
export class StaffChatWebSocket {
  private ws: WebSocket | null = null
  private chatId: number
  private userId: number
  private onMessage: (message: any) => void
  private onTyping: (userId: number, isTyping: boolean) => void
  private onError: (error: Error) => void
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private wasConnected = false

  constructor(
    chatId: number,
    userId: number,
    onMessage: (message: any) => void,
    onTyping: (userId: number, isTyping: boolean) => void,
    onError: (error: Error) => void
  ) {
    this.chatId = chatId
    this.userId = userId
    this.onMessage = onMessage
    this.onTyping = onTyping
    this.onError = onError
  }

  connect(): void {
    try {
      // Build WebSocket URL using unified helper
      const wsEndpoint = buildWsUrl(`/ws/staff-chat/${this.chatId}?user_id=${this.userId}`)
      
      if (!wsEndpoint) {
        console.error(`[StaffChatWebSocket] Failed to build WebSocket URL for staff chat ${this.chatId}`)
        if (this.onError) {
          this.onError(new Error("Failed to build WebSocket URL"))
        }
        return
      }
      
      console.log(`[StaffChatWebSocket] Connecting to: ${wsEndpoint}`)
      this.ws = new WebSocket(wsEndpoint)

      this.ws.onopen = () => {
        console.log(`[StaffChatWebSocket] Connected for staff chat ${this.chatId}, userId: ${this.userId}`)
        this.wasConnected = true
        this.reconnectAttempts = 0
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === "staff.message") {
            if (data.message) {
              this.onMessage(data.message)
            }
          } else if (data.type === "message_sent") {
            if (data.message) {
              this.onMessage(data.message)
            }
          } else if (data.type === "staff.typing") {
            this.onTyping(data.user_id, data.is_typing)
          } else if (data.type === "initial_messages") {
            const messages = data.messages || []
            messages.forEach((msg: any) => this.onMessage(msg))
          }
        } catch (error) {
          console.error("[StaffChatWebSocket] Error parsing message:", error)
        }
      }

      this.ws.onerror = (error) => {
        console.error(`[StaffChatWebSocket] WebSocket error for staff chat ${this.chatId}:`, error)
        if (this.onError) {
          this.onError(new Error(`WebSocket connection failed for staff chat ${this.chatId}`))
        }
      }

      this.ws.onclose = (event) => {
        console.log(`[StaffChatWebSocket] WebSocket disconnected for staff chat ${this.chatId}`)
        if (event.code !== 1000) {
          this.attemptReconnect()
        }
      }
    } catch (error) {
      console.warn("Error creating StaffChatWebSocket:", error)
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      setTimeout(() => {
        console.log(`Attempting to reconnect StaffChatWebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
        this.connect()
      }, this.reconnectDelay * this.reconnectAttempts)
    }
  }

  sendMessage(messageText: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "message",
        message_text: messageText,
      }))
    }
  }

  sendTyping(isTyping: boolean): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "typing",
        is_typing: isTyping,
      }))
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}

// =========================================================
// STAFF CHAT FUNCTIONS
// =========================================================

/**
 * Get staff chats for a user
 */
export async function getStaffChats(telegramId: number): Promise<{ chats: StaffChat[]; count: number }> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/staff/list?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      console.error(`Failed to fetch staff chats: HTTP ${res.status}`)
      return { chats: [], count: 0 }
    }
    
    const data = await res.json()
    return { chats: data.chats || [], count: data.count || 0 }
  } catch (error) {
    console.error("Error fetching staff chats:", error)
    return { chats: [], count: 0 }
  }
}

/**
 * Get a single staff chat by ID
 */
export async function getStaffChat(chatId: number, telegramId: number): Promise<StaffChat | null> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/staff/${chatId}?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      console.error(`Failed to fetch staff chat: HTTP ${res.status}`)
      return null
    }
    
    const data = await res.json()
    return data || null
  } catch (error) {
    console.error("Error fetching staff chat:", error)
    return null
  }
}

/**
 * Create a new staff chat
 */
export async function createStaffChat(senderId: number, receiverId: number, telegramId?: number): Promise<StaffChat | null> {
  try {
    let senderTelegramId = telegramId
    
    // If telegramId not provided, try to get it from senderId (assuming senderId is user.id)
    if (!senderTelegramId) {
      // Try to get user info by user_id (if there's an endpoint for that)
      // For now, we'll need telegramId to be passed from ChatContext
      console.error("[createStaffChat] telegramId is required but not provided")
      return null
    }
    
    const res = await apiFetch(`${API_BASE}/chat/staff/create?telegram_id=${senderTelegramId}`, {
      method: "POST",
      body: JSON.stringify({
        receiver_id: receiverId,
      }),
    })
    
    if (!res.ok) {
      const errorText = await res.text()
      console.error(`Failed to create staff chat: HTTP ${res.status}`, errorText)
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error creating staff chat:", error)
    return null
  }
}

/**
 * Get messages for a staff chat
 */
export async function getStaffChatMessages(
  chatId: number,
  telegramId: number,
  limit: number = 100,
  offset: number = 0
): Promise<Message[]> {
  try {
    const url = `${API_BASE}/chat/staff/${chatId}/messages?telegram_id=${telegramId}&limit=${limit}&offset=${offset}`
    
    console.log(`[getStaffChatMessages] Requesting: ${url}`, {
      chatId,
      telegramId,
      limit,
      offset
    })
    
    const res = await apiFetch(url)
    
    if (!res.ok) {
      const errorText = await res.text().catch(() => 'Unable to read error response')
      console.error(`[getStaffChatMessages] ❌ Failed to fetch staff messages: HTTP ${res.status}`, {
        chatId,
        telegramId,
        url,
        status: res.status,
        statusText: res.statusText,
        errorBody: errorText
      })
      return []
    }
    
    const data = await res.json()
    const messages = data.messages || []
    
    if (messages.length === 0) {
      console.warn(`[getStaffChatMessages] ⚠️ No messages returned for staff chat ${chatId}`, {
        chatId,
        telegramId,
        url,
        responseData: data
      })
    } else {
      console.log(`[getStaffChatMessages] ✅ Success: Received ${messages.length} messages for staff chat ${chatId}`, {
        chatId,
        telegramId,
        messageCount: messages.length,
        firstMessageId: messages.length > 0 ? messages[0].id : null,
        lastMessageId: messages.length > 0 ? messages[messages.length - 1].id : null
      })
    }
    
    return messages
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error)
    console.error(`[getStaffChatMessages] ❌ Error fetching staff messages for chat ${chatId}:`, {
      chatId,
      telegramId,
      error: errorMsg,
      stack: error instanceof Error ? error.stack : undefined
    })
    return []
  }
}

/**
 * Send a message in a staff chat
 */
export async function sendStaffMessage(
  chatId: number,
  senderId: number,
  messageText: string,
  telegramId?: number,
  attachments?: Record<string, any>
): Promise<number | null> {
  try {
    if (!telegramId) {
      console.error("[sendStaffMessage] telegramId is required but not provided")
      return null
    }
    
    const res = await apiFetch(`${API_BASE}/chat/staff/${chatId}/messages?telegram_id=${telegramId}`, {
      method: "POST",
      body: JSON.stringify({
        sender_id: senderId,
        message_text: messageText,
        attachments: attachments || null,
      }),
    })
    
    if (!res.ok) {
      const errorText = await res.text()
      console.error(`Failed to send staff message: HTTP ${res.status}`, errorText)
      return null
    }
    
    const data = await res.json()
    return data.message_id || null
  } catch (error) {
    console.error("Error sending staff message:", error)
    return null
  }
}

/**
 * Get available staff members for chat
 */
export async function getAvailableStaff(telegramId: number): Promise<ClientInfo[]> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/staff/available?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      console.error(`Failed to fetch available staff: HTTP ${res.status}`)
      return []
    }
    
    const data = await res.json()
    return data.staff || []
  } catch (error) {
    console.error("Error fetching available staff:", error)
    return []
  }
}

/**
 * Close a staff chat
 */
export async function closeStaffChat(chatId: number, telegramId: number): Promise<boolean> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/staff/${chatId}/close?telegram_id=${telegramId}`, {
      method: "PUT",
    })
    
    return res.ok
  } catch (error) {
    console.error("Error closing staff chat:", error)
    return false
  }
}

// =========================================================
// CCS STATISTICS FUNCTIONS
// =========================================================

/**
 * CCS Statistics Types
 */
export interface CCSOperator {
  id: number
  telegram_id: number
  full_name: string | null
  username: string | null
  phone: string | null
  role: string
  is_online: boolean
  last_seen_at: string | null
  created_at: string
  active_chats_count: number
  total_answered_chats: number
  today_answered_chats: number
  week_answered_chats: number
  total_messages_sent: number
}

export interface CCSClient {
  id: number
  telegram_id: number
  full_name: string | null
  username: string | null
  phone: string | null
  is_online: boolean
  last_seen_at: string | null
  region: string | null
  abonent_id: string | null
  active_chats_count: number
  total_chats_count: number
  last_chat_at: string | null
}

export interface CCSOverview {
  total_operators: number
  online_operators: number
  total_supervisors: number
  online_supervisors: number
  total_clients: number
  online_clients: number
  active_chats: number
  inbox_chats: number
  assigned_chats: number
  today_chats: number
  week_chats: number
  month_chats: number
  today_messages: number
  week_messages: number
}

export interface CCSDailyTrend {
  date: string
  total_chats: number
  answered_chats: number
  closed_chats: number
}

export interface CCSStatistics {
  operators: CCSOperator[]
  clients: CCSClient[]
  overview: CCSOverview
  daily_trends: CCSDailyTrend[]
}

/**
 * Get comprehensive CCS statistics
 * Includes operators, clients, overview and daily trends
 */
export async function getCCSStatistics(telegramId: number): Promise<CCSStatistics | null> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/ccs/statistics?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      console.error(`Failed to fetch CCS statistics: HTTP ${res.status}`)
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching CCS statistics:", error)
    return null
  }
}

/**
 * Get detailed statistics for a specific operator
 */
export async function getOperatorStatistics(operatorId: number, telegramId: number): Promise<any | null> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/ccs/operator/${operatorId}?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      console.error(`Failed to fetch operator statistics: HTTP ${res.status}`)
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching operator statistics:", error)
    return null
  }
}

/**
 * Get online users summary (for quick real-time updates)
 */
export async function getOnlineSummary(telegramId: number): Promise<any | null> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/ccs/online-summary?telegram_id=${telegramId}`)
    
    if (!res.ok) {
      console.error(`Failed to fetch online summary: HTTP ${res.status}`)
      return null
    }
    
    return await res.json()
  } catch (error) {
    console.error("Error fetching online summary:", error)
    return null
  }
}

/**
 * Get list of recently active clients
 */
export async function getRecentClients(telegramId: number, limit: number = 50): Promise<CCSClient[]> {
  try {
    const res = await apiFetch(`${API_BASE}/chat/ccs/recent-clients?telegram_id=${telegramId}&limit=${limit}`)
    
    if (!res.ok) {
      console.error(`Failed to fetch recent clients: HTTP ${res.status}`)
      return []
    }
    
    const data = await res.json()
    return data.clients || []
  } catch (error) {
    console.error("Error fetching recent clients:", error)
    return []
  }
}

