"use client"

import { useState, useRef } from "react"

interface InputBarProps {
  onSendMessage: (text: string) => Promise<void>
  isDarkMode: boolean
  isCompact?: boolean
}

export default function InputBar({ onSendMessage, isDarkMode, isCompact = false }: InputBarProps) {
  const [message, setMessage] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const emojis = ["😊", "😂", "❤️", "👍", "👎", "😢", "😮", "😡", "🤔", "👋", "🙏", "✅", "❌", "🎉", "⚡", "🔥"]

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    e.stopPropagation()
    
    const messageText = message.trim()
    if (!messageText || isSending) {
      return
    }

    setIsSending(true)
    setMessage("")

    // Add haptic feedback if available
    if ((window as any).Telegram?.WebApp?.HapticFeedback) {
      (window as any).Telegram.WebApp.HapticFeedback.impactOccurred("light")
    }

    // Play notification sound
    try {
      const audio = new Audio(
        "data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhCSd+zO/FfC8HIoHN8tiSNBgSaLzttZ1OGShIod7qvGYbCTPD8NqNP",
      )
      audio.volume = 0.1
      audio.play().catch(() => {}) // Ignore if audio fails
    } catch {}

    try {
      await onSendMessage(messageText)
    } catch (error) {
      console.error("Error sending message:", error)
      // Restore message if sending failed
      setMessage(messageText)
    } finally {
      setIsSending(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter bosilganda xabar yuborish (Shift+Enter yangi qator uchun)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      e.stopPropagation()
      // handleSubmit ni to'g'ridan-to'g'ri chaqirish o'rniga form submit qilish
      const form = (e.target as HTMLElement).closest('form')
      if (form) {
        form.requestSubmit()
      }
    }
  }

  const addEmoji = (emoji: string) => {
    setMessage((prev) => prev + emoji)
    setShowEmojiPicker(false)
    inputRef.current?.focus()
  }

  return (
    <div className={`${isCompact ? "p-1.5 xs:p-2 sm:p-2.5 md:p-3" : "p-2 xs:p-2.5 sm:p-3 md:p-4"} border-t border-blue-200 transition-colors duration-300 bg-white safe-area-bottom flex-shrink-0 w-full`}>
      {/* Emoji Picker */}
      {showEmojiPicker && (
        <div className="mb-2 xs:mb-2.5 sm:mb-3 p-2 xs:p-2.5 sm:p-3 rounded-lg grid grid-cols-6 xs:grid-cols-7 sm:grid-cols-8 gap-1.5 xs:gap-2 bg-blue-50">
          {emojis.map((emoji, index) => (
            <button
              key={index}
              onClick={() => addEmoji(emoji)}
              className="p-1.5 xs:p-2 sm:p-2 rounded-lg hover:scale-110 transition-transform text-sm xs:text-base sm:text-lg hover:bg-blue-100 touch-manipulation min-h-[44px] min-w-[44px]"
            >
              {emoji}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex items-end space-x-1.5 xs:space-x-2 sm:space-x-2.5 md:space-x-3 w-full">
        {/* Emoji Button */}
        <button
          type="button"
          onClick={() => setShowEmojiPicker(!showEmojiPicker)}
          className={`${isCompact ? "w-8 h-8 xs:w-9 xs:h-9" : "w-9 h-9 xs:w-10 xs:h-10 sm:w-11 sm:h-11 md:w-10 md:h-10"} rounded-full flex items-center justify-center transition-colors text-sm xs:text-base sm:text-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50 active:bg-blue-100 touch-manipulation min-h-[44px] min-w-[44px] flex-shrink-0`}
        >
          😊
        </button>

        {/* Message Input */}
        <div className="flex-1 relative min-w-0">
          <textarea
            ref={inputRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Xabar yozing..."
            rows={1}
            className="w-full px-2 xs:px-2.5 sm:px-3 md:px-4 py-2 xs:py-2.5 sm:py-2.5 md:py-3 rounded-2xl resize-none transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm xs:text-sm sm:text-base md:text-base bg-blue-50 text-blue-900 placeholder-blue-400 border border-blue-200 touch-manipulation"
            style={{
              minHeight: "44px",
              maxHeight: "120px",
              fontSize: "16px", // Prevent zoom on iOS
            }}
            disabled={isSending}
          />

          {/* Character Counter (optional) */}
          {message.length > 100 && (
            <div className="absolute -top-5 xs:-top-6 right-2 text-[10px] xs:text-xs text-blue-600">
              {message.length}/1000
            </div>
          )}
        </div>

        {/* Send Button */}
        <button
          type="submit"
          disabled={!message.trim() || isSending}
          className={`${isCompact ? "w-8 h-8 xs:w-9 xs:h-9" : "w-9 h-9 xs:w-10 xs:h-10 sm:w-11 sm:h-11 md:w-10 md:h-10"} rounded-full flex items-center justify-center transition-all duration-200 transform active:scale-95 touch-manipulation min-h-[44px] min-w-[44px] flex-shrink-0 ${
            message.trim() && !isSending
              ? "bg-blue-500 hover:bg-blue-600 text-white shadow-lg hover:shadow-xl"
              : "bg-blue-200 text-blue-400 cursor-not-allowed"
          }`}
        >
          {isSending ? (
            <div className="w-3.5 h-3.5 xs:w-4 xs:h-4 sm:w-4 sm:h-4 md:w-5 md:h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
          ) : (
            <svg className="w-4 h-4 xs:w-4 xs:h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          )}
        </button>
      </form>
    </div>
  )
}
