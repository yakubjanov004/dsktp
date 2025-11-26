import { getRuntimeConfig } from "./api"
import { buildNgrokBypassHeaders, normalizeBaseUrl } from "./network"

/**
 * User presence utilities
 * Helper functions for online/offline status and last seen labels
 * 
 * Supports both:
 * - Production: Telegram WebApp with initData
 * - Development: Browser without Telegram (uses telegram_id query param fallback)
 */

let presenceApiBase = normalizeBaseUrl(process.env.NEXT_PUBLIC_API_BASE || "/api") || "/api"

// Store telegram_id for dev fallback (set from page.tsx when user is loaded)
let _cachedTelegramId: number | null = null

/**
 * Set telegram_id for dev fallback mode
 * Called from page.tsx after user is loaded
 */
export function setPresenceTelegramId(telegramId: number | null): void {
  _cachedTelegramId = telegramId
  console.log(`[presence] Telegram ID set for dev fallback: ${telegramId}`)
}

async function resolvePresenceApiBase(): Promise<string> {
  if (presenceApiBase && presenceApiBase !== "/api") {
    return presenceApiBase
  }
  try {
    const config = await getRuntimeConfig()
    if (config?.apiBaseUrl) {
      presenceApiBase = normalizeBaseUrl(config.apiBaseUrl) || "/api"
    }
  } catch (error) {
    console.warn("[presence] Failed to resolve runtime API base:", error)
  }
  return presenceApiBase
}

/**
 * Check if running inside Telegram WebApp
 */
export function isTelegramWebApp(): boolean {
  return typeof window !== 'undefined' && 
         !!window.Telegram?.WebApp?.initData &&
         window.Telegram.WebApp.initData.length > 0
}

/**
 * Set user online/offline status (heartbeat)
 * @param isOnline - Whether user is online
 * 
 * 🔐 Production: Uses Telegram WebApp initData from X-Telegram-Init-Data header
 * 🛠️ Development: Uses telegram_id query param for dev fallback (when no initData)
 */
export async function setOnlineStatus(isOnline: boolean): Promise<boolean> {
  try {
    // Get initData from Telegram WebApp
    const initData = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData
    
    const API_BASE = await resolvePresenceApiBase()
    
    // ========================================
    // PRODUCTION: Telegram WebApp with initData
    // ========================================
    if (initData) {
      const url = `${API_BASE}/user/me/status`
      
      // Use fetch with keepalive for offline status (page unload, visibility change)
      const useKeepalive = !isOnline && typeof navigator !== 'undefined'
      
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData,
        ...buildNgrokBypassHeaders(),
      }

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify({ is_online: isOnline }),
        credentials: "include",
        keepalive: useKeepalive
      })

      if (!response.ok) {
        console.error(`[setOnlineStatus] Failed: HTTP ${response.status}`)
        return false
      }

      console.log(`[setOnlineStatus] ✅ Status updated (production): is_online=${isOnline}`)
      return true
    }
    
    // ========================================
    // DEVELOPMENT: Fallback without Telegram
    // ========================================
    // TODO: dev fallback - use telegram_id query param
    if (_cachedTelegramId) {
      const url = `${API_BASE}/user/status/dev?telegram_id=${_cachedTelegramId}`
      
      const useKeepalive = !isOnline && typeof navigator !== 'undefined'
      
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...buildNgrokBypassHeaders(),
      }

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify({ is_online: isOnline }),
        credentials: "include",
        keepalive: useKeepalive
      })

      if (!response.ok) {
        // Dev endpoint may not exist - that's okay, just log warning
        console.warn(`[setOnlineStatus] Dev fallback failed: HTTP ${response.status} (this is okay in production)`)
        return false
      }

      console.log(`[setOnlineStatus] ✅ Status updated (dev fallback): is_online=${isOnline}, telegram_id=${_cachedTelegramId}`)
      return true
    }
    
    // No initData and no cached telegram_id - cannot update status
    console.warn('[setOnlineStatus] No Telegram initData and no cached telegram_id - cannot update status')
    return false
    
  } catch (error) {
    console.error("[setOnlineStatus] Error:", error)
    return false
  }
}

/**
 * Get human-readable label for user's last seen status
 * @param isOnline - Whether user is currently online
 * @param lastSeenAt - ISO timestamp string of when user was last seen
 * @returns Human-readable label like "Online", "5 daqiqa oldin", etc.
 */
export function getLastSeenLabel(
  isOnline: boolean,
  lastSeenAt?: string | null
): string {
  if (isOnline) {
    return "Online"
  }

  if (!lastSeenAt) {
    return "Offline"
  }

  try {
    const last = new Date(lastSeenAt).getTime()
    const now = Date.now()
    const diffMs = now - last

    // Handle future dates (clock skew)
    if (diffMs < 0) {
      return "Online"
    }

    const diffMin = Math.floor(diffMs / 60000)

    if (diffMin < 1) {
      return "Hozirgina online edi"
    }
    if (diffMin === 1) {
      return "1 daqiqa oldin"
    }
    if (diffMin < 60) {
      return `${diffMin} daqiqa oldin`
    }

    const diffHours = Math.floor(diffMin / 60)
    if (diffHours === 1) {
      return "1 soat oldin"
    }
    if (diffHours < 24) {
      return `${diffHours} soat oldin`
    }

    const diffDays = Math.floor(diffHours / 24)
    if (diffDays === 1) {
      return "1 kun oldin"
    }
    if (diffDays < 7) {
      return `${diffDays} kun oldin`
    }

    const diffWeeks = Math.floor(diffDays / 7)
    if (diffWeeks === 1) {
      return "1 hafta oldin"
    }
    if (diffWeeks < 4) {
      return `${diffWeeks} hafta oldin`
    }

    const diffMonths = Math.floor(diffDays / 30)
    if (diffMonths === 1) {
      return "1 oy oldin"
    }
    if (diffMonths < 12) {
      return `${diffMonths} oy oldin`
    }

    return "Uzoq vaqt oldin"
  } catch (error) {
    console.error("[getLastSeenLabel] Error parsing date:", error)
    return "Offline"
  }
}

