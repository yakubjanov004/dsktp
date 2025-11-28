"use client"

import { useState, useEffect } from "react"
import type { Message } from "../../lib/api"
import { useChat } from "../../context/ChatContext"
import { forwardMessage } from "../../lib/api"

interface ForwardModalProps {
  message: Message
  isOpen: boolean
  onClose: () => void
  currentChatId: string
}

export default function ForwardModal({
  message,
  isOpen,
  onClose,
  currentChatId
}: ForwardModalProps) {
  const { chatSessions, users, telegramId } = useChat()
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null)
  const [isForwarding, setIsForwarding] = useState(false)

  // Filter out current chat from available chats
  const availableChats = chatSessions.filter(chat => chat.id !== currentChatId)

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedChatId(null)
      setIsForwarding(false)
    }
  }, [isOpen])

  const handleForward = async () => {
    if (!selectedChatId || !telegramId) return

    setIsForwarding(true)
    try {
      const result = await forwardMessage(
        parseInt(currentChatId),
        message.id,
        parseInt(selectedChatId),
        telegramId
      )

      if (result?.success) {
        onClose()
      }
    } catch (error) {
      console.error("Error forwarding message:", error)
    } finally {
      setIsForwarding(false)
    }
  }

  if (!isOpen) return null

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-lg shadow-xl w-full max-w-md max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Xabarni forward qilish</h2>
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

        {/* Message Preview */}
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
          <div className="text-sm text-gray-600 mb-2">Forward qilinadigan xabar:</div>
          <div className="bg-white rounded-lg p-3 border border-gray-200">
            <div className="text-sm text-gray-700 line-clamp-3">
              {message.message_text}
            </div>
          </div>
        </div>

        {/* Chat List */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {availableChats.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              Boshqa chatlar topilmadi
            </div>
          ) : (
            <div className="space-y-2">
              {availableChats.map((chat) => {
                const chatUser = users.find(u => 
                  u.id.toString() === (chat.clientId || chat.operatorId || "")
                )
                const chatName = chatUser?.full_name || chat.clientName || chat.operatorName || "Noma'lum"

                return (
                  <button
                    key={chat.id}
                    onClick={() => setSelectedChatId(chat.id)}
                    className={`w-full text-left p-3 rounded-lg transition-colors border ${
                      selectedChatId === chat.id
                        ? "bg-blue-50 border-blue-500"
                        : "border-gray-200 hover:bg-gray-50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold">
                          {chatName[0]?.toUpperCase() || "?"}
                        </div>
                        <div>
                          <div className="font-medium text-gray-900">{chatName}</div>
                          <div className="text-xs text-gray-500">
                            {chat.status === "active" ? "Faol" : "Nofaol"}
                          </div>
                        </div>
                      </div>
                      {selectedChatId === chat.id && (
                        <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-end space-x-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg font-medium transition-colors bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
          >
            Bekor qilish
          </button>
          <button
            onClick={handleForward}
            disabled={!selectedChatId || isForwarding}
            className="px-4 py-2 rounded-lg font-medium transition-colors bg-blue-500 text-white hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {isForwarding ? "Forward qilinmoqda..." : "Forward qilish"}
          </button>
        </div>
      </div>
    </div>
  )
}

