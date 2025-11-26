"use client"

import { useState, useEffect } from "react"
import type { Message } from "../../lib/api"

interface MessageBubbleProps {
  message: Message
  isOwnMessage: boolean
  isDarkMode: boolean
  isNew: boolean
  senderName: string
  showSenderName?: boolean  // Always show sender name (for supervisor view)
}

export default function MessageBubble({ message, isOwnMessage, isDarkMode, isNew, senderName, showSenderName = false }: MessageBubbleProps) {
  const [isVisible, setIsVisible] = useState(!isNew)

  useEffect(() => {
    if (isNew) {
      const timer = setTimeout(() => setIsVisible(true), 100)
      return () => clearTimeout(timer)
    }
  }, [isNew])

  const formatTime = (timestamp: string | Date) => {
    const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp
    return date.toLocaleTimeString("uz-UZ", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
  }
  
  // Get message text - handle both old and new format
  const messageText = message.message_text || ""
  const messageTimestamp = message.created_at || new Date()

  return (
    <div
      className={`flex w-full ${isOwnMessage ? "justify-end" : "justify-start"} transition-all duration-500 ${
        isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
      }`}
    >
      <div
        className={`max-w-[85%] xs:max-w-[80%] sm:max-w-xs md:max-w-sm lg:max-w-md xl:max-w-lg px-2.5 xs:px-3 sm:px-3.5 md:px-4 lg:px-5 py-2 xs:py-2.5 sm:py-2.5 md:py-3 lg:py-3.5 rounded-2xl shadow-sm relative group ${
          isOwnMessage
            ? "bg-blue-500 text-white"
            : "bg-white text-blue-900 border border-blue-200"
        } ${isOwnMessage ? "rounded-br-md" : "rounded-bl-md"}`}
      >
        {/* Sender Name (for group chats, multi-agent, or supervisor view) */}
        {((showSenderName && senderName) || (!isOwnMessage && senderName)) && (
          <p className={`text-[10px] xs:text-xs sm:text-xs md:text-sm font-medium mb-0.5 xs:mb-1 sm:mb-1 ${
            isOwnMessage ? "text-blue-100" : "text-blue-600"
          }`}>{senderName}</p>
        )}

        {/* Message Content */}
        <div className="space-y-1.5 xs:space-y-2 sm:space-y-2">
          {/* Show message text - default to text if message_text exists */}
          {messageText && (
            <p className="text-sm xs:text-sm sm:text-sm md:text-base lg:text-base leading-relaxed break-words whitespace-pre-wrap word-wrap overflow-wrap-anywhere">{messageText}</p>
          )}

          {/* Handle attachments if present */}
          {message.attachments && typeof message.attachments === 'object' && (
            <>
              {message.attachments.image && (
                <div className="rounded-lg overflow-hidden max-w-full">
                  <img 
                    src={message.attachments.image || "/placeholder.svg"} 
                    alt="Ulashilgan rasm" 
                    className="max-w-full h-auto w-full object-contain rounded-lg" 
                  />
                </div>
              )}
              {message.attachments.file && (
                <div className="flex items-center space-x-1.5 xs:space-x-2 sm:space-x-2.5 md:space-x-3 p-2 xs:p-2.5 sm:p-2.5 md:p-3 rounded-lg bg-blue-50">
                  <div className="text-lg xs:text-xl sm:text-xl md:text-2xl flex-shrink-0">📎</div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs xs:text-xs sm:text-sm md:text-sm font-medium truncate text-blue-900">{message.attachments.file.name || 'Fayl'}</p>
                    {message.attachments.file.size && (
                      <p className="text-[10px] xs:text-xs text-blue-600">{message.attachments.file.size}</p>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Timestamp and Status */}
        <div
          className={`flex items-center justify-end mt-1.5 xs:mt-2 sm:mt-2 space-x-1 text-[10px] xs:text-xs sm:text-xs opacity-70 group-hover:opacity-100 transition-opacity ${
            isOwnMessage ? "text-blue-100" : "text-blue-600"
          }`}
        >
          <span>{formatTime(messageTimestamp)}</span>

          {/* Read Receipt for Own Messages */}
          {isOwnMessage && (
            <div className="flex space-x-0.5 xs:space-x-1">
              <svg className="w-3 h-3 xs:w-3.5 xs:h-3.5 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
          )}
        </div>

        {/* Message Tail */}
        <div
          className={`absolute top-2 xs:top-2.5 sm:top-3 md:top-3 w-3 h-3 xs:w-3.5 xs:h-3.5 sm:w-4 sm:h-4 ${isOwnMessage ? "-right-1.5 xs:-right-2" : "-left-1.5 xs:-left-2"} ${
            isOwnMessage
              ? "bg-blue-500"
              : "bg-white border-l border-t border-blue-200"
          } transform ${isOwnMessage ? "rotate-45" : "-rotate-45"}`}
        ></div>
      </div>
    </div>
  )
}
