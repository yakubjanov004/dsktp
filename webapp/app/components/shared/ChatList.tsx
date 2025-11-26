"use client"

import { useState, useEffect } from "react"
import { type Message } from "../../lib/api"
import { useChat } from "../../context/ChatContext"

type ChatListUser = {
  id: number
  full_name?: string
  role?: string
  status?: string
}

type ChatListChat = {
  id: string
  clientId: string
  operatorId: string | null
  status: "active" | "inactive" | "closed"
  createdAt?: Date | string
  lastActivity: Date | string
  lastMessage: (Message & { text?: string }) | null
  clientName?: string
  operatorName?: string | null
}

interface ChatListProps {
  chats: ChatListChat[]
  users: ChatListUser[]
  onChatSelect: (chatId: string) => void
  isDarkMode: boolean
  currentUserId: number | string
  showOpenButton?: boolean
  groupByDate?: boolean
  isLoading?: boolean
  emptyMessage?: string
}

export default function ChatList({
  chats,
  users,
  onChatSelect,
  isDarkMode,
  currentUserId,
  showOpenButton = false,
  groupByDate = true,
  isLoading = false,
  emptyMessage = "Chatlar topilmadi",
}: ChatListProps) {
  const { typingUsers, unreadCounts, onlineUsers } = useChat()
  
  // State to force re-render every 30 seconds for time updates
  const [, setTick] = useState(0)
  
  // Update every 30 seconds to keep time labels accurate
  useEffect(() => {
    const interval = setInterval(() => {
      setTick(prev => prev + 1)
    }, 30000) // 30 seconds
    
    return () => clearInterval(interval)
  }, [])

  const formatLastActivity = (timestamp: Date | string) => {
    const now = new Date()
    const activity = new Date(timestamp)
    const diffInMinutes = Math.floor((now.getTime() - activity.getTime()) / (1000 * 60))

    if (diffInMinutes < 1) return "Hozirgina"
    if (diffInMinutes < 60) return `${diffInMinutes}min oldin`
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}soat oldin`
    return activity.toLocaleDateString("uz-UZ")
  }

  // Oxirgi operator nomini topish
  const getOperatorName = (chat: ChatListChat) => {
    if (!chat.operatorId) return "" // Agar operator_id yo'q bo'lsa, bo'sh qaytaradi
    const operatorId = typeof chat.operatorId === "string" ? parseInt(chat.operatorId, 10) : chat.operatorId
    const operator = users.find((u) => u.id === operatorId)
    return operator?.full_name || ""
  }

  const getOtherUserId = (chat: ChatListChat) => {
    const currentUserIdNum =
      typeof currentUserId === "string" ? parseInt(currentUserId, 10) : (currentUserId as number)
    const chatClientId = parseInt(chat.clientId, 10)
    return currentUserIdNum === chatClientId
      ? chat.operatorId
        ? parseInt(chat.operatorId, 10)
        : null
      : chatClientId
  }

  const resolveDate = (value: Date | string) => (value instanceof Date ? value : new Date(value))

  const getDateLabel = (date: Date) => {
    const now = new Date()
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const startOfYesterday = new Date(startOfToday)
    startOfYesterday.setDate(startOfYesterday.getDate() - 1)

    if (date >= startOfToday) return "Bugun"
    if (date >= startOfYesterday) return "Kecha"
    return date.toLocaleDateString("uz-UZ", {
      day: "numeric",
      month: "long",
      year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
    })
  }

  const sortedChats = [...chats].sort(
    (a, b) => resolveDate(b.lastActivity).getTime() - resolveDate(a.lastActivity).getTime()
  )

  const groupedChats: { label: string | null; items: ChatListChat[] }[] = groupByDate
    ? sortedChats.reduce<{ label: string | null; items: ChatListChat[] }[]>((acc, chat) => {
        const label = getDateLabel(resolveDate(chat.lastActivity))
        const existing = acc.find((group) => group.label === label)
        if (existing) {
          existing.items.push(chat)
        } else {
          acc.push({ label, items: [chat] })
        }
        return acc
      }, [])
    : [{ label: null, items: sortedChats }]

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-4 pb-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="p-3 sm:p-4 rounded-xl bg-white border border-blue-200 animate-pulse">
            <div className="flex items-start space-x-3 sm:space-x-4">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-gray-300"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-gray-300 rounded w-3/4"></div>
                <div className="h-3 bg-gray-300 rounded w-1/2"></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  // Empty state
  if (!chats || chats.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-4">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <p className="text-blue-600 text-center font-medium mb-2">{emptyMessage}</p>
        <p className="text-blue-500 text-sm text-center">Yangi chatlar bu yerda ko'rinadi</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-4">
      {groupedChats.map((group, groupIndex) => (
        <div key={group.label ?? `group-${groupIndex}`}>
          {group.label && (
            <div
              className={`text-xs font-semibold uppercase tracking-wide mb-3 ${
                isDarkMode ? "text-gray-300" : "text-blue-800"
              }`}
            >
              {group.label}
            </div>
          )}
          <div className="space-y-4">
            {group.items.map((chat, index) => {
        const otherUserId = getOtherUserId(chat)
        const otherUser = otherUserId ? users.find((u) => u.id === otherUserId) : null
        const currentUserIdNum = typeof currentUserId === "string" ? parseInt(currentUserId) : currentUserId
        const isTyping = typingUsers[chat.id] || typingUsers[`${chat.id}-${otherUserId}`] || false
        const unreadCount = unreadCounts[`${chat.id}-${currentUserIdNum}`] || 0
        const isOnline = otherUserId ? onlineUsers.has(otherUserId) : false

        return (
          <div
            key={chat.id}
            onClick={() => onChatSelect(chat.id)}
            className="p-3 sm:p-4 rounded-xl cursor-pointer transition-all duration-200 transform active:scale-[0.98] hover:scale-[1.02] hover:shadow-lg bg-white hover:bg-blue-50 active:bg-blue-100 border border-blue-200 animate-slide-in touch-manipulation"
            style={{ animationDelay: `${index * 100}ms`, touchAction: "manipulation" }}
          >
            <div className="flex items-start space-x-3 sm:space-x-4">
              {/* Avatar */}
              <div className="relative flex-shrink-0">
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-sm sm:text-base">
                  {otherUser?.full_name?.[0]?.toUpperCase() || "?"}
                </div>
                <div
                  className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-white ${
                    isOnline ? "bg-green-500" : "bg-blue-200"
                  }`}
                ></div>
              </div>

              {/* Chat Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center space-x-2 min-w-0 flex-1">
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold truncate text-blue-900 text-sm sm:text-base">
                        {otherUser?.full_name || chat.operatorName || chat.clientName || "Noma'lum foydalanuvchi"}
                      </h3>
                      {/* Oxirgi operator nomi - operator_id dan olinadi */}
                      {getOperatorName(chat) && (
                        <p className="text-xs text-blue-600 truncate">
                          {getOperatorName(chat)}
                        </p>
                      )}
                    </div>
                    {/* Status Checkmark - Active/Inactive ko'rsatadi */}
                    {chat.status === "active" ? (
                      <div className="flex-shrink-0 w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-green-100 border-2 border-green-300 flex items-center justify-center">
                        <svg className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </div>
                    ) : chat.status === "inactive" ? (
                      <div className="flex-shrink-0 w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-red-100 border-2 border-red-300 flex items-center justify-center">
                        <svg className="w-3 h-3 sm:w-3.5 sm:h-3.5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </div>
                    ) : null}
                  </div>
                  <div className="flex items-center space-x-2 flex-shrink-0">
                    {unreadCount > 0 && (
                      <span className="px-2 py-0.5 bg-blue-500 text-white text-xs rounded-full font-medium">
                        {unreadCount}
                      </span>
                    )}
                    <span className="text-xs text-blue-600 whitespace-nowrap">
                      {formatLastActivity(chat.lastActivity)}
                    </span>
                  </div>
                </div>


                <div className="flex items-center justify-between">
                  {isTyping ? (
                    <div className="text-sm italic text-blue-600">
                      <span className="inline-flex space-x-1">
                        <span>Yozmoqda</span>
                        <span className="flex space-x-1">
                          <span className="w-1 h-1 bg-current rounded-full animate-bounce"></span>
                          <span
                            className="w-1 h-1 bg-current rounded-full animate-bounce"
                            style={{ animationDelay: "0.1s" }}
                          ></span>
                          <span
                            className="w-1 h-1 bg-current rounded-full animate-bounce"
                            style={{ animationDelay: "0.2s" }}
                          ></span>
                        </span>
                      </span>
                    </div>
                  ) : (
                    <p className="text-sm truncate text-blue-600">
                      {chat.lastMessage ? (
                        <>
                          {(typeof chat.lastMessage.sender_id === "string"
                            ? parseInt(chat.lastMessage.sender_id, 10)
                            : chat.lastMessage.sender_id) === currentUserIdNum && "Siz: "}
                          {chat.lastMessage.message_text || chat.lastMessage.text || "Media fayl"}
                        </>
                      ) : (
                        "Hali xabar yo'q"
                      )}
                    </p>
                  )}

                  {/* Status Badge */}
                  <div className="flex items-center space-x-2">
                    {chat.status === "active" ? (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200">
                        ✅ Faol
                      </span>
                    ) : chat.status === "closed" ? (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
                        🔒 Yopilgan
                      </span>
                    ) : null}
                    {showOpenButton && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onChatSelect(chat.id)
                        }}
                        className="px-3 py-1 rounded-lg text-xs font-medium transition-colors bg-blue-500 text-white hover:bg-blue-600"
                      >
                        Ochish
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
