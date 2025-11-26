"use client"

import { useState, useRef, useEffect } from "react"
import { useChat } from "../../context/ChatContext"
import type { Message } from "../../lib/api"
import MessageBubble from "./MessageBubble"
import InputBar from "./InputBar"
import ChatHeader from "./ChatHeader"

interface ChatSession {
  id: string
  clientId: string
  operatorId: string | null
  status: "active" | "inactive"
  createdAt: Date
  lastActivity: Date
  lastClientActivityAt?: string | null
  messages: Message[]
  lastMessage: Message | null
  clientName?: string
  operatorName?: string | null
}

interface ChatWindowProps {
  chat: ChatSession
  currentUserId: number | string
  onBack?: () => void
  onClose?: () => void
  isDarkMode: boolean
  isReadOnly?: boolean
  isCompact?: boolean
  isFloating?: boolean
  isStaffChat?: boolean
  isLoadingMessages?: boolean
  isSupervisorView?: boolean  // CCS viewing client chats - shows operator messages on right with names
}

export default function ChatWindow({
  chat,
  currentUserId,
  onBack,
  onClose,
  isDarkMode,
  isReadOnly = false,
  isCompact = false,
  isFloating = false,
  isStaffChat = false,
  isLoadingMessages = false,
  isSupervisorView = false,
}: ChatWindowProps) {
  const { users, sendMessage, sendStaffMessage, closeChat, typingUsers } = useChat()
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [showScrollToTopButton, setShowScrollToTopButton] = useState(false)
  const [showCloseConfirm, setShowCloseConfirm] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)

  // Convert currentUserId to number if it's a string
  const currentUserIdNum = typeof currentUserId === "string" ? parseInt(currentUserId) : currentUserId
  const chatClientId = parseInt(chat.clientId)
  
  // Determine other user (operator or client)
  const otherUserId = currentUserIdNum === chatClientId ? (chat.operatorId ? parseInt(chat.operatorId) : null) : chatClientId
  const otherUser = otherUserId ? users.find((u) => u.id === otherUserId) : null
  const isTyping = typingUsers[chat.id] || typingUsers[`${chat.id}-${otherUserId}`] || false

  const scrollToBottom = (smooth = true) => {
    // Use requestAnimationFrame to ensure DOM is updated
    requestAnimationFrame(() => {
      if (messagesContainerRef.current) {
        const container = messagesContainerRef.current
        const scrollHeight = container.scrollHeight
        const clientHeight = container.clientHeight
        
        if (scrollHeight > clientHeight) {
          container.scrollTo({
            top: scrollHeight,
            behavior: smooth ? "smooth" : "auto",
          })
        }
      }
      
      // Fallback to scrollIntoView
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({
          behavior: smooth ? "smooth" : "auto",
          block: "end",
        })
      }
    })
  }

  const scrollToTop = (smooth = true) => {
    requestAnimationFrame(() => {
      if (messagesContainerRef.current) {
        messagesContainerRef.current.scrollTo({
          top: 0,
          behavior: smooth ? "smooth" : "auto",
        })
      }
    })
  }

  const handleScroll = () => {
    if (messagesContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100
      const isScrolledFromTop = scrollTop > 200 // Show scroll to top button if scrolled more than 200px
      setShowScrollButton(!isNearBottom)
      setShowScrollToTopButton(isScrolledFromTop)
    }
  }

  const handleSendMessage = async (text: string) => {
    if (isStaffChat) {
      await sendStaffMessage(chat.id, text, currentUserIdNum)
    } else {
      await sendMessage(chat.id, text, currentUserIdNum)
    }

    // Add haptic feedback if available
    if ((window as any).Telegram?.WebApp?.HapticFeedback) {
      (window as any).Telegram.WebApp.HapticFeedback.impactOccurred("light")
    }
  }

  const handleCloseChat = () => {
    // Show confirmation modal first
    setShowCloseConfirm(true)
  }

  const confirmCloseChat = () => {
    closeChat(chat.id)
    setShowCloseConfirm(false)
    if (onBack) onBack()
    if (onClose) onClose()
  }

  const cancelCloseChat = () => {
    setShowCloseConfirm(false)
  }

  // Handle ESC key to close modal
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && showCloseConfirm) {
        setShowCloseConfirm(false)
      }
    }

    if (showCloseConfirm) {
      document.addEventListener("keydown", handleEscape)
      // Prevent body scroll when modal is open
      document.body.style.overflow = "hidden"
    }

    return () => {
      document.removeEventListener("keydown", handleEscape)
      document.body.style.overflow = ""
    }
  }, [showCloseConfirm])

  // Scroll to bottom on mount
  useEffect(() => {
    // Use requestAnimationFrame and setTimeout to ensure DOM is ready
    requestAnimationFrame(() => {
      setTimeout(() => {
        scrollToBottom(false)
      }, 100)
    })
  }, [])

  // Scroll to bottom when messages change
  useEffect(() => {
    if (chat.messages && chat.messages.length > 0) {
      // Use requestAnimationFrame to ensure new message is rendered
      requestAnimationFrame(() => {
        setTimeout(() => {
          scrollToBottom(true)
        }, 50)
      })
    }
  }, [chat.messages])

  const windowClass = isFloating
    ? "bg-white border border-blue-200 rounded-xl shadow-2xl"
    : isCompact
      ? "bg-white border border-blue-200 rounded-xl"
      : "bg-white"

  return (
    <>
      {/* Close Confirmation Modal */}
      {showCloseConfirm && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 sm:p-3 md:p-4 safe-area"
          onClick={cancelCloseChat}
        >
          <div 
            className="w-full max-w-xs sm:max-w-sm md:max-w-md bg-white rounded-xl shadow-2xl overflow-hidden animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-3 sm:p-4 md:p-6">
              <div className="flex items-center justify-center mb-3 sm:mb-4">
                <div className="w-12 h-12 sm:w-14 sm:h-14 md:w-16 md:h-16 rounded-full bg-red-100 flex items-center justify-center">
                  <svg className="w-6 h-6 sm:w-7 sm:h-7 md:w-8 md:h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
              </div>
              <h3 className="text-base sm:text-lg md:text-xl font-bold text-center mb-2 text-blue-900">
                Chatni yopishni tasdiqlaysizmi?
              </h3>
              <p className="text-xs sm:text-sm md:text-base text-center text-blue-700 mb-4 sm:mb-5 md:mb-6">
                Haqiqatdan chatni yopmoqchimisiz? Bu amalni bekor qilib bo'lmaydi.
              </p>
              <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
                <button
                  onClick={confirmCloseChat}
                  className="flex-1 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg font-medium transition-colors text-sm sm:text-base bg-red-500 text-white hover:bg-red-600 active:bg-red-700 touch-manipulation min-h-[44px] flex items-center justify-center"
                >
                  Ha, yopish
                </button>
                <button
                  onClick={cancelCloseChat}
                  className="flex-1 px-3 sm:px-4 py-2.5 sm:py-3 rounded-lg font-medium transition-colors text-sm sm:text-base bg-white border border-blue-200 text-blue-700 hover:bg-blue-50 active:bg-blue-100 touch-manipulation min-h-[44px] flex items-center justify-center"
                >
                  Bekor qilish
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className={`flex flex-col h-full w-full min-h-0 ${windowClass} ${isFloating || isCompact ? "max-h-96" : ""}`}>
        {/* Chat Header - Sticky */}
      <div className="sticky top-0 z-20 bg-white border-b border-blue-200 shadow-sm flex-shrink-0">
        <ChatHeader
          user={otherUser}
          chat={chat}
          onBack={onBack}
          onClose={undefined}
          onCloseChat={undefined}
          isDarkMode={false}
          isReadOnly={isReadOnly}
          isCompact={isCompact || isFloating}
        />
      </div>

      {/* Messages Area - Fully responsive */}
      <div className="flex-1 flex flex-col relative overflow-hidden min-h-0 w-full">
        <div
          ref={messagesContainerRef}
          onScroll={handleScroll}
          className={`flex-1 overflow-y-auto overflow-x-hidden w-full px-2 xs:px-2.5 sm:px-3 md:px-4 lg:px-5 py-2 xs:py-2.5 sm:py-3 md:py-4 space-y-2 xs:space-y-2.5 sm:space-y-3 md:space-y-4 bg-blue-50 ${isFloating || isCompact ? "max-h-60" : ""}`}
          style={{
            scrollBehavior: "smooth",
            WebkitOverflowScrolling: "touch",
            overscrollBehavior: "contain",
            overscrollBehaviorY: "contain",
            minHeight: 0,
            scrollPaddingTop: "0.75rem",
            scrollPaddingBottom: "0.75rem",
            touchAction: "pan-y",
            // Custom scrollbar for better visibility
            scrollbarWidth: "thin",
            scrollbarColor: "rgba(59, 130, 246, 0.5) transparent",
          }}
        >
          {isLoadingMessages ? (
            <div className="space-y-4 p-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className={`flex ${i % 2 === 0 ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-xs rounded-lg p-3 animate-pulse ${
                    i % 2 === 0 ? 'bg-gray-300' : 'bg-gray-200'
                  }`}>
                    <div className="h-4 bg-gray-400 rounded w-full mb-2"></div>
                    <div className="h-3 bg-gray-400 rounded w-2/3"></div>
                  </div>
                </div>
              ))}
            </div>
          ) : chat.messages && chat.messages.length > 0 ? (
            chat.messages.map((message: Message, index: number) => {
              const messageSenderId = typeof message.sender_id === "string" ? parseInt(message.sender_id) : message.sender_id
              
              // CCS (supervisor) viewing client chats:
              // - Client messages → LEFT side
              // - Operator messages → RIGHT side (with operator name shown)
              // Normal view: own messages on right, others on left
              let isOwnMessage: boolean
              if (isSupervisorView && !isStaffChat) {
                // Supervisor viewing client chat - operator messages on right
                isOwnMessage = message.sender_type === "operator"
              } else {
                // Normal view - own messages on right
                isOwnMessage = messageSenderId === currentUserIdNum
              }
              
              // Har bir xabar uchun to'g'ri yuboruvchi ismini topish
              let senderName = ""
              
              if (isSupervisorView && !isStaffChat) {
                // Supervisor view: Show operator names on RIGHT, client name on LEFT
                if (message.sender_type === "operator") {
                  // Find operator name from users list or message.sender_name
                  const operatorUser = users.find((u) => u.id === messageSenderId)
                  if (operatorUser) {
                    senderName = operatorUser.full_name || "Operator"
                  } else if (message.sender_name) {
                    senderName = message.sender_name
                  } else {
                    senderName = "Operator"
                  }
                } else {
                  // Client message - show client name
                  senderName = chat.clientName || message.sender_name || "Mijoz"
                }
              } else {
                // Normal view
                if (isOwnMessage) {
                  senderName = "Siz"
                } else {
                  // Xabar yuboruvchi foydalanuvchini topish
                  const messageSender = users.find((u) => u.id === messageSenderId)
                  if (messageSender) {
                    senderName = messageSender.full_name || "Foydalanuvchi"
                  } else if (message.sender_name) {
                    senderName = message.sender_name
                  } else if (otherUser && messageSenderId === otherUserId) {
                    // Fallback: agar otherUser topilgan bo'lsa va ID mos kelsa
                    senderName = otherUser.full_name || "Foydalanuvchi"
                  }
                }
              }
              
              return (
                <MessageBubble
                  key={message.id || `msg-${index}-${message.created_at}`}
                  message={message}
                  isOwnMessage={isOwnMessage}
                  isDarkMode={false}
                  isNew={index === chat.messages.length - 1}
                  senderName={senderName}
                  showSenderName={isSupervisorView && !isStaffChat}
                />
              )
            })
          ) : (
            <div className="flex items-center justify-center h-full w-full text-center py-6 sm:py-8 md:py-12 px-2 sm:px-4">
              <div>
                <div className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl mb-2 sm:mb-3 md:mb-4">💬</div>
                <h3 className="text-sm sm:text-base md:text-lg lg:text-xl font-semibold mb-1 sm:mb-2 text-blue-900">Hali xabar yo'q</h3>
                <p className="text-xs sm:text-sm md:text-base text-blue-700">Birinchi xabarni yozing</p>
              </div>
            </div>
          )}

          {/* Typing Indicator */}
          {isTyping && (
            <div className="flex justify-start animate-fade-in w-full">
              <div className="max-w-[85%] xs:max-w-[80%] sm:max-w-xs md:max-w-sm lg:max-w-md px-2.5 xs:px-3 sm:px-4 md:px-5 py-2 xs:py-2.5 sm:py-3 md:py-3.5 rounded-2xl rounded-bl-md bg-white text-blue-600 border border-blue-200">
                <div className="flex space-x-1">
                  <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-current rounded-full animate-bounce"></div>
                  <div
                    className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-current rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  ></div>
                  <div
                    className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-current rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  ></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Scroll to Top Button */}
        {showScrollToTopButton && (
          <button
            onClick={() => scrollToTop(true)}
            className="absolute top-2 xs:top-2.5 sm:top-3 md:top-4 right-2 xs:right-2.5 sm:right-3 md:right-4 w-9 h-9 xs:w-10 xs:h-10 sm:w-11 sm:h-11 md:w-10 md:h-10 rounded-full shadow-lg transition-all duration-300 transform active:scale-95 hover:scale-110 z-10 bg-white hover:bg-blue-50 active:bg-blue-100 text-blue-600 border border-blue-200 touch-manipulation min-h-[44px] min-w-[44px]"
            title="Tepaga"
          >
            <svg className="w-4 h-4 xs:w-4 xs:h-4 sm:w-5 sm:h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
            </svg>
          </button>
        )}

        {/* Scroll to Bottom Button */}
        {showScrollButton && (
          <button
            onClick={() => scrollToBottom(true)}
            className="absolute bottom-14 xs:bottom-16 sm:bottom-18 md:bottom-20 lg:bottom-24 right-2 xs:right-2.5 sm:right-3 md:right-4 w-9 h-9 xs:w-10 xs:h-10 sm:w-11 sm:h-11 md:w-10 md:h-10 rounded-full shadow-lg transition-all duration-300 transform active:scale-95 hover:scale-110 z-10 bg-white hover:bg-blue-50 active:bg-blue-100 text-blue-600 border border-blue-200 touch-manipulation min-h-[44px] min-w-[44px]"
            title="Pastga"
          >
            <svg className="w-4 h-4 xs:w-4 xs:h-4 sm:w-5 sm:h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
            </svg>
          </button>
        )}

        {/* Input Bar */}
        {!isReadOnly && (
          <InputBar onSendMessage={handleSendMessage} isDarkMode={false} isCompact={isCompact || isFloating} />
        )}
      </div>
    </div>
    </>
  )
}
