// src/ws/useChatSocket.ts

import { useEffect, useRef } from "react"
import { buildWsUrl } from "@/app/lib/wsUrl"

type Options = {
  chatId: number
  telegramId: number
  onMessage: (data: any) => void
  onStatus?: (status: "connecting" | "open" | "closed" | "reconnecting") => void
}

export function useChatSocket({ chatId, telegramId, onMessage, onStatus }: Options) {
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(0)
  const aliveRef = useRef(true)
  const pingTimer = useRef<any>(null)
  const offlineQueue = useRef<any[]>([]) // yuborilmagan local eventlar

  useEffect(() => {
    if (!chatId || !telegramId) return
    aliveRef.current = true

    // WebSocket path - backend exposes /api/ws/chat via wsBaseUrl (/api prefix already included)
    const url = buildWsUrl(`/ws/chat?chat_id=${chatId}&telegram_id=${telegramId}`)
    if (!url) {
      console.error("[useChatSocket] Failed to build WebSocket URL")
      return
    }
    
    console.log(`[useChatSocket] Connecting to WebSocket:`, {
      chatId,
      telegramId,
      url
    })

    const connect = () => {
      onStatus?.("connecting")
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        onStatus?.("open")
        retryRef.current = 0

        // Heartbeat
        const ping = () => {
          if (!aliveRef.current) return
          if (ws.readyState === WebSocket.OPEN) {
            try {
              ws.send("ping")
            } catch {}
            pingTimer.current = setTimeout(ping, 15000)
          }
        }
        ping()

        // Offline queue'ni flush
        while (offlineQueue.current.length && ws.readyState === WebSocket.OPEN) {
          const msg = offlineQueue.current.shift()
          try {
            ws.send(msg)
          } catch {}
        }
      }

      ws.onmessage = (evt) => {
        if (evt.data === "pong") {
          // Heartbeat response
          return
        }
        try {
          const parsed = typeof evt.data === "string" ? JSON.parse(evt.data) : evt.data
          if (parsed?.event === "message.new") {
            onMessage(parsed.payload)
            return
          }
          if (parsed?.type === "chat.message") {
            onMessage(parsed.message)
          }
        } catch (error) {
          console.error("[useChatSocket] Failed to parse WebSocket payload:", error)
        }
      }

      ws.onclose = () => {
        onStatus?.("closed")
        if (!aliveRef.current) return
        // Reconnect — exponential backoff (<= 15s)
        const delay = Math.min(1000 * Math.pow(2, retryRef.current++), 15000)
        setTimeout(() => {
          onStatus?.("reconnecting")
          connect()
        }, delay)
      }

      ws.onerror = () => {
        try {
          ws.close()
        } catch {}
      }
    }

    connect()

    return () => {
      aliveRef.current = false
      if (pingTimer.current) clearTimeout(pingTimer.current)
      try {
        wsRef.current?.close()
      } catch {}
    }
  }, [chatId, telegramId, onMessage, onStatus])

  // Agar frontdan WS orqali event yuborish kerak bo'lsa:
  const send = (obj: any) => {
    const str = typeof obj === "string" ? obj : JSON.stringify(obj)
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(str)
    } else {
      // oflayn — keyin yuboramiz
      offlineQueue.current.push(str)
    }
  }

  return { send }
}

