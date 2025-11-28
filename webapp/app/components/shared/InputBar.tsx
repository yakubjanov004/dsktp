"use client"

import { useState, useRef, useEffect } from "react"

interface InputBarProps {
  onSendMessage: (text: string) => Promise<void>
  onTyping?: (isTyping: boolean) => void
  onSendVoice?: (audioFile: File) => Promise<void>
  onSendImage?: (imageFile: File, messageText?: string) => Promise<void>
  isDarkMode: boolean
  isCompact?: boolean
}

export default function InputBar({ onSendMessage, onTyping, onSendVoice, onSendImage, isDarkMode, isCompact = false }: InputBarProps) {
  const [message, setMessage] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [recordingTime, setRecordingTime] = useState(0)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const recordingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const emojis = ["😊", "😂", "❤️", "👍", "👎", "😢", "😮", "😡", "🤔", "👋", "🙏", "✅", "❌", "🎉", "⚡", "🔥"]

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current)
      }
      if (onTyping) {
        onTyping(false)
      }
    }
  }, [onTyping])

  const handleTyping = (value: string) => {
    setMessage(value)
    
    if (!onTyping) return
    
    const isTyping = value.trim().length > 0
    
    // Clear previous timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current)
      typingTimeoutRef.current = null
    }
    
    // Send typing event
    onTyping(isTyping)
    
    // Auto-clear typing after 3 seconds of inactivity
    if (isTyping) {
      typingTimeoutRef.current = setTimeout(() => {
        onTyping(false)
        typingTimeoutRef.current = null
      }, 3000)
    }
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    e.stopPropagation()
    
    const messageText = message.trim()
    if (!messageText || isSending) {
      return
    }

    // Clear typing indicator
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current)
      typingTimeoutRef.current = null
    }
    if (onTyping) {
      onTyping(false)
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
    const newValue = message + emoji
    handleTyping(newValue)
    setShowEmojiPicker(false)
    inputRef.current?.focus()
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4"
      })
      
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }
      
      mediaRecorder.onstop = async () => {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop())
          streamRef.current = null
        }
        
        if (audioChunksRef.current.length > 0) {
          const audioBlob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType })
          const audioFile = new File([audioBlob], `voice-${Date.now()}.${mediaRecorder.mimeType.includes("webm") ? "webm" : "mp4"}`, {
            type: mediaRecorder.mimeType
          })
          
          if (onSendVoice && audioFile.size > 0) {
            await onSendVoice(audioFile)
          }
        }
        
        setIsRecording(false)
        setRecordingTime(0)
      }
      
      mediaRecorder.start()
      setIsRecording(true)
      setRecordingTime(0)
      
      recordingIntervalRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1)
      }, 1000)
    } catch (error) {
      console.error("Error starting recording:", error)
      alert("Microphone access denied. Please allow microphone access.")
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop()
    }
    if (recordingIntervalRef.current) {
      clearInterval(recordingIntervalRef.current)
      recordingIntervalRef.current = null
    }
  }

  const cancelRecording = () => {
    if (mediaRecorderRef.current) {
      if (mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop()
      }
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    audioChunksRef.current = []
    setIsRecording(false)
    setRecordingTime(0)
    if (recordingIntervalRef.current) {
      clearInterval(recordingIntervalRef.current)
      recordingIntervalRef.current = null
    }
  }

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate image file
    if (!file.type.startsWith('image/')) {
      alert('Iltimos, faqat rasm faylini tanlang')
      return
    }

    // Check file size (max 10MB)
    const maxSize = 10 * 1024 * 1024 // 10MB
    if (file.size > maxSize) {
      alert('Rasm hajmi 10MB dan katta bo\'lmasligi kerak')
      return
    }

    if (onSendImage) {
      onSendImage(file, message.trim() || undefined)
      setMessage("") // Clear message after sending
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleImageButtonClick = () => {
    fileInputRef.current?.click()
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current)
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop())
        streamRef.current = null
      }
    }
  }, [])

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

      {/* Recording Indicator */}
      {isRecording && (
        <div className="mb-2 flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-red-700 font-medium">
              Recording: {Math.floor(recordingTime / 60)}:{(recordingTime % 60).toString().padStart(2, "0")}
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={stopRecording}
              className="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600"
            >
              Send
            </button>
            <button
              onClick={cancelRecording}
              className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex items-end space-x-1.5 xs:space-x-2 sm:space-x-2.5 md:space-x-3 w-full">
        {/* Hidden file input for images */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleImageSelect}
          className="hidden"
        />

        {/* Voice/Emoji/Image Button */}
        {isRecording ? (
          <button
            type="button"
            onClick={stopRecording}
            className={`${isCompact ? "w-8 h-8 xs:w-9 xs:h-9" : "w-9 h-9 xs:w-10 xs:h-10 sm:w-11 sm:h-11 md:w-10 md:h-10"} rounded-full flex items-center justify-center transition-colors bg-red-500 text-white hover:bg-red-600 active:bg-red-700 touch-manipulation min-h-[44px] min-w-[44px] flex-shrink-0`}
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z" />
            </svg>
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={startRecording}
              className={`${isCompact ? "w-8 h-8 xs:w-9 xs:h-9" : "w-9 h-9 xs:w-10 xs:h-10 sm:w-11 sm:h-11 md:w-10 md:h-10"} rounded-full flex items-center justify-center transition-colors text-sm xs:text-base sm:text-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50 active:bg-blue-100 touch-manipulation min-h-[44px] min-w-[44px] flex-shrink-0`}
              title="Voice message"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => setShowEmojiPicker(!showEmojiPicker)}
              className={`${isCompact ? "w-8 h-8 xs:w-9 xs:h-9" : "w-9 h-9 xs:w-10 xs:h-10 sm:w-11 sm:h-11 md:w-10 md:h-10"} rounded-full flex items-center justify-center transition-colors text-sm xs:text-base sm:text-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50 active:bg-blue-100 touch-manipulation min-h-[44px] min-w-[44px] flex-shrink-0`}
            >
              😊
            </button>
            {onSendImage && (
              <button
                type="button"
                onClick={handleImageButtonClick}
                className={`${isCompact ? "w-8 h-8 xs:w-9 xs:h-9" : "w-9 h-9 xs:w-10 xs:h-10 sm:w-11 sm:h-11 md:w-10 md:h-10"} rounded-full flex items-center justify-center transition-colors text-sm xs:text-base sm:text-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50 active:bg-blue-100 touch-manipulation min-h-[44px] min-w-[44px] flex-shrink-0`}
                title="Rasm yuborish"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </button>
            )}
          </>
        )}

        {/* Message Input */}
        <div className="flex-1 relative min-w-0">
          <textarea
            ref={inputRef}
            value={message}
            onChange={(e) => handleTyping(e.target.value)}
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
