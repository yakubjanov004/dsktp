"use client"

import { useState, useEffect, useRef } from "react"
import MessageBubble from "./MessageBubble"
import InputBar from "./InputBar"

export default function ChatWindow({ messages, onSendMessage, isDarkMode }) {
  const [showScrollButton, setShowScrollButton] = useState(false)
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)

  const scrollToBottom = (smooth = true) => {
    messagesEndRef.current?.scrollIntoView({
      behavior: smooth ? "smooth" : "auto",
    })
  }

  const handleScroll = () => {
    if (messagesContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100
      setShowScrollButton(!isNearBottom)
    }
  }

  useEffect(() => {
    scrollToBottom(false)
  }, [])

  useEffect(() => {
    scrollToBottom(true)
  }, [messages])

  return (
    <div className="flex-1 flex flex-col relative">
      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className={`flex-1 overflow-y-auto px-4 py-4 space-y-4 ${isDarkMode ? "bg-gray-900" : "bg-gray-50"}`}
        style={{ maxHeight: "calc(100vh - 140px)" }}
      >
        {messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            isDarkMode={isDarkMode}
            isNew={index === messages.length - 1}
          />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Scroll to Bottom Button */}
      {showScrollButton && (
        <button
          onClick={() => scrollToBottom(true)}
          className={`absolute bottom-20 right-4 w-12 h-12 rounded-full shadow-lg transition-all duration-300 transform hover:scale-110 active:scale-95 z-10 ${
            isDarkMode ? "bg-gray-700 hover:bg-gray-600 text-white" : "bg-white hover:bg-gray-50 text-gray-600"
          }`}
        >
          <svg className="w-6 h-6 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </button>
      )}

      {/* Input Bar */}
      <InputBar onSendMessage={onSendMessage} isDarkMode={isDarkMode} />
    </div>
  )
}
