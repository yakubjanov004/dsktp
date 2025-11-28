"use client"

import { useState, useEffect } from "react"
import type { Message } from "../../lib/api"
import ReactionPicker from "./ReactionPicker"
import ForwardModal from "./ForwardModal"
import VoiceMessage from "./VoiceMessage"
import { toggleMessageReaction, editMessage, markMessageRead, getMessageReads, type MessageRead } from "../../lib/api"
import { useChat } from "../../context/ChatContext"

interface MessageBubbleProps {
  message: Message
  isOwnMessage: boolean
  isDarkMode: boolean
  isNew: boolean
  senderName: string
  showSenderName?: boolean  // Always show sender name (for supervisor view)
}

export default function MessageBubble({ message, isOwnMessage, isDarkMode, isNew, senderName, showSenderName = false }: MessageBubbleProps) {
  const { telegramId } = useChat()
  const [isVisible, setIsVisible] = useState(!isNew)
  const [showReactionPicker, setShowReactionPicker] = useState(false)
  const [showForwardModal, setShowForwardModal] = useState(false)
  const [reactions, setReactions] = useState(message.reactions || [])
  const [isEditing, setIsEditing] = useState(false)
  const [editText, setEditText] = useState(message.message_text || "")
  const [isSaving, setIsSaving] = useState(false)
  const [readCount, setReadCount] = useState(message.read_count || 0)
  const [showReadList, setShowReadList] = useState(false)
  const [readList, setReadList] = useState<MessageRead[]>([])

  useEffect(() => {
    if (isNew) {
      const timer = setTimeout(() => setIsVisible(true), 100)
      return () => clearTimeout(timer)
    }
  }, [isNew])

  // Update reactions when message changes
  useEffect(() => {
    if (message.reactions) {
      setReactions(message.reactions)
    }
  }, [message.reactions])

  // Update editText when message changes (if not editing)
  useEffect(() => {
    if (!isEditing) {
      setEditText(message.message_text || "")
    }
  }, [message.message_text, isEditing])

  // Update read count when message changes
  useEffect(() => {
    setReadCount(message.read_count || 0)
  }, [message.read_count])

  // Load read list when showing
  useEffect(() => {
    if (showReadList && isOwnMessage && message.id && telegramId) {
      if (readList.length === 0) {
        getMessageReads(message.chat_id, message.id, telegramId).then(result => {
          if (result?.reads) {
            setReadList(result.reads)
          }
        }).catch(console.error)
      }
    } else if (!showReadList) {
      setReadList([]) // Clear when closing
    }
  }, [showReadList, isOwnMessage, message.id, message.chat_id, telegramId])


  const formatTime = (timestamp: string | Date) => {
    const date = typeof timestamp === "string" ? new Date(timestamp) : timestamp
    return date.toLocaleTimeString("uz-UZ", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
  }

  const handleReactionSelect = async (emoji: string) => {
    if (!telegramId) return
    
    setShowReactionPicker(false)
    
    const result = await toggleMessageReaction(
      message.chat_id,
      message.id,
      emoji,
      telegramId
    )
    
    if (result?.reactions) {
      setReactions(result.reactions)
    }
  }

  const handleEdit = () => {
    setIsEditing(true)
    setEditText(message.message_text || "")
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditText(message.message_text || "")
  }

  const handleSaveEdit = async () => {
    if (!telegramId || !editText.trim() || editText.trim() === message.message_text) {
      setIsEditing(false)
      return
    }

    setIsSaving(true)
    try {
      const result = await editMessage(
        message.chat_id,
        message.id,
        editText.trim(),
        telegramId
      )
      
      if (result?.success) {
        setIsEditing(false)
      }
    } catch (error) {
      console.error("Error editing message:", error)
    } finally {
      setIsSaving(false)
    }
  }
  
  // Get message text - handle both old and new format
  const messageText = message.message_text || ""
  const messageTimestamp = message.created_at || new Date()

  // Check if message can be edited (within 15 minutes)
  const canEdit = isOwnMessage && (() => {
    if (!message.created_at) return false
    const created = new Date(message.created_at)
    const now = new Date()
    const diffMinutes = (now.getTime() - created.getTime()) / (1000 * 60)
    return diffMinutes <= 15
  })()

  return (
    <div
      data-message-id={message.id}
      data-is-own={isOwnMessage.toString()}
      className={`flex w-full ${isOwnMessage ? "justify-end" : "justify-start"} transition-all duration-500 ${
        isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
      }`}
    >
      <div
        className={`inline-block w-fit max-w-[85%] sm:max-w-[80%] md:max-w-[75%] lg:max-w-[70%] px-2.5 xs:px-3 sm:px-3.5 md:px-4 lg:px-5 py-2 xs:py-2.5 sm:py-2.5 md:py-3 lg:py-3.5 rounded-2xl shadow-sm relative group ${
          isOwnMessage
            ? "bg-blue-500 text-white"
            : "bg-white text-blue-900 border border-blue-200"
        } ${isOwnMessage ? "rounded-br-md" : "rounded-bl-md"}`}
      >
        {/* Forwarded Indicator */}
        {message.forwarded_from_message_id && (
          <div className={`text-[10px] xs:text-xs mb-1 flex items-center gap-1 ${
            isOwnMessage ? "text-blue-200" : "text-blue-500"
          }`}>
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span>Forwarded</span>
          </div>
        )}

        {/* Sender Name (for group chats, multi-agent, or supervisor view) */}
        {((showSenderName && senderName) || (!isOwnMessage && senderName)) && (
          <p className={`text-[10px] xs:text-xs sm:text-xs md:text-sm font-medium mb-0.5 xs:mb-1 sm:mb-1 ${
            isOwnMessage ? "text-blue-100" : "text-blue-600"
          }`}>{senderName}</p>
        )}

        {/* Message Content */}
        <div className="space-y-1.5 xs:space-y-2 sm:space-y-2">
          {/* Edit Mode */}
          {isEditing && isOwnMessage ? (
            <div className="space-y-2">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className="w-full px-2 py-1.5 rounded-lg text-sm bg-white text-blue-900 border border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                rows={3}
                autoFocus
                disabled={isSaving}
              />
              <div className="flex items-center justify-end space-x-2">
                <button
                  onClick={handleCancelEdit}
                  disabled={isSaving}
                  className="px-3 py-1 text-xs font-medium text-blue-600 hover:text-blue-700 disabled:opacity-50"
                >
                  Bekor qilish
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={isSaving || !editText.trim()}
                  className="px-3 py-1 text-xs font-medium bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? "Saqlanmoqda..." : "Saqlash"}
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Show message text - default to text if message_text exists */}
              {messageText && (
                <p className="text-sm xs:text-sm sm:text-sm md:text-base lg:text-base leading-relaxed break-words whitespace-pre-wrap word-wrap overflow-wrap-anywhere">{messageText}</p>
              )}
            </>
          )}

          {/* Handle attachments if present */}
          {message.attachments && typeof message.attachments === 'object' && (
            <>
              {message.attachments.type === "voice" && message.attachments.url && (
                <VoiceMessage
                  audioUrl={message.attachments.url}
                  isOwnMessage={isOwnMessage}
                  telegramId={telegramId}
                />
              )}
              {message.attachments.image && (
                <div className="rounded-lg overflow-hidden max-w-full">
                  <img 
                    src={message.attachments.image || "/placeholder.svg"} 
                    alt="Ulashilgan rasm" 
                    className="max-w-full h-auto w-full object-contain rounded-lg" 
                  />
                </div>
              )}
              {message.attachments.file && message.attachments.type !== "voice" && (
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

        {/* Reactions */}
        {reactions.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5 xs:mt-2 sm:mt-2">
            {reactions.map((reaction, index) => (
              <button
                key={`${reaction.emoji}-${index}`}
                onClick={() => handleReactionSelect(reaction.emoji)}
                className={`px-1.5 xs:px-2 sm:px-2.5 py-0.5 xs:py-1 rounded-full text-xs xs:text-sm flex items-center gap-1 transition-all hover:scale-105 ${
                  isOwnMessage
                    ? "bg-blue-400/30 text-blue-100 border border-blue-300/30"
                    : "bg-blue-50 text-blue-700 border border-blue-200"
                }`}
              >
                <span>{reaction.emoji}</span>
                <span className="font-medium">{reaction.count}</span>
              </button>
            ))}
          </div>
        )}

        {/* Action Buttons */}
        <div className="relative mt-1.5 xs:mt-2 sm:mt-2 flex items-center gap-2">
          <button
            onClick={() => setShowReactionPicker(!showReactionPicker)}
            className={`opacity-0 group-hover:opacity-100 transition-opacity text-lg xs:text-xl sm:text-xl ${
              isOwnMessage ? "text-blue-100" : "text-blue-600"
            }`}
          >
            😊
          </button>
          {canEdit && !isEditing && (
            <button
              onClick={handleEdit}
              className={`opacity-0 group-hover:opacity-100 transition-opacity text-lg xs:text-xl sm:text-xl ${
                isOwnMessage ? "text-blue-100" : "text-blue-600"
              }`}
              title="Tahrirlash"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
          )}
          <button
            onClick={() => setShowForwardModal(true)}
            className={`opacity-0 group-hover:opacity-100 transition-opacity text-lg xs:text-xl sm:text-xl ${
              isOwnMessage ? "text-blue-100" : "text-blue-600"
            }`}
            title="Forward qilish"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </button>
          {showReactionPicker && (
            <ReactionPicker
              onSelect={handleReactionSelect}
              onClose={() => setShowReactionPicker(false)}
            />
          )}
        </div>

        {/* Timestamp and Status */}
        <div
          className={`flex items-center justify-end mt-1.5 xs:mt-2 sm:mt-2 space-x-1 text-[10px] xs:text-xs sm:text-xs opacity-70 group-hover:opacity-100 transition-opacity ${
            isOwnMessage ? "text-blue-100" : "text-blue-600"
          }`}
        >
          {message.edited_at && (
            <span className="italic">(tahrirlangan)</span>
          )}
          <span>{formatTime(messageTimestamp)}</span>

          {/* Read Receipt for Own Messages */}
          {isOwnMessage && (
            <div className="relative">
              <button
                onClick={() => setShowReadList(!showReadList)}
                className="flex space-x-0.5 xs:space-x-1 hover:opacity-80 transition-opacity"
                title={readCount > 0 ? `${readCount} o'qilgan` : "Yuborildi"}
              >
                {readCount > 0 ? (
                  // Blue double check (read)
                  <svg className="w-3 h-3 xs:w-3.5 xs:h-3.5 sm:w-4 sm:h-4 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                ) : (
                  // Single check (sent)
                  <svg className="w-3 h-3 xs:w-3.5 xs:h-3.5 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
              
              {/* Read List Modal */}
              {showReadList && (
                <div className="absolute bottom-full right-0 mb-2 bg-white border border-blue-200 rounded-lg shadow-lg p-2 min-w-[200px] z-50">
                  <div className="text-xs font-semibold text-blue-900 mb-2">O'qilgan:</div>
                  {readList.length > 0 ? (
                    <div className="space-y-1 max-h-40 overflow-y-auto">
                      {readList.map((read) => (
                        <div key={read.user_id} className="text-xs text-blue-700">
                          <div className="font-medium">{read.user_name || "Foydalanuvchi"}</div>
                          <div className="text-blue-500">
                            {new Date(read.read_at).toLocaleString("uz-UZ", {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-blue-500">Yuklanmoqda...</div>
                  )}
                </div>
              )}
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

      {/* Forward Modal */}
      {showForwardModal && (
        <ForwardModal
          message={message}
          isOpen={showForwardModal}
          onClose={() => setShowForwardModal(false)}
          currentChatId={message.chat_id.toString()}
        />
      )}
    </div>
  )
}
