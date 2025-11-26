const NGROK_HOST_HINTS = ["ngrok-free.app", "ngrok-free.dev", "ngrok.app", "ngrok.io"]

function hasHostname(hostname?: string | null): hostname is string {
  return typeof hostname === "string" && hostname.length > 0
}

function includesNgrokHint(hostname: string): boolean {
  return NGROK_HOST_HINTS.some((hint) => hostname.includes(hint))
}

/**
 * Normalize API/WS base URL by trimming whitespace and trailing slash.
 * Keeps relative paths (e.g. "/api") intact.
 */
export function normalizeBaseUrl(url?: string | null): string {
  if (!url) {
    return ""
  }
  const trimmed = url.trim()
  if (trimmed === "/") {
    return "/"
  }
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed
}

/**
 * Detect whether current environment runs behind an ngrok tunnel.
 * Checks window.location hostname when available, otherwise falls back to env hints.
 */
export function isNgrokEnvironment(hostnameOverride?: string | null): boolean {
  if (hasHostname(hostnameOverride) && includesNgrokHint(hostnameOverride)) {
    return true
  }

  if (typeof window !== "undefined" && hasHostname(window.location.hostname)) {
    if (includesNgrokHint(window.location.hostname)) {
      return true
    }
  }

  const envHints = [
    process.env.NEXT_PUBLIC_NGROK_HOST,
    process.env.NEXT_PUBLIC_APP_DOMAIN,
    process.env.NGROK_HOST,
  ]

  if (envHints.some((hint) => hasHostname(hint) && includesNgrokHint(hint!))) {
    return true
  }

  return process.env.NEXT_PUBLIC_USE_NGROK === "1" || process.env.USE_NGROK === "1"
}

/**
 * Build headers required to bypass ngrok browser warning interstitial.
 */
export function buildNgrokBypassHeaders(hostnameOverride?: string | null): Record<string, string> {
  if (!isNgrokEnvironment(hostnameOverride)) {
    return {}
  }
  const headerValue = process.env.NEXT_PUBLIC_NGROK_SKIP_VALUE || process.env.NGROK_SKIP_VALUE || "1"
  return { "ngrok-skip-browser-warning": headerValue }
}

