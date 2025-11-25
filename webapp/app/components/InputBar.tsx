"use client"

import { useState, useRef } from "react"

export default function InputBar({ onSendMessage, isDarkMode }) {
  const [message, setMessage] = useState("")
  const [isSending, setIsSending] = useState(false)
  const inputRef = useRef(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!message.trim() || isSending) return

    setIsSending(true)
    const messageText = message.trim()
    setMessage("")

    // Add haptic feedback if available
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("light")
    }

    try {
      await onSendMessage(messageText)
    } finally {
      setIsSending(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div
      className={`sticky bottom-0 p-4 border-t transition-colors duration-300 ${
        isDarkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
      }`}
    >
      <form onSubmit={handleSubmit} className="flex items-end space-x-3">
        {/* Message Input */}
        <div className="flex-1 relative">
          <textarea
            ref={inputRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type a message..."
            rows={1}
            className={`w-full px-4 py-3 rounded-2xl resize-none transition-all duration-200 focus:outline-none focus:ring-2 ${
              isDarkMode
                ? "bg-gray-700 text-white placeholder-gray-400 focus:ring-blue-500 border border-gray-600"
                : "bg-gray-100 text-gray-800 placeholder-gray-500 focus:ring-blue-500 border border-gray-300"
            }`}
            style={{
              minHeight: "48px",
              maxHeight: "120px",
            }}
            disabled={isSending}
          />

          {/* Character Counter (optional) */}
          {message.length > 100 && (
            <div className={`absolute -top-6 right-2 text-xs ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
              {message.length}/1000
            </div>
          )}
        </div>

        {/* Send Button */}
        <button
          type="submit"
          disabled={!message.trim() || isSending}
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 transform active:scale-95 ${
            message.trim() && !isSending
              ? isDarkMode
                ? "bg-blue-600 hover:bg-blue-700 text-white shadow-lg hover:shadow-xl"
                : "bg-blue-500 hover:bg-blue-600 text-white shadow-lg hover:shadow-xl"
              : isDarkMode
                ? "bg-gray-600 text-gray-400 cursor-not-allowed"
                : "bg-gray-300 text-gray-500 cursor-not-allowed"
          }`}
        >
          {isSending ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
          ) : (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          )}
        </button>
      </form>

      {/* WebSocket Status Indicator */}
      <div
        className={`flex items-center justify-center mt-2 text-xs ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}
      >
        <div className="w-2 h-2 rounded-full bg-yellow-500 mr-2 animate-pulse"></div>
        Local mode (WebSocket ready for integration)
      </div>
    </div>
  )
}
