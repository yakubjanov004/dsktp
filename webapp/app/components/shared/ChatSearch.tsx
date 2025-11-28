"use client"

import { useState, useEffect, useRef } from "react"
import type { Message } from "../../lib/api"
import { searchChatMessages } from "../../lib/api"
import { useChat } from "../../context/ChatContext"

interface ChatSearchProps {
  chatId: string
  isOpen: boolean
  onClose: () => void
  onSelectMessage: (messageId: number) => void
}

export default function ChatSearch({
  chatId,
  isOpen,
  onClose,
  onSelectMessage
}: ChatSearchProps) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<Message[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const { telegramId } = useChat()

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  // Reset when modal closes
  useEffect(() => {
    if (!isOpen) {
      setQuery("")
      setResults([])
    }
  }, [isOpen])

  // Debounced search
  useEffect(() => {
    if (!isOpen || !query.trim() || !telegramId) {
      setResults([])
      return
    }

    const timeoutId = setTimeout(async () => {
      setIsSearching(true)
      
      const chatIdNum = parseInt(chatId)
      const result = await searchChatMessages(chatIdNum, query.trim(), telegramId, 50)
      
      setResults(result?.results || [])
      setIsSearching(false)
    }, 300)

    return () => clearTimeout(timeoutId)
  }, [query, chatId, telegramId, isOpen])

  const handleSelectMessage = (message: Message) => {
    onSelectMessage(message.id)
    onClose()
  }

  const highlightText = (text: string, query: string): string => {
    if (!query.trim()) return text
    
    const escaped = query.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regex = new RegExp(`(${escaped})`, 'gi')
    const parts = text.split(regex)
    
    return parts.map((part) => {
      return regex.test(part) 
        ? `<mark class="bg-yellow-200 text-yellow-900">${part}</mark>`
        : part
    }).join('')
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-20 md:pt-24 bg-black bg-opacity-50" onClick={onClose}>
      <div 
        className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Xabarlarni qidirish</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Yopish"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Search Input */}
        <div className="px-4 py-3 border-b border-gray-200">
          <div className="relative">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Qidirish..."
              className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <svg
              className="absolute left-3 top-2.5 w-5 h-5 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            {isSearching && (
              <div className="absolute right-3 top-2.5">
                <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            )}
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {!query.trim() ? (
            <div className="text-center text-gray-500 py-8">
              Xabarlarni qidirish uchun so'z kiriting
            </div>
          ) : isSearching ? (
            <div className="text-center text-gray-500 py-8">Qidirilmoqda...</div>
          ) : results.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              Hech qanday natija topilmadi
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-sm text-gray-600 mb-3">
                {results.length} ta natija topildi
              </div>
              {results.map((message) => (
                <button
                  key={message.id}
                  onClick={() => handleSelectMessage(message)}
                  className="w-full text-left p-3 rounded-lg hover:bg-blue-50 transition-colors border border-gray-200"
                >
                  <div className="flex items-start justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700">
                      {message.sender_name || "Noma'lum"}
                    </span>
                    <span className="text-xs text-gray-500">
                      {new Date(message.created_at).toLocaleString("uz-UZ", {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit"
                      })}
                    </span>
                  </div>
                  <div
                    className="text-sm text-gray-900 line-clamp-2"
                    dangerouslySetInnerHTML={{
                      __html: highlightText(message.message_text || "", query)
                    }}
                  />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

