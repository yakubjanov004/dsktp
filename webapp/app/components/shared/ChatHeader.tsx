"use client"

import { useState, useEffect } from "react"
import { useChat } from "../../context/ChatContext"
import { getLastSeenLabel } from "../../lib/presence"
import type { DatabaseUser, Chat } from "../../lib/api"

interface ChatHeaderUser {
  id?: number
  full_name?: string | null
  name?: string | null
  is_online?: boolean
  last_seen_at?: string | null
}

interface ChatHeaderChat {
  createdAt: string | Date
  lastActivity?: string | Date
  lastClientActivityAt?: string | null
  status: "active" | "inactive"
  operatorName?: string | null
  clientName?: string | null
}

interface ChatHeaderProps {
  user?: ChatHeaderUser | DatabaseUser | null
  chat: ChatHeaderChat
  onBack?: () => void
  onClose?: () => void
  onCloseChat?: () => void
  isDarkMode?: boolean
  isReadOnly?: boolean
  isCompact?: boolean
  wsStatus?: "connected" | "reconnecting" | "disconnected"
}

export default function ChatHeader({
  user,
  chat,
  onBack,
  onClose,
  onCloseChat,
  isDarkMode,
  isReadOnly,
  isCompact,
  wsStatus = "connected"
}: ChatHeaderProps) {
  const { onlineUsers } = useChat()
  
  // State to force re-render every minute for "last seen" update
  const [, setTick] = useState(0)
  
  // Update every 30 seconds to keep "last seen" accurate
  useEffect(() => {
    const interval = setInterval(() => {
      setTick(prev => prev + 1)
    }, 30000) // 30 seconds
    
    return () => clearInterval(interval)
  }, [])
  
  // Determine if user is online
  // Priority: 1) WebSocket onlineUsers (real-time), 2) user.is_online from database, 3) false
  // WebSocket status should take priority as it's real-time
  const isUserOnline = user?.id 
    ? (onlineUsers.has(user.id) || user?.is_online === true)
    : false
  
  // Get last seen label
  // Priority for timestamp:
  // 1. lastClientActivityAt (chat-specific activity)
  // 2. user.last_seen_at (user's global online status)
  // 3. chat.lastActivity (fallback to chat's last activity)
  const getLastSeenTimestamp = (): string | null => {
    if (chat.lastClientActivityAt) {
      return chat.lastClientActivityAt
    }
    if (user?.last_seen_at) {
      return user.last_seen_at
    }
    // Fallback: use chat's lastActivity as approximate "last seen"
    if (chat.lastActivity) {
      const lastActivity = chat.lastActivity instanceof Date 
        ? chat.lastActivity.toISOString() 
        : chat.lastActivity
      return lastActivity
    }
    return null
  }
  
  const lastSeenAt = getLastSeenTimestamp()
  
  // If we have a timestamp and user is offline, show "X daqiqa oldin"
  // Otherwise, if online show "Online"
  const lastSeenLabel = isUserOnline 
    ? "🟢 Online" 
    : lastSeenAt 
      ? getLastSeenLabel(false, lastSeenAt)
      : "Offline"

  return (
    <div className={`px-2 xs:px-2.5 sm:px-3 md:px-4 py-2 xs:py-2.5 sm:py-2.5 md:py-3 flex items-center justify-between bg-white flex-shrink-0 w-full ${isCompact ? "px-1.5 xs:px-2 sm:px-2.5 md:px-3 py-1.5 xs:py-2" : ""}`}>
      <div className="flex items-center space-x-1.5 xs:space-x-2 sm:space-x-2.5 md:space-x-3 min-w-0 flex-1">
        {/* Back Button - Always visible */}
        {onBack && (
          <button
            onClick={onBack}
            className="p-1.5 xs:p-1.5 sm:p-2 rounded-lg transition-colors flex-shrink-0 hover:bg-blue-50 active:bg-blue-100 text-blue-600 touch-manipulation min-w-[44px] min-h-[44px] flex items-center justify-center"
            title="Orqaga"
          >
            <svg className="w-5 h-5 xs:w-5 xs:h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        )}

        {/* User Info */}
        <div className="flex items-center space-x-1.5 xs:space-x-2 sm:space-x-2.5 md:space-x-3 min-w-0 flex-1">
          <div className="relative flex-shrink-0">
            <div className={`${isCompact ? "w-7 h-7 xs:w-8 xs:h-8" : "w-8 h-8 xs:w-9 xs:h-9 sm:w-10 sm:h-10 md:w-11 md:h-11"} rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-xs xs:text-xs sm:text-sm md:text-base`}>
              {(user?.full_name || (user as ChatHeaderUser)?.name)?.[0]?.toUpperCase() || "?"}
            </div>
            {/* Online/Offline indicator */}
            <div
              className={`absolute -bottom-0.5 xs:-bottom-1 -right-0.5 xs:-right-1 w-2.5 h-2.5 xs:w-3 xs:h-3 rounded-full border-2 border-white ${
                isUserOnline ? "bg-green-500" : "bg-gray-400"
              }`}
            ></div>
          </div>
          <div className="min-w-0 flex-1">
            <h3 className={`font-semibold truncate ${isCompact ? "text-xs xs:text-xs sm:text-sm" : "text-xs xs:text-sm sm:text-sm md:text-base lg:text-base"} text-blue-900`}>
              {(user?.full_name || (user as ChatHeaderUser)?.name) || chat.operatorName || chat.clientName || "Noma'lum foydalanuvchi"}
            </h3>
            {!isCompact && (
              <div className="flex items-center gap-1.5">
                <p className={`text-[10px] xs:text-xs sm:text-xs md:text-xs truncate ${
                  isUserOnline ? "text-green-600 font-medium" : "text-gray-500"
                }`}>
                  {lastSeenLabel}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center space-x-1 xs:space-x-1.5 sm:space-x-2 flex-shrink-0">
        {/* WebSocket Status Indicator */}
        {wsStatus === "reconnecting" && (
          <div className="flex items-center space-x-1 px-2 py-1 rounded-full bg-yellow-100 border border-yellow-200">
            <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></div>
            <span className="text-[10px] text-yellow-700 font-medium hidden sm:inline">Qayta ulanmoqda...</span>
          </div>
        )}
        
        {/* Status Badge */}
        <span
          className={`px-1.5 xs:px-2 sm:px-2 md:px-2.5 py-0.5 xs:py-1 rounded-full text-[10px] xs:text-xs sm:text-xs font-medium whitespace-nowrap ${
            chat.status === "active"
              ? "bg-green-100 text-green-800 border border-green-200"
              : "bg-gray-100 text-gray-700 border border-gray-200"
          }`}
        >
          <span className="hidden xs:inline sm:inline">{chat.status === "active" ? "✅ Faol" : "⏸️ Nofaol"}</span>
          <span className="xs:hidden">{chat.status === "active" ? "✅" : "⏸️"}</span>
        </span>
      </div>
    </div>
  )
}
