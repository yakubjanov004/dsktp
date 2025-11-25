"use client"

import { useState, useEffect } from "react"
import { useChat } from "../../context/ChatContext"
import ChatList from "../shared/ChatList"
import ChatWindow from "../shared/ChatWindow"
import ClosedChats from "../shared/ClosedChats"
import FloatingActionButton from "./FloatingActionButton"
import StatisticsModal from "./StatisticsModal"
import SearchModal from "./SearchModal"

interface TelegramUser {
  first_name: string
  last_name: string
  username: string
  id: number
}

interface CallCenterDashboardProps {
  user: TelegramUser
  dbUser?: any
  isDarkMode: boolean
  onRoleChange: () => void
  role?: "operator" | "supervisor"
}

export default function CallCenterDashboard({ user, dbUser, isDarkMode, onRoleChange, role = "operator" }: CallCenterDashboardProps) {
  const { 
    chatSessions,
    staffChats,
    users, 
    activeChats, 
    addToActiveChats, 
    removeFromActiveChats, 
    startNewChat, 
    isLoading, 
    loadChatMessages, 
    closeChat,
    loadChats,
    loadMyChats,
    loadActiveChatStats,
    activeChatStats,
    onlineUsers,
    loadStaffChats,
    startStaffChat,
    sendStaffMessage,
    loadStaffChatMessages,
    setOnNewMessage,
  } = useChat()
  const currentUserId = dbUser?.id || user.id
  const [activeView, setActiveView] = useState("dashboard")
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null)
  const [openChatWindows, setOpenChatWindows] = useState<string[]>([])
  const [showNewChatModal, setShowNewChatModal] = useState(false)
  const [showStatisticsModal, setShowStatisticsModal] = useState(false)
  const [showSearchModal, setShowSearchModal] = useState(false)
  const [hasLoadedInitial, setHasLoadedInitial] = useState(false)
  const [showNewStaffChatModal, setShowNewStaffChatModal] = useState(false)

  // Operator uchun faqat unga yuborilgan chatlar ko'rsatiladi
  const currentUserIdStr = currentUserId.toString()
  
  // Faol chatlar = status='active' bo'lgan chatlar (operatorga yuborilgan)
  const openChats = chatSessions.filter((chat) => {
    return chat.status === "active" && 
           chat.operatorId === currentUserIdStr
  })
  
  // Chat tarixi = faqat operator o'zi yozishgan chatlar (operator_id = currentUserId)
  // Bu chatlar operatorga yuborilgan va operator kamida 1 ta xabar yozgan
  const chatHistory = chatSessions.filter((chat) => {
    return chat.operatorId === currentUserIdStr
  })

  // Get active chat count from stats
  const activeChatCount = activeChatStats?.operator_counts.find(
    (op) => op.operator_id === currentUserId
  )?.cnt || openChats.length

  // Load initial data on mount - only once
  useEffect(() => {
    if (hasLoadedInitial || isLoading || role !== "operator") return
    
    setHasLoadedInitial(true)
    
    // 1. Load operator active chats (for "Faol chatlar" tab)
    if (user.id) {
      loadMyChats(20)
    }
    
    // 2. Load all operator chats (for "Chat tarixi" tab - active va inactive)
    loadChats()
    
    // 3. Load active chat stats (includes operator_counts)
    loadActiveChatStats()
    
    // 4. Load staff chats
    loadStaffChats()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasLoadedInitial, isLoading, role, user.id]) // loadMyChats, loadChats, loadActiveChatStats, loadStaffChats are stable

  // Auto-open chat window when new message arrives
  useEffect(() => {
    if (!setOnNewMessage) return
    
    setOnNewMessage((chatId: string) => {
      // Only auto-open if no chat is currently selected
      if (!selectedChatId) {
        // Check if this is a chat assigned to current operator
        const chat = chatSessions.find((c) => c.id === chatId)
        if (chat && chat.operatorId === currentUserIdStr) {
          // This is operator's chat - auto-open it
          setSelectedChatId(chatId)
        }
      }
    })
    
    return () => {
      if (setOnNewMessage) {
        setOnNewMessage(null as any)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChatId, currentUserIdStr, setOnNewMessage])

  const handleOpenChatWindow = (chatId: string) => {
    // Chat oynasini to'liq ochish
    setSelectedChatId(chatId)
    
    // Pastki o'ng burchakdagi kichik oynani yopish
    setOpenChatWindows((prev) => prev.filter((id) => id !== chatId))
    // DON'T remove from active chats - keep WebSocket connection alive for real-time updates
    // The chat is still active, just moved to full view
  }

  const handleCloseChatWindow = (chatId: string) => {
    setOpenChatWindows((prev) => prev.filter((id) => id !== chatId))
    removeFromActiveChats(chatId)
  }

  // Find selected chat from both chatSessions and staffChats
  const selectedChat = selectedChatId 
    ? (chatSessions.find((chat) => chat.id === selectedChatId) || staffChats.find((chat) => chat.id === selectedChatId))
    : null
  const isStaffChat = selectedChatId ? staffChats.some((chat) => chat.id === selectedChatId) : false

  // Load messages when chat is selected - ensure all messages are loaded for this chat
  useEffect(() => {
    if (selectedChatId) {
      console.log('[CallCenterDashboard] Loading messages for selected chat:', selectedChatId)
      if (staffChats.some((chat) => chat.id === selectedChatId)) {
        // Staff chat
        loadStaffChatMessages(selectedChatId, true)
      } else {
        // Regular chat
        loadChatMessages(selectedChatId, true)
        addToActiveChats(selectedChatId)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChatId, loadChatMessages, loadStaffChatMessages, addToActiveChats])

  const handleCreateNewChat = () => {
    const clients = users.filter(user => user.role === "client")
    const randomClient = clients[Math.floor(Math.random() * clients.length)]
    
    if (randomClient) {
      const chatTypes = [
        "Umumiy yordam so'rovi",
        "Texnik muammo",
        "To'lov savoli", 
        "Funksiya so'rovi"
      ]
      const randomType = chatTypes[Math.floor(Math.random() * chatTypes.length)]
      
      startNewChat(randomClient.id)
      setShowNewChatModal(false)
    }
  }

  return (
    <div className={`h-[100dvh] h-screen w-full ${isDarkMode ? "bg-gray-900" : "bg-gray-50"} safe-area overflow-hidden flex flex-col`}>
      {/* Header */}
      <div
        className={`${isDarkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"} border-b sticky top-0 z-20 flex-shrink-0 safe-area-top`}
      >
        <div className="w-full max-w-7xl mx-auto px-2 sm:px-3 md:px-4 lg:px-6 py-2 sm:py-2.5 md:py-3">
          <div className="flex items-center justify-between gap-1.5 sm:gap-2 md:gap-3">
            <div className="flex items-center space-x-1.5 sm:space-x-2 md:space-x-3 min-w-0 flex-1">
              <div className="w-8 h-8 xs:w-9 xs:h-9 sm:w-10 sm:h-10 md:w-11 md:h-11 rounded-full bg-gradient-to-r from-purple-500 to-pink-600 flex items-center justify-center text-white font-bold text-xs sm:text-sm md:text-base flex-shrink-0">
                🎧
              </div>
              <div className="min-w-0 flex-1">
                <h1 className={`text-sm xs:text-base sm:text-lg md:text-xl font-bold truncate ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                  {role === "supervisor" ? "Call Center Supervisor" : "Call Center Operator"}
                </h1>
                <p className={`text-xs sm:text-sm md:text-base truncate ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                  {user.first_name} {dbUser?.full_name ? `(${dbUser.full_name})` : ""}
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-1 sm:space-x-1.5 md:space-x-2 flex-shrink-0">
              {/* Stats */}
              <div className="flex space-x-1.5 sm:space-x-2">
                <div
                  className={`px-2 sm:px-3 md:px-4 py-1 sm:py-1.5 md:py-2 rounded-lg text-xs sm:text-sm md:text-base whitespace-nowrap ${isDarkMode ? "bg-green-900/30 text-green-400" : "bg-green-100 text-green-800"}`}
                >
                  <span className="font-medium">{openChats.length} Faol</span>
                </div>
              </div>

              <button
                onClick={onRoleChange}
                className={`px-2 sm:px-3 md:px-4 py-1.5 sm:py-2 md:py-2.5 rounded-lg text-xs sm:text-sm md:text-base font-medium transition-colors touch-manipulation min-h-[44px] flex items-center justify-center ${
                  isDarkMode
                    ? "bg-gray-700 text-gray-300 hover:bg-gray-600 active:bg-gray-500"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200 active:bg-gray-300"
                }`}
              >
                <span className="hidden sm:inline">Rolni o'zgartirish</span>
                <span className="sm:hidden">🔄</span>
              </button>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex space-x-1.5 sm:space-x-2 mt-2 sm:mt-3 overflow-x-auto pb-1 -mx-2 px-2 sm:-mx-3 sm:px-3 md:mx-0 md:px-0 scrollbar-hide">
            {[
              { id: "dashboard", label: "Faol chatlar", count: openChats.length },
              { id: "closed", label: "Chat tarixi", count: chatHistory.length },
              { id: "staff", label: "Xodimlar bilan chat", count: staffChats.length },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveView(tab.id)
                  setSelectedChatId(null)
                }}
                className={`px-2.5 sm:px-3 md:px-4 py-1.5 sm:py-2 md:py-2.5 rounded-lg font-medium transition-all duration-200 text-xs sm:text-sm md:text-base whitespace-nowrap touch-manipulation min-h-[44px] flex items-center ${
                  activeView === tab.id
                    ? isDarkMode
                      ? "bg-purple-600 text-white shadow-lg"
                      : "bg-purple-500 text-white shadow-lg"
                    : isDarkMode
                      ? "text-gray-400 hover:text-white hover:bg-gray-700 active:bg-gray-600"
                      : "text-gray-600 hover:text-gray-900 hover:bg-gray-100 active:bg-gray-200"
                }`}
              >
                {tab.label}
                {tab.count > 0 && (
                  <span
                    className={`ml-1 sm:ml-2 px-1.5 py-0.5 rounded-full text-xs ${
                      activeView === tab.id ? "bg-white/20" : isDarkMode ? "bg-gray-700" : "bg-gray-200"
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* New Chat Modal */}
      {showNewChatModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 sm:p-4">
          <div
            className={`max-w-sm sm:max-w-md w-full p-4 sm:p-6 rounded-xl shadow-2xl ${
              isDarkMode ? "bg-gray-800 text-white" : "bg-white text-gray-900"
            }`}
          >
            <h3 className={`text-lg sm:text-xl font-bold mb-4 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
              Yangi chat yaratish
            </h3>
            <p className={`mb-6 text-sm sm:text-base ${isDarkMode ? "text-gray-300" : "text-gray-600"}`}>
              Random mijoz bilan yangi chat yaratiladi.
            </p>
            <div className="flex space-x-3">
              <button
                onClick={handleCreateNewChat}
                className={`flex-1 py-2 sm:py-3 px-3 sm:px-4 rounded-lg font-medium transition-colors text-sm sm:text-base ${
                  isDarkMode
                    ? "bg-purple-600 text-white hover:bg-purple-700"
                    : "bg-purple-500 text-white hover:bg-purple-600"
                }`}
              >
                Yaratish
              </button>
              <button
                onClick={() => setShowNewChatModal(false)}
                className={`flex-1 py-2 sm:py-3 px-3 sm:px-4 rounded-lg font-medium transition-colors text-sm sm:text-base ${
                  isDarkMode
                    ? "bg-gray-700 text-gray-300 hover:bg-gray-600"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                Bekor qilish
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="w-full max-w-7xl mx-auto px-2 sm:px-3 md:px-4 lg:px-6 py-2 sm:py-3 md:py-4 lg:py-6 pb-2 sm:pb-3 md:pb-4 lg:pb-6 safe-area-bottom flex-1 flex flex-col min-h-0 overflow-hidden">
        {selectedChat ? (
          <div className="animate-fade-in h-full flex flex-col min-h-0 overflow-hidden">
            <ChatWindow
              chat={selectedChat}
              currentUserId={currentUserId}
              onBack={() => {
                setSelectedChatId(null)
                // Pastki o'ng burchakdagi kichik oynalarni ham yopish
                setOpenChatWindows([])
              }}
              onClose={() => {
                setSelectedChatId(null)
                // Pastki o'ng burchakdagi kichik oynalarni ham yopish
                setOpenChatWindows([])
              }}
              isDarkMode={isDarkMode}
              isReadOnly={!isStaffChat && selectedChat.status === "inactive"}
              isStaffChat={isStaffChat}
            />
          </div>
        ) : (
          <div className="animate-slide-in">
            {activeView === "dashboard" ? (
              <div className="h-full flex flex-col min-h-0">
                <div className="flex-shrink-0 mb-3 sm:mb-4 md:mb-6 px-1">
                  <h2 className={`text-base sm:text-lg md:text-xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                    Faol chatlar
                  </h2>
                </div>
                {openChats.length === 0 ? (
                  <div className={`text-center py-12 flex-shrink-0 ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                    <div className="text-4xl sm:text-6xl mb-4">💬</div>
                    <h3 className="text-lg sm:text-xl font-semibold mb-2">Ochiq chatlar yo'q</h3>
                    <p className="text-sm sm:text-base">Yangi chatlar kelganda, ular bu yerda ko'rinadi.</p>
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
                      chats={openChats}
                      users={users}
                      onChatSelect={handleOpenChatWindow}
                      isDarkMode={isDarkMode}
                      currentUserId={currentUserId}
                      showOpenButton={true}
                      isLoading={isLoading}
                      emptyMessage="Faol chatlar topilmadi"
                    />
                  </div>
                )}
              </div>
            ) : activeView === "closed" ? (
              <div className="h-full flex flex-col min-h-0">
                <div className="flex-shrink-0 mb-3 sm:mb-4 md:mb-6 px-1">
                  <h2 className={`text-base sm:text-lg md:text-xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                    Chat tarixi (Mening chatlarim)
                  </h2>
                </div>
                {chatHistory.length === 0 ? (
                  <div className={`text-center py-12 flex-shrink-0 ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                    <div className="text-4xl sm:text-6xl mb-4">📝</div>
                    <h3 className="text-lg sm:text-xl font-semibold mb-2">Chat tarixi yo'q</h3>
                    <p className="text-sm sm:text-base">Siz yozgan chatlar bu yerda ko'rinadi.</p>
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
                      chats={chatHistory}
                      users={users}
                      onChatSelect={handleOpenChatWindow}
                      isDarkMode={isDarkMode}
                      currentUserId={currentUserId}
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
                  <h2 className={`text-base sm:text-lg md:text-xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                    Xodimlar bilan chat
                  </h2>
                  <button
                    onClick={() => setShowNewStaffChatModal(true)}
                    className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors touch-manipulation min-h-[44px] ${
                      isDarkMode
                        ? "bg-purple-600 text-white hover:bg-purple-700"
                        : "bg-purple-500 text-white hover:bg-purple-600"
                    }`}
                  >
                    + Yangi chat
                  </button>
                </div>
                {staffChats.length === 0 ? (
                  <div className={`text-center py-12 flex-shrink-0 ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                    <div className="text-4xl sm:text-6xl mb-4">💬</div>
                    <h3 className="text-lg sm:text-xl font-semibold mb-2">Xodimlar bilan chatlar yo'q</h3>
                    <p className="text-sm sm:text-base">Yangi chat yaratish uchun "Yangi chat" tugmasini bosing.</p>
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
                      onChatSelect={handleOpenChatWindow}
                      isDarkMode={isDarkMode}
                      currentUserId={currentUserId}
                      showOpenButton={true}
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
          className={`fixed inset-0 ${isDarkMode ? "bg-black" : "bg-black"} bg-opacity-50 flex items-center justify-center z-50 p-4 safe-area`}
          onClick={() => setShowNewStaffChatModal(false)}
        >
          <div 
            className={`w-full max-w-md ${isDarkMode ? "bg-gray-800" : "bg-white"} rounded-xl shadow-2xl overflow-hidden animate-scale-in`}
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="p-4 sm:p-6">
              <h3 className={`text-lg sm:text-xl font-bold mb-4 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                Xodimni tanlang
              </h3>
              
              {users.filter(u => u.role === 'callcenter_operator' || u.role === 'callcenter_supervisor').length === 0 ? (
                <div className="text-center py-8">
                  <div className="text-4xl mb-4">👥</div>
                  <p className={isDarkMode ? "text-gray-300" : "text-gray-700"}>Xodimlar topilmadi</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[60vh] overflow-y-auto scrollbar-hide">
                  {users
                    .filter(u => (u.role === 'callcenter_operator' || u.role === 'callcenter_supervisor') && u.id !== currentUserId)
                    .map((staff) => {
                      const isOnline = onlineUsers.has(staff.id)
                      return (
                        <button
                          key={staff.id}
                          onClick={async (e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            console.log('[CallCenterDashboard] Starting staff chat with:', { staffId: staff.id, currentUserId })
                            if (currentUserId) {
                              try {
                                const chatId = await startStaffChat(staff.id)
                                console.log('[CallCenterDashboard] Staff chat created:', chatId)
                                if (chatId) {
                                  setSelectedChatId(chatId)
                                  setShowNewStaffChatModal(false)
                                } else {
                                  console.error('[CallCenterDashboard] Failed to create staff chat - chatId is null')
                                  alert('Xodim bilan chat yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko\'ring.')
                                }
                              } catch (error) {
                                console.error('[CallCenterDashboard] Error creating staff chat:', error)
                                alert('Xodim bilan chat yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko\'ring.')
                              }
                            } else {
                              console.error('[CallCenterDashboard] currentUserId is not available')
                              alert('Foydalanuvchi ma\'lumotlari topilmadi. Iltimos, sahifani yangilang.')
                            }
                          }}
                          className={`w-full p-3 sm:p-4 rounded-lg border-2 transition-all duration-200 text-left touch-manipulation min-h-[60px] cursor-pointer ${
                            isDarkMode
                              ? "border-gray-700 bg-gray-700 hover:bg-gray-600 active:bg-gray-500"
                              : "border-gray-200 active:border-gray-300 bg-white hover:bg-gray-50 active:bg-gray-100"
                          }`}
                          style={{ pointerEvents: 'auto' }}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3 min-w-0 flex-1">
                              <div className="relative">
                                <div className={`w-10 h-10 rounded-full ${isDarkMode ? "bg-purple-600" : "bg-purple-500"} flex items-center justify-center text-white font-bold flex-shrink-0`}>
                                  {staff.full_name?.[0]?.toUpperCase() || "?"}
                                </div>
                                {/* Online/Offline indicator */}
                                <div className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 ${isDarkMode ? "border-gray-800" : "border-white"} ${
                                  isOnline ? "bg-green-500" : "bg-gray-400"
                                }`}></div>
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className={`font-medium text-sm sm:text-base truncate ${
                                  isDarkMode ? "text-white" : "text-gray-900"
                                }`}>
                                  {staff.full_name || staff.username || "Noma'lum xodim"}
                                  {isOnline && (
                                    <span className="ml-2 text-xs text-green-500">🟢 Onlayn</span>
                                  )}
                                  {!isOnline && (
                                    <span className="ml-2 text-xs text-gray-500">⚫ Offlayn</span>
                                  )}
                                </div>
                                {staff.phone && (
                                  <div className={`text-xs truncate ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
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
                  className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors text-base touch-manipulation min-h-[44px] flex items-center justify-center ${
                    isDarkMode
                      ? "bg-gray-700 text-gray-300 hover:bg-gray-600"
                      : "bg-white border border-gray-200 text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  Bekor qilish
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Chat Windows - Only show in Dashboard and when no selected chat */}
      {activeView === "dashboard" && !selectedChatId && openChatWindows.map((chatId) => {
        const chat = chatSessions.find((c) => c.id === chatId)
        if (!chat) return null

        return (
          <div
            key={chatId}
            className="fixed bottom-4 right-4 w-72 h-80 sm:w-80 sm:h-96 z-30 animate-slide-up"
            style={{
              right: `${4 + openChatWindows.indexOf(chatId) * 280}px`,
              zIndex: 30 + openChatWindows.indexOf(chatId),
            }}
          >
            <ChatWindow
              chat={chat}
              currentUserId={currentUserId}
              onBack={() => {}}
              isDarkMode={isDarkMode}
              isFloating={true}
              onClose={() => handleCloseChatWindow(chatId)}
            />
          </div>
        )
      })}

      {/* Modals */}
      <StatisticsModal 
        isOpen={showStatisticsModal}
        onClose={() => setShowStatisticsModal(false)}
        isDarkMode={isDarkMode}
      />
      
      <SearchModal 
        isOpen={showSearchModal}
        onClose={() => setShowSearchModal(false)}
        isDarkMode={isDarkMode}
      />

      {/* Floating Action Button */}
      <FloatingActionButton 
        isDarkMode={isDarkMode}
        onNewChat={() => setShowNewChatModal(true)}
        onSearch={() => setShowSearchModal(true)}
        onStatistics={() => setShowStatisticsModal(true)}
      />
    </div>
  )
}
