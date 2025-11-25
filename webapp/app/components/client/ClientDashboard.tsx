"use client"

import { useState, useEffect, useRef } from "react"
import { useChat } from "../../context/ChatContext"
import ChatList from "../shared/ChatList"
import ChatWindow from "../shared/ChatWindow"
import ClosedChats from "../shared/ClosedChats"
import type { DatabaseUser } from "../../lib/api"

interface TelegramUser {
  first_name: string
  last_name: string
  username: string
  id: number
}

interface ClientDashboardProps {
  user: TelegramUser
  dbUser?: DatabaseUser | null
  isDarkMode: boolean
  onRoleChange: () => void
}

export default function ClientDashboard({ user, dbUser, isDarkMode, onRoleChange }: ClientDashboardProps) {
  const { chatSessions, users, startNewChat, isLoading, addToActiveChats, loadChatMessages } = useChat()

  // Track loaded chat IDs to prevent duplicate loads
  const loadedChatIdRef = useRef<string | null>(null)

  // Filter chats for this client - faqat 1 ta chat bo'ladi
  // clientId is string, dbUser.id is number - convert both to string for comparison
  // If dbUser is not loaded yet, wait for it (don't filter yet)
  const clientIdToMatch = dbUser?.id ? dbUser.id.toString() : null
  const clientChats = clientIdToMatch 
    ? chatSessions.filter((chat) => {
        // Match by clientId (which is stored as string in ChatSession)
        return chat.clientId === clientIdToMatch
      })
    : [] // Don't show chats until dbUser is loaded
  
  // Debug: log for troubleshooting
  useEffect(() => {
    if (chatSessions.length > 0) {
      console.log('[ClientDashboard] Chat sessions:', chatSessions.map(c => ({ id: c.id, clientId: c.clientId, status: c.status })))
      console.log('[ClientDashboard] Looking for clientId:', clientIdToMatch)
      console.log('[ClientDashboard] dbUser?.id:', dbUser?.id)
      console.log('[ClientDashboard] Filtered chats:', clientChats.map(c => ({ id: c.id, clientId: c.clientId })))
    }
  }, [chatSessions, clientIdToMatch, dbUser?.id, clientChats])
  
  // Client uchun faqat 1 ta chat (yoki 0 ta)
  const clientChat = clientChats.length > 0 ? clientChats[0] : null
  const hasChat = !!clientChat

  const selectedChat = clientChat // Client uchun faqat 1 ta chat

  // Load messages when chat exists - similar to CCO dashboard
  // IMPORTANT: This ensures WebSocket connection is established when chat is loaded
  useEffect(() => {
    if (clientChat?.id) {
      console.log('[ClientDashboard] Loading messages for chat:', clientChat.id, 'dbUser?.id:', dbUser?.id)
      // Load messages for this chat (force reload to get latest messages)
      if (loadedChatIdRef.current !== clientChat.id) {
        loadedChatIdRef.current = clientChat.id
        loadChatMessages(clientChat.id, true)
      }
      // Initialize WebSocket connection - this is critical for real-time updates
      // addToActiveChats will initialize WebSocket if userId is available
      // If userId is not available yet, it will retry when userId becomes available
      if (dbUser?.id) {
        console.log('[ClientDashboard] dbUser.id available, calling addToActiveChats for chat:', clientChat.id)
        addToActiveChats(clientChat.id)
      } else {
        console.warn('[ClientDashboard] dbUser.id not available yet, will retry when dbUser is loaded')
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientChat?.id, dbUser?.id]) // Depend on both chatId and dbUser.id - userId is needed for WebSocket

  // Agar chat yo'q bo'lsa, avtomatik yaratish
  useEffect(() => {
    if (!hasChat && !isLoading && dbUser?.id) {
      // Avtomatik yangi chat yaratish
      startNewChat(dbUser.id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasChat, isLoading, dbUser?.id]) // startNewChat is stable, no need in deps

  return (
    <div className="h-[100dvh] h-screen w-full bg-white safe-area overflow-hidden flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-blue-100 sticky top-0 z-10 shadow-sm safe-area-top flex-shrink-0">
        <div className="w-full max-w-7xl mx-auto px-2 sm:px-3 md:px-4 lg:px-6 py-2 sm:py-2.5 md:py-3">
          <div className="flex items-center justify-between gap-1.5 sm:gap-2 md:gap-3">
            <div className="flex items-center space-x-1.5 sm:space-x-2 md:space-x-3 min-w-0 flex-1">
              <div className="w-8 h-8 xs:w-9 xs:h-9 sm:w-10 sm:h-10 md:w-11 md:h-11 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-xs sm:text-sm md:text-base flex-shrink-0">
                {user.first_name?.[0]?.toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <h1 className="text-sm xs:text-base sm:text-lg md:text-xl font-bold truncate text-blue-900">Yordam chat</h1>
                <p className="text-xs sm:text-sm md:text-base truncate text-blue-700">
                  {dbUser?.full_name || `${user.first_name} ${user.last_name}`.trim()}
                </p>
                {dbUser && (
                  <div className="flex items-center space-x-1.5 sm:space-x-2 mt-0.5 sm:mt-1 flex-wrap">
                    {dbUser.phone && (
                      <span className="text-[10px] xs:text-xs sm:text-sm text-blue-600">
                        📱 {dbUser.phone}
                      </span>
                    )}
                    {dbUser.region && (
                      <span className="text-[10px] xs:text-xs sm:text-sm text-blue-600">
                        📍 {dbUser.region}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center space-x-1 sm:space-x-1.5 md:space-x-2 flex-shrink-0">
              {/* User Info Button */}
              {dbUser && (
                <button
                  onClick={() => {
                    // Show user info modal or dropdown
                    alert(`Foydalanuvchi ma'lumotlari:\n\nIsm: ${dbUser.full_name}\nTelefon: ${dbUser.phone || 'Ko\'rsatilmagan'}\nViloyat: ${dbUser.region || 'Ko\'rsatilmagan'}\nManzil: ${dbUser.address || 'Ko\'rsatilmagan'}\nAbonent ID: ${dbUser.abonent_id || 'Ko\'rsatilmagan'}\nRol: ${dbUser.role}`)
                  }}
                  className="w-8 h-8 xs:w-9 xs:h-9 sm:w-10 sm:h-10 md:w-11 md:h-11 p-0 rounded-lg flex items-center justify-center text-sm sm:text-base md:text-lg transition-colors bg-white border border-blue-200 text-blue-700 hover:bg-blue-50 active:bg-blue-100 touch-manipulation"
                  title="Foydalanuvchi ma'lumotlari"
                >
                  👤
                </button>
              )}
            </div>
          </div>

          {/* No tabs - client has only 1 chat */}
        </div>
      </div>


      {/* Main Content - Fully responsive with proper height calculation */}
      <div className="w-full max-w-7xl mx-auto px-2 sm:px-3 md:px-4 lg:px-6 py-2 sm:py-3 md:py-4 lg:py-6 pb-2 sm:pb-3 md:pb-4 lg:pb-6 safe-area-bottom flex-1 flex flex-col min-h-0 overflow-hidden">
        {clientChat ? (
          <div className="animate-fade-in h-full w-full flex flex-col min-h-0 overflow-hidden">
            <ChatWindow
              chat={clientChat}
              currentUserId={dbUser?.id || user.id}
              onBack={undefined}
              onClose={undefined}
              isDarkMode={false}
              isReadOnly={false}
              isLoadingMessages={isLoading}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center h-full w-full text-center py-8 sm:py-12 md:py-16">
            <div>
              <div className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl mb-3 sm:mb-4">💬</div>
              <h3 className="text-lg sm:text-xl md:text-2xl font-semibold mb-2 text-blue-900">Chat yaratilmoqda...</h3>
              <p className="text-sm sm:text-base md:text-lg text-blue-700">Iltimos, kuting</p>
            </div>
          </div>
        )}
      </div>

    </div>
  )
}
