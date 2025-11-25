/**
 * WebSocket URL builder utilities
 * Provides unified WebSocket URL construction from runtime configuration
 * 
 * Telegram iframe fix: Uses runtime config from backend instead of env vars
 * because environment variables don't work in Telegram Web Apps
 */

// This will be set dynamically from getRuntimeConfig()
let runtimeWsBaseUrl: string | null = null

/**
 * Set the runtime WebSocket base URL from backend config
 * Call this once on app startup with getRuntimeConfig()
 */
export function setRuntimeWsBaseUrl(wsBaseUrl: string): void {
  runtimeWsBaseUrl = wsBaseUrl
  console.log("[wsUrl] Runtime WS base URL configured:", wsBaseUrl)
}

/**
 * Converts HTTP/HTTPS URL to WebSocket/WSS URL
 * @param url - HTTP or HTTPS URL (e.g., "https://webapp.darrov.uz" or "http://localhost:3000")
 * @returns WebSocket URL (e.g., "wss://webapp.darrov.uz" or "ws://localhost:3000")
 */
export function httpToWs(url: string): string {
  if (!url) return ""
  
  try {
    const u = new URL(url)
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:"
    return u.toString().replace(/\/$/, "") // Remove trailing slash
  } catch {
    // If URL parsing fails, try simple string replacement
    if (url.startsWith("https://")) {
      return url.replace("https://", "wss://").replace(/\/$/, "")
    }
    if (url.startsWith("http://")) {
      return url.replace("http://", "ws://").replace(/\/$/, "")
    }
    return url
  }
}

/**
 * Builds WebSocket URL with runtime configuration
 * 
 * IMPORTANT: WebSocket URL must match the backend's actual WebSocket endpoint
 * The backend returns wsBaseUrl in /config, which is the proper WebSocket origin
 * 
 * Priority:
 * 1. Runtime WS base URL (set from backend /config endpoint) - BEST
 * 2. NEXT_PUBLIC_WS_URL environment variable (local dev fallback)
 * 
 * @param path - WebSocket endpoint path (e.g., "/ws/chat?chat_id=123")
 * @returns Full WebSocket URL
 */
export function buildWsUrl(path: string): string {
  // Ensure path starts with /
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  
  // 1) Use runtime WS base URL (set from backend config) - THIS IS THE CORRECT WAY
  if (runtimeWsBaseUrl) {
    const baseUrl = runtimeWsBaseUrl.replace(/\/$/, "")
    const fullUrl = `${baseUrl}${normalizedPath}`
    console.log("[buildWsUrl] Using runtime WS config from backend:", {
      wsBase: baseUrl,
      path: normalizedPath,
      fullUrl: fullUrl
    })
    return fullUrl
  }
  
  // 2) Environment fallback (useful for local development)
  const envWsBase = process.env.NEXT_PUBLIC_WS_URL?.replace(/\/$/, "")
  if (envWsBase) {
    const fallbackUrl = `${envWsBase}${normalizedPath}`
    console.warn("[buildWsUrl] Runtime WS config missing, falling back to NEXT_PUBLIC_WS_URL:", {
      envWsBase,
      url: fallbackUrl,
    })
    return fallbackUrl
  }
  
  const errorMessage = "[buildWsUrl] No WebSocket URL available! Call fetchRuntimeConfig() before connecting."
  console.error(errorMessage, { path: normalizedPath })
  throw new Error(errorMessage)
}


