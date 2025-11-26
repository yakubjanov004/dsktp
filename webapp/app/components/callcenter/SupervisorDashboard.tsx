"use client"

import { useState, useEffect, useMemo, useCallback } from "react"
import { useChat } from "../../context/ChatContext"
import ChatWindow from "../shared/ChatWindow"
import ChatList from "../shared/ChatList"
import { assignChat, type DatabaseUser } from "../../lib/api"
import { normalizeChatId } from "@/utils/chatId"

interface TelegramUser {
  first_name: string
  last_name: string
  username: string
  id: number
}

interface SupervisorDashboardProps {
  user: TelegramUser
  dbUser?: DatabaseUser | null
  isDarkMode: boolean
}

export default function SupervisorDashboard({ user, dbUser, isDarkMode }: SupervisorDashboardProps) {
  const { 
    chatSessions,
    staffChats,
    users, 
    loadChatMessages, 
    refreshChats,
    loadChats,
    loadInbox,
    loadActiveChats,
    loadActiveChatStats,
    activeChatStats,
    isLoading,
    onlineUsers,
    loadStaffChats,
    startStaffChat,
    sendStaffMessage,
    loadStaffChatMessages,
    setOnNewMessage,
    addToActiveChats,
  } = useChat()
  const [activeView, setActiveView] = useState("new")
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null)
  const [showAssignModal, setShowAssignModal] = useState(false)
  const [chatToAssign, setChatToAssign] = useState<string | null>(null)
  const [selectedOperatorId, setSelectedOperatorId] = useState<number | null>(null)
  const [hasLoadedInitial, setHasLoadedInitial] = useState(false)
  const [showNewStaffChatModal, setShowNewStaffChatModal] = useState(false)

  const selectChat = useCallback((rawChatId: string) => {
    const normalized = normalizeChatId(rawChatId)
    if (!normalized) {
      console.warn("[SupervisorDashboard] Invalid chatId received", { rawChatId })
      return
    }
    setSelectedChatId(normalized)
  }, [])

  // Yangi chatlar = faqat client yozganlari (operatorga yuborilmagan)
  // Agar operator_id yo'q bo'lsa va status active bo'lsa, bu yangi chat
  const newChats = chatSessions.filter((chat) => {
    return !chat.operatorId && chat.status === "active"
  })

  // Faol chatlar = operatorga yuborilgan va active status
  // Agar operator_id bor bo'lsa va status active bo'lsa, bu faol chat
  const activeChats = chatSessions.filter((chat) => {
    return chat.status === "active" && !!chat.operatorId
  })

  // Chat tarixi = barcha chatlar (hamma xammasi)
  const allChats = chatSessions

  // Get operators
  const operators = users.filter((u) => u.role === "callcenter_operator")

  // Get operator active chat counts from stats
  const getOperatorActiveChatCount = (operatorId: number) => {
    if (!activeChatStats) {
      return activeChats.filter((chat) => chat.operatorId === operatorId.toString()).length
    }
    const operatorStat = activeChatStats.operator_counts.find(
      (op) => op.operator_id === operatorId
    )
    return operatorStat?.cnt || 0
  }

  // Get inbox count from stats
  const inboxCount = activeChatStats?.inbox_count || newChats.length

  // Load initial data on mount - only once
  useEffect(() => {
    if (hasLoadedInitial || isLoading) return
    
    setHasLoadedInitial(true)
    
    // 1. Load inbox (new chats - active, operator_id IS NULL)
    loadInbox(20)
    
    // 2. Load assigned active chats (active, operator_id IS NOT NULL)
    loadActiveChats(20)
    
    // 3. Load all chats for history (barcha chatlar, eng so'nggi aktivlik bo'yicha)
    loadChats()
    
    // 4. Load active chat stats (includes inbox_count and operator_counts)
    loadActiveChatStats()
    
    // 5. Load staff chats
    loadStaffChats()
    
    // 6. Load users (operators) - this is already loaded by ChatContext
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasLoadedInitial, isLoading]) // loadInbox, loadActiveChats, loadChats, loadActiveChatStats, loadStaffChats are stable

  // Auto-open chat window when new message arrives
  useEffect(() => {
    if (!setOnNewMessage) return
    
    setOnNewMessage((chatId: string) => {
      if (selectedChatId) {
        return
      }
      const normalized = normalizeChatId(chatId)
      if (!normalized) {
        console.warn("[SupervisorDashboard] setOnNewMessage: Invalid chatId", { chatId })
        return
      }
      const chat = chatSessions.find((c) => c.id === normalized)
      if (chat && (!chat.operatorId || chat.status === "active")) {
        selectChat(normalized)
      }
    })
    
    return () => {
      if (setOnNewMessage) {
        setOnNewMessage(null as any)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChatId, setOnNewMessage])

  // Track loading state for selected chat
  const [isLoadingSelectedChat, setIsLoadingSelectedChat] = useState(false)

  // Find selected chat from both chatSessions and staffChats
  // Use useMemo to ensure selectedChat updates when chatSessions or staffChats change
  const selectedChat = useMemo(() => {
    if (!selectedChatId) return null
    const chat = chatSessions.find((chat) => chat.id === selectedChatId) || staffChats.find((chat) => chat.id === selectedChatId)
    console.log('[SupervisorDashboard] 🔍 selectedChat updated:', {
      selectedChatId,
      found: !!chat,
      messagesCount: chat?.messages?.length || 0,
      chatSessionsCount: chatSessions.length,
      staffChatsCount: staffChats.length,
      hasMessages: !!(chat?.messages && chat.messages.length > 0),
      chatDetails: chat ? {
        id: chat.id,
        clientId: chat.clientId,
        operatorId: chat.operatorId,
        status: chat.status,
        messagesLength: chat.messages?.length || 0,
        lastMessage: chat.lastMessage ? { id: chat.lastMessage.id, text: chat.lastMessage.message_text?.substring(0, 50) } : null
      } : null
    })
    return chat || null
  }, [selectedChatId, chatSessions, staffChats])
  const isStaffChat = selectedChatId ? staffChats.some((chat) => chat.id === selectedChatId) : false

  // Load messages when chat is selected - loadChatMessages will handle loading chat if needed
  useEffect(() => {
    if (selectedChatId) {
      console.log('[SupervisorDashboard] ⚡ Chat selected:', {
        selectedChatId,
        chatExistsInSessions: chatSessions.some(c => c.id === selectedChatId),
        chatExistsInStaffChats: staffChats.some(c => c.id === selectedChatId),
        chatSessionsCount: chatSessions.length,
        staffChatsCount: staffChats.length
      })
      
      setIsLoadingSelectedChat(true)
      const loadMessages = async () => {
        try {
          if (staffChats.some((chat) => chat.id === selectedChatId)) {
            // Staff chat
            console.log('[SupervisorDashboard] 📨 Loading staff chat messages for:', selectedChatId, {
              staffChatExists: staffChats.some(c => c.id === selectedChatId),
              staffChat: staffChats.find(c => c.id === selectedChatId)
            })
            await loadStaffChatMessages(selectedChatId, true)
            
            // Wait a bit for state to update
            await new Promise(resolve => setTimeout(resolve, 300))
            
            // Verify messages were loaded
            const updatedStaffChat = staffChats.find(c => c.id === selectedChatId)
            console.log('[SupervisorDashboard] ✅ Staff chat messages loaded:', {
              selectedChatId,
              messagesCount: updatedStaffChat?.messages?.length || 0,
              hasMessages: !!(updatedStaffChat?.messages && updatedStaffChat.messages.length > 0),
              chatFound: !!updatedStaffChat
            })
          } else {
            // Regular chat - load all messages with force=true to ensure full chat is loaded
            // This ensures that when supervisor enters a chat, all messages are displayed
            console.log('[SupervisorDashboard] 📨 Loading regular chat messages for:', selectedChatId, {
              chatExists: chatSessions.some(c => c.id === selectedChatId),
              chatInSessions: chatSessions.find(c => c.id === selectedChatId)
            })
            
            // Ensure chat exists in sessions before loading messages
            const chatExists = chatSessions.some(c => c.id === selectedChatId)
            if (!chatExists) {
              console.warn('[SupervisorDashboard] ⚠️ Chat not found in chatSessions, will be created by loadChatMessages')
            }
            
            await loadChatMessages(selectedChatId, true)
            
            // Wait a bit for state to update
            await new Promise(resolve => setTimeout(resolve, 200))
            
            // Add to active chats to ensure WebSocket connection for real-time updates
            addToActiveChats(selectedChatId)
            
            // Wait a bit more for state to fully update
            await new Promise(resolve => setTimeout(resolve, 300))
            
            // Verify messages were loaded by checking chatSessions
            // Note: chatSessions is from context, so we read it directly
            const updatedChat = chatSessions.find(c => c.id === selectedChatId)
            console.log('[SupervisorDashboard] ✅ Messages loaded (state check):', {
              selectedChatId,
              messagesCount: updatedChat?.messages?.length || 0,
              hasMessages: !!(updatedChat?.messages && updatedChat.messages.length > 0),
              chatFound: !!updatedChat
            })
          }
        } catch (error) {
          console.error('[SupervisorDashboard] ❌ Error loading messages:', error)
        } finally {
          // Small delay to ensure state is updated
          setTimeout(() => setIsLoadingSelectedChat(false), 100)
        }
      }
      loadMessages()
    } else {
      setIsLoadingSelectedChat(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChatId]) // Keep dependencies minimal - loadChatMessages, loadStaffChatMessages, addToActiveChats are stable

  const handleAssignChat = (chatId: string) => {
    setChatToAssign(chatId)
    setShowAssignModal(true)
  }

  const handleConfirmAssign = async () => {
    if (!chatToAssign || !selectedOperatorId) return

    const success = await assignChat(parseInt(chatToAssign), selectedOperatorId)
    if (success) {
      // Refresh chats to get updated data
      await refreshChats()
      setShowAssignModal(false)
      setChatToAssign(null)
      setSelectedOperatorId(null)
      // If viewing this chat, go back to list
      if (selectedChatId === chatToAssign) {
        setSelectedChatId(null)
      }
    } else {
      alert("Chatni operatorga yuborishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
    }
  }

  const handleCancelAssign = () => {
    setShowAssignModal(false)
    setChatToAssign(null)
    setSelectedOperatorId(null)
  }

  return (
    <div className="h-[100dvh] h-screen w-full bg-white safe-area overflow-hidden flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-blue-100 sticky top-0 z-10 shadow-sm safe-area-top flex-shrink-0">
        <div className="w-full max-w-7xl mx-auto px-2 sm:px-3 md:px-4 lg:px-6 py-2 sm:py-2.5 md:py-3">
          <div className="flex items-center justify-between gap-1.5 sm:gap-2 md:gap-3">
            <div className="flex items-center space-x-1.5 sm:space-x-2 md:space-x-3 min-w-0 flex-1">
              <div className="w-8 h-8 xs:w-9 xs:h-9 sm:w-10 sm:h-10 md:w-11 md:h-11 rounded-full bg-gradient-to-r from-purple-500 to-pink-600 flex items-center justify-center text-white font-bold text-xs sm:text-sm md:text-base flex-shrink-0">
                👔
              </div>
              <div className="min-w-0 flex-1">
                <h1 className="text-sm xs:text-base sm:text-lg md:text-xl font-bold truncate text-blue-900">Call Center Supervisor</h1>
                <p className="text-xs sm:text-sm md:text-base truncate text-blue-700">
                  {dbUser?.full_name || `${user.first_name} ${user.last_name}`.trim()}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-1 sm:space-x-1.5 md:space-x-2 flex-shrink-0" />
          </div>

          {/* Navigation Tabs */}
          <div className="flex space-x-1.5 sm:space-x-2 mt-2 sm:mt-3 overflow-x-auto pb-1 -mx-2 px-2 sm:-mx-3 sm:px-3 md:mx-0 md:px-0 scrollbar-hide">
            {[
              { id: "new", label: "Yangi chatlar", count: inboxCount, badge: inboxCount > 0 },
              { id: "active", label: "Faol chatlar", count: activeChats.length },
              { id: "closed", label: "Chat tarixi", count: allChats.length },
              { id: "staff", label: "Xodimlar bilan chat", count: staffChats.length },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveView(tab.id)
                  setSelectedChatId(null)
                }}
                className={`px-2.5 sm:px-3 md:px-4 py-1.5 sm:py-2 md:py-2.5 rounded-lg font-medium transition-all duration-200 text-xs sm:text-sm md:text-base whitespace-nowrap touch-manipulation min-h-[44px] flex items-center relative ${
                  activeView === tab.id
                    ? "bg-blue-500 text-white shadow-md"
                    : "bg-white text-blue-700 border border-blue-200 active:bg-blue-50"
                }`}
              >
                {tab.label}
                {tab.count > 0 && (
                  <span
                    className={`ml-2 px-2 py-0.5 rounded-full text-xs ${
                      activeView === tab.id ? "bg-white/30" : "bg-blue-100"
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
                {tab.badge && tab.count > 0 && (
                  <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center text-white text-[10px] font-bold">
                    {tab.count > 99 ? '99+' : tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Assign Chat Modal */}
      {showAssignModal && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 safe-area"
          onClick={handleCancelAssign}
        >
          <div 
            className="w-full max-w-md bg-white rounded-xl shadow-2xl overflow-hidden animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 sm:p-6">
              <h3 className="text-lg sm:text-xl font-bold mb-4 text-blue-900">
                Operatorni tanlang
              </h3>
              
              {operators.length === 0 ? (
                <div className="text-center py-8">
                  <div className="text-4xl mb-4">👥</div>
                  <p className="text-blue-700">Operatorlar topilmadi</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[60vh] overflow-y-auto scrollbar-hide">
                  {operators.map((operator) => {
                    const activeCount = getOperatorActiveChatCount(operator.id)
                    return (
                      <button
                        key={operator.id}
                        onClick={() => setSelectedOperatorId(operator.id)}
                        className={`w-full p-3 sm:p-4 rounded-lg border-2 transition-all duration-200 text-left touch-manipulation min-h-[60px] ${
                          selectedOperatorId === operator.id
                            ? "border-blue-500 bg-blue-50"
                            : "border-blue-200 active:border-blue-300 bg-white"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-3 min-w-0 flex-1">
                            <div className="relative">
                              <div className="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold flex-shrink-0">
                                {operator.full_name?.[0]?.toUpperCase() || "?"}
                              </div>
                              {/* Online/Offline indicator */}
                              <div className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-white ${
                                onlineUsers.has(operator.id) ? "bg-green-500" : "bg-gray-400"
                              }`}></div>
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className={`font-medium text-sm sm:text-base truncate ${
                                selectedOperatorId === operator.id ? "text-blue-900" : "text-blue-700"
                              }`}>
                                {operator.full_name || operator.username || "Noma'lum operator"}
                                {onlineUsers.has(operator.id) && (
                                  <span className="ml-2 text-xs text-green-600">🟢 Onlayn</span>
                                )}
                                {!onlineUsers.has(operator.id) && (
                                  <span className="ml-2 text-xs text-gray-500">⚫ Offlayn</span>
                                )}
                              </div>
                              {operator.phone && (
                                <div className="text-xs text-blue-600 truncate">
                                  📱 {operator.phone}
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center space-x-2 flex-shrink-0">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                              activeCount > 0 
                                ? "bg-green-100 text-green-800" 
                                : "bg-gray-100 text-gray-600"
                            }`}>
                              {activeCount} faol
                            </span>
                            {selectedOperatorId === operator.id && (
                              <span className="text-blue-500 text-lg">✓</span>
                            )}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
              
              <div className="flex space-x-3 mt-6">
                <button
                  onClick={handleConfirmAssign}
                  disabled={!selectedOperatorId || operators.length === 0}
                  className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors text-base touch-manipulation min-h-[44px] flex items-center justify-center ${
                    selectedOperatorId && operators.length > 0
                      ? "bg-blue-500 text-white active:bg-blue-600"
                      : "bg-blue-200 text-blue-400 cursor-not-allowed"
                  }`}
                >
                  Yuborish
                </button>
                <button
                  onClick={handleCancelAssign}
                  className="flex-1 px-4 py-3 rounded-lg font-medium transition-colors text-base bg-white border border-blue-200 text-blue-700 active:bg-blue-50 touch-manipulation min-h-[44px] flex items-center justify-center"
                >
                  Bekor qilish
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="w-full max-w-7xl mx-auto px-2 sm:px-3 md:px-4 lg:px-6 py-2 sm:py-3 md:py-4 lg:py-6 pb-2 sm:pb-3 md:pb-4 lg:pb-6 safe-area-bottom flex-1 flex flex-col min-h-0 overflow-hidden">
        {selectedChat ? (
          <div className="animate-fade-in h-full flex flex-col min-h-0 overflow-hidden">
            {selectedChat ? (
              <ChatWindow
                chat={selectedChat}
                currentUserId={dbUser?.id || user.id}
                onBack={() => setSelectedChatId(null)}
                onClose={() => setSelectedChatId(null)}
                isDarkMode={false}
                isReadOnly={!isStaffChat}
                isStaffChat={isStaffChat}
                isLoadingMessages={isLoadingSelectedChat}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="text-6xl mb-4">⏳</div>
                  <h3 className="text-xl font-semibold mb-2 text-blue-900">Chat yuklanmoqda...</h3>
                  <p className="text-base text-blue-700">Iltimos, kuting</p>
                  <div className="mt-4 text-sm text-blue-600">
                    Chat ID: {selectedChatId}
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="animate-slide-in h-full flex flex-col min-h-0 overflow-hidden">
            {activeView === "new" ? (
              <div className="h-full flex flex-col min-h-0">
                <h2 className="text-base sm:text-lg md:text-xl font-bold mb-3 sm:mb-4 md:mb-6 text-blue-900 flex-shrink-0 px-1">
                  Yangi chatlar (Client yozganlari)
                </h2>
                {newChats.length === 0 ? (
                  <div className="text-center py-12 flex-shrink-0">
                    <div className="text-6xl mb-4">💬</div>
                    <h3 className="text-xl font-semibold mb-2 text-blue-900">Yangi chatlar yo'q</h3>
                    <p className="text-base text-blue-700">Client yozgan yangi chatlar bu yerda ko'rinadi.</p>
                  </div>
                ) : (
                  <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0 scrollbar-hide" style={{
                    WebkitOverflowScrolling: "touch",
                    overscrollBehavior: "contain",
                    overscrollBehaviorY: "contain",
                    scrollPaddingTop: "1rem",
                    scrollPaddingBottom: "1rem",
                    touchAction: "pan-y",
                  }}>
                    <div className="space-y-3 sm:space-y-4 pb-4">
                      {newChats.map((chat, index) => {
                        const client = users.find((u) => u.id === parseInt(chat.clientId))
                        return (
                          <div
                            key={chat.id}
                            className="p-3 sm:p-4 rounded-xl bg-white hover:bg-blue-50 active:bg-blue-100 border border-blue-200 animate-slide-in touch-manipulation"
                            style={{ animationDelay: `${index * 100}ms`, touchAction: "manipulation" }}
                          >
                            <div className="flex items-start space-x-3 sm:space-x-4">
                              <div className="relative flex-shrink-0">
                                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-sm sm:text-base">
                                  {client?.full_name?.[0]?.toUpperCase() || "?"}
                                </div>
                                <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-red-500 border-2 border-white"></div>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between mb-1">
                                  <h3 className="font-semibold truncate text-blue-900 text-sm sm:text-base">
                                    {client?.full_name || chat.clientName || "Noma'lum mijoz"}
                                  </h3>
                                </div>
                                <div className="flex items-center justify-between">
                                  <span className="text-xs text-blue-600">
                                    {new Date(chat.createdAt).toLocaleString("uz-UZ", {
                                      day: "numeric",
                                      month: "short",
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    })}
                                  </span>
                                  <div className="flex items-center space-x-2">
                                    <button
                                      onClick={() => selectChat(chat.id)}
                                      className="px-2.5 sm:px-3 py-1.5 sm:py-2 rounded-lg text-xs font-medium transition-colors bg-blue-100 text-blue-700 hover:bg-blue-200 active:bg-blue-300 touch-manipulation min-h-[44px]"
                                    >
                                      Ko'rish
                                    </button>
                                    <button
                                      onClick={() => handleAssignChat(chat.id)}
                                      className="px-2.5 sm:px-3 py-1.5 sm:py-2 rounded-lg text-xs font-medium transition-colors bg-blue-500 text-white hover:bg-blue-600 active:bg-blue-700 touch-manipulation min-h-[44px]"
                                    >
                                      Yuborish
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : activeView === "active" ? (
              <div className="h-full flex flex-col min-h-0">
                <h2 className="text-base sm:text-lg md:text-xl font-bold mb-3 sm:mb-4 md:mb-6 text-blue-900 flex-shrink-0 px-1">
                  Faol chatlar
                </h2>
                {activeChats.length === 0 ? (
                  <div className="text-center py-12 flex-shrink-0">
                    <div className="text-6xl mb-4">📋</div>
                    <h3 className="text-xl font-semibold mb-2 text-blue-900">Faol chatlar yo'q</h3>
                    <p className="text-base text-blue-700">Operator va client gaplashgan chatlar bu yerda ko'rinadi.</p>
                  </div>
                ) : (
                  <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0 scrollbar-hide" style={{
                    WebkitOverflowScrolling: "touch",
                    overscrollBehavior: "contain",
                    overscrollBehaviorY: "contain",
                    scrollPaddingTop: "1rem",
                    scrollPaddingBottom: "1rem",
                    touchAction: "pan-y",
                  }}>
                    <div className="space-y-3 sm:space-y-4 pb-4">
                      {activeChats.map((chat, index) => {
                        const client = users.find((u) => u.id === parseInt(chat.clientId))
                        const operator = users.find((u) => u.id === parseInt(chat.operatorId || "0"))
                        const operatorActiveCount = operator ? getOperatorActiveChatCount(operator.id) : 0
                        return (
                          <div
                            key={chat.id}
                            onClick={() => selectChat(chat.id)}
                            className="p-3 sm:p-4 rounded-xl cursor-pointer transition-all duration-200 transform active:scale-[0.98] hover:scale-[1.02] hover:shadow-lg bg-white hover:bg-blue-50 active:bg-blue-100 border border-blue-200 animate-slide-in touch-manipulation"
                            style={{ animationDelay: `${index * 100}ms`, touchAction: "manipulation" }}
                          >
                            <div className="flex items-start space-x-3 sm:space-x-4">
                              <div className="relative flex-shrink-0">
                                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-sm sm:text-base">
                                  {client?.full_name?.[0]?.toUpperCase() || "?"}
                                </div>
                                <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-green-500 border-2 border-white"></div>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between mb-1">
                                  <h3 className="font-semibold truncate text-blue-900 text-sm sm:text-base">
                                    {client?.full_name || chat.clientName || "Noma'lum mijoz"}
                                  </h3>
                                </div>
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center space-x-2">
                                    <span className="text-xs text-blue-600">
                                      Operator: {operator?.full_name || chat.operatorName || "Noma'lum"}
                                    </span>
                                    <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-800">
                                      ({operatorActiveCount} faol)
                                    </span>
                                  </div>
                                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-200">
                                    ✅ Faol
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : activeView === "closed" ? (
              <div className="h-full flex flex-col min-h-0">
                <h2 className="text-base sm:text-lg md:text-xl font-bold mb-3 sm:mb-4 md:mb-6 text-blue-900 flex-shrink-0 px-1">
                  Chat tarixi (Barcha chatlar)
                </h2>
                {allChats.length === 0 ? (
                  <div className="text-center py-12 flex-shrink-0">
                    <div className="text-6xl mb-4">📝</div>
                    <h3 className="text-xl font-semibold mb-2 text-blue-900">Chatlar yo'q</h3>
                    <p className="text-base text-blue-700">Barcha chatlar bu yerda ko'rinadi.</p>
                  </div>
                ) : (
                  <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0 scrollbar-hide" style={{
                    WebkitOverflowScrolling: "touch",
                    overscrollBehavior: "contain",
                    overscrollBehaviorY: "contain",
                    scrollPaddingTop: "1rem",
                    scrollPaddingBottom: "1rem",
                    touchAction: "pan-y",
                  }}>
                    <ChatList
                      chats={allChats}
                      users={users}
                      onChatSelect={selectChat}
                      isDarkMode={false}
                      currentUserId={dbUser?.id || user.id}
                      showOpenButton={false}
                      isLoading={isLoading}
                      emptyMessage="Chat tarixi topilmadi"
                    />
                  </div>
                )}
              </div>
            ) : activeView === "staff" ? (
              <div className="h-full flex flex-col min-h-0">
                <div className="flex-shrink-0 mb-3 sm:mb-4 md:mb-6 px-1 flex items-center justify-between">
                  <h2 className="text-base sm:text-lg md:text-xl font-bold text-blue-900">
                    Xodimlar bilan chat
                  </h2>
                  <button
                    onClick={() => setShowNewStaffChatModal(true)}
                    className="px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors bg-blue-500 text-white hover:bg-blue-600 active:bg-blue-700 touch-manipulation min-h-[44px]"
                  >
                    + Yangi chat
                  </button>
                </div>
                {staffChats.length === 0 ? (
                  <div className="text-center py-12 flex-shrink-0">
                    <div className="text-6xl mb-4">💬</div>
                    <h3 className="text-xl font-semibold mb-2 text-blue-900">Xodimlar bilan chatlar yo'q</h3>
                    <p className="text-base text-blue-700">Yangi chat yaratish uchun "Yangi chat" tugmasini bosing.</p>
                  </div>
                ) : (
                  <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0 scrollbar-hide" style={{
                    WebkitOverflowScrolling: "touch",
                    overscrollBehavior: "contain",
                    overscrollBehaviorY: "contain",
                    scrollPaddingTop: "1rem",
                    scrollPaddingBottom: "1rem",
                    touchAction: "pan-y",
                  }}>
                    <ChatList
                      chats={staffChats}
                      users={users}
                      onChatSelect={selectChat}
                      isDarkMode={false}
                      currentUserId={dbUser?.id || user.id}
                      showOpenButton={false}
                      isLoading={isLoading}
                      emptyMessage="Xodimlar chati topilmadi"
                    />
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* New Staff Chat Modal */}
      {showNewStaffChatModal && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 safe-area"
          onClick={() => setShowNewStaffChatModal(false)}
        >
          <div 
            className="w-full max-w-md bg-white rounded-xl shadow-2xl overflow-hidden animate-scale-in"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="p-4 sm:p-6">
              <h3 className="text-lg sm:text-xl font-bold mb-4 text-blue-900">
                Xodimni tanlang
              </h3>
              
              {users.filter(u => u.role === 'callcenter_operator' || u.role === 'callcenter_supervisor').length === 0 ? (
                <div className="text-center py-8">
                  <div className="text-4xl mb-4">👥</div>
                  <p className="text-blue-700">Xodimlar topilmadi</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[60vh] overflow-y-auto scrollbar-hide">
                  {users
                    .filter(u => (u.role === 'callcenter_operator' || u.role === 'callcenter_supervisor') && u.id !== (dbUser?.id || user.id))
                    .map((staff) => {
                      const isOnline = onlineUsers.has(staff.id)
                      return (
                        <button
                          key={staff.id}
                          onClick={async (e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            const currentUserId = dbUser?.id || user.id
                            console.log('[SupervisorDashboard] Starting staff chat with:', { staffId: staff.id, currentUserId })
                            if (currentUserId) {
                              try {
                                const chatId = await startStaffChat(staff.id)
                                console.log('[SupervisorDashboard] Staff chat created:', chatId)
                                if (chatId) {
                                  selectChat(chatId)
                                  setShowNewStaffChatModal(false)
                                } else {
                                  console.error('[SupervisorDashboard] Failed to create staff chat - chatId is null')
                                  alert('Xodim bilan chat yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko\'ring.')
                                }
                              } catch (error) {
                                console.error('[SupervisorDashboard] Error creating staff chat:', error)
                                alert('Xodim bilan chat yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko\'ring.')
                              }
                            } else {
                              console.error('[SupervisorDashboard] currentUserId is not available')
                              alert('Foydalanuvchi ma\'lumotlari topilmadi. Iltimos, sahifani yangilang.')
                            }
                          }}
                          className="w-full p-3 sm:p-4 rounded-lg border-2 transition-all duration-200 text-left touch-manipulation min-h-[60px] cursor-pointer border-blue-200 active:border-blue-300 bg-white hover:bg-blue-50 active:bg-blue-100"
                          style={{ pointerEvents: 'auto' }}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3 min-w-0 flex-1">
                              <div className="relative">
                                <div className="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold flex-shrink-0">
                                  {staff.full_name?.[0]?.toUpperCase() || "?"}
                                </div>
                                {/* Online/Offline indicator */}
                                <div className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-white ${
                                  isOnline ? "bg-green-500" : "bg-gray-400"
                                }`}></div>
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="font-medium text-sm sm:text-base truncate text-blue-700">
                                  {staff.full_name || staff.username || "Noma'lum xodim"}
                                  {isOnline && (
                                    <span className="ml-2 text-xs text-green-600">🟢 Onlayn</span>
                                  )}
                                  {!isOnline && (
                                    <span className="ml-2 text-xs text-gray-500">⚫ Offlayn</span>
                                  )}
                                </div>
                                {staff.phone && (
                                  <div className="text-xs text-blue-600 truncate">
                                    📱 {staff.phone}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </button>
                      )
                    })}
                </div>
              )}
              
              <div className="flex space-x-3 mt-6">
                <button
                  onClick={() => setShowNewStaffChatModal(false)}
                  className="flex-1 px-4 py-3 rounded-lg font-medium transition-colors text-base bg-white border border-blue-200 text-blue-700 active:bg-blue-50 touch-manipulation min-h-[44px] flex items-center justify-center"
                >
                  Bekor qilish
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

