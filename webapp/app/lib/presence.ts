import { getRuntimeConfig } from "./api"
import { buildNgrokBypassHeaders, normalizeBaseUrl } from "./network"

/**
 * User presence utilities
 * Helper functions for online/offline status and last seen labels
 */

let presenceApiBase = normalizeBaseUrl(process.env.NEXT_PUBLIC_API_BASE || "/api") || "/api"

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
 * Set user online/offline status (heartbeat)
 * @param isOnline - Whether user is online
 * 
 * 🔐 Uses Telegram WebApp initData from X-Telegram-Init-Data header
 * No query params needed - all auth info comes from validated initData
 */
export async function setOnlineStatus(isOnline: boolean): Promise<boolean> {
  try {
    // Get initData from Telegram WebApp
    const initData = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData
    
    if (!initData) {
      console.warn('[setOnlineStatus] No Telegram initData available')
      return false
    }

    const API_BASE = await resolvePresenceApiBase()
    const url = `${API_BASE}/user/me/status`
    
    // Use fetch with keepalive for offline status (page unload, visibility change)
    // keepalive ensures the request completes even if page is closing
    // Always use keepalive for offline status to ensure last_seen_at is updated
    // keepalive is supported in modern browsers and helps ensure the request completes
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
      keepalive: useKeepalive  // Keep connection alive for faster send on page unload
    })

    if (!response.ok) {
      console.error(`[setOnlineStatus] Failed: HTTP ${response.status}`)
      return false
    }

    console.log(`[setOnlineStatus] Status updated: is_online=${isOnline}`)
    return true
  } catch (error) {
    console.error("[setOnlineStatus] Error:", error)
    return false
  }
}

/**
 * Get human-readable label for user's last seen status
 * @param isOnline - Whether user is currently online
 * @param lastSeenAt - ISO timestamp string of when user was last seen
 * @returns Human-readable label like "Online", "Last seen 5 minutes ago", etc.
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
      return "Last seen just now"
    }
    if (diffMin === 1) {
      return "Last seen 1 minute ago"
    }
    if (diffMin < 60) {
      return `Last seen ${diffMin} minutes ago`
    }

    const diffHours = Math.floor(diffMin / 60)
    if (diffHours === 1) {
      return "Last seen 1 hour ago"
    }
    if (diffHours < 24) {
      return `Last seen ${diffHours} hours ago`
    }

    const diffDays = Math.floor(diffHours / 24)
    if (diffDays === 1) {
      return "Last seen 1 day ago"
    }
    if (diffDays < 7) {
      return `Last seen ${diffDays} days ago`
    }

    const diffWeeks = Math.floor(diffDays / 7)
    if (diffWeeks === 1) {
      return "Last seen 1 week ago"
    }
    if (diffWeeks < 4) {
      return `Last seen ${diffWeeks} weeks ago`
    }

    const diffMonths = Math.floor(diffDays / 30)
    if (diffMonths === 1) {
      return "Last seen 1 month ago"
    }
    if (diffMonths < 12) {
      return `Last seen ${diffMonths} months ago`
    }

    return "Last seen long time ago"
  } catch (error) {
    console.error("[getLastSeenLabel] Error parsing date:", error)
    return "Offline"
  }
}

