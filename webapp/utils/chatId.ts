export function normalizeChatId(value: string | number | null | undefined): string | null {
  if (value === null || typeof value === "undefined") {
    return null
  }

  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toString()
  }

  if (typeof value !== "string") {
    return null
  }

  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }

  const match = trimmed.match(/\d+/)
  if (match && match[0]) {
    return match[0]
  }

  return /^\d+$/.test(trimmed) ? trimmed : null
}

export function normalizeChatIdNumber(value: string | number | null | undefined): number | null {
  const normalized = normalizeChatId(value)
  if (!normalized) {
    return null
  }

  const parsed = Number(normalized)
  return Number.isNaN(parsed) ? null : parsed
}

