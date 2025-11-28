"use client"

import { useState, useEffect, useCallback } from "react"
import type { Message } from "../../lib/api"
import { getChatMedia } from "../../lib/api"

interface MediaGalleryProps {
  chatId: string
  telegramId: number
  isOpen: boolean
  onClose: () => void
}

export default function MediaGallery({ chatId, telegramId, isOpen, onClose }: MediaGalleryProps) {
  const [media, setMedia] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedMedia, setSelectedMedia] = useState<Message | null>(null)
  const [mediaType, setMediaType] = useState<"all" | "image" | "video">("all")

  const loadMedia = useCallback(async () => {
    setIsLoading(true)
    try {
      const result = await getChatMedia(
        parseInt(chatId),
        telegramId,
        mediaType === "all" ? undefined : mediaType,
        200
      )
      if (result?.media) {
        setMedia(result.media)
      }
    } catch (error) {
      console.error("Error loading media:", error)
    } finally {
      setIsLoading(false)
    }
  }, [chatId, telegramId, mediaType])

  useEffect(() => {
    if (isOpen) {
      loadMedia()
    } else {
      setMedia([])
      setSelectedMedia(null)
      setMediaType("all")
    }
  }, [isOpen, loadMedia])

  const getMediaUrl = (attachments: any): string | null => {
    if (!attachments || typeof attachments !== "object") return null
    return attachments.url || attachments.image || attachments.video || null
  }

  const isImage = (attachments: any): boolean => {
    if (!attachments) return false
    return attachments.type === "image" || attachments.image !== undefined
  }

  const isVideo = (attachments: any): boolean => {
    if (!attachments) return false
    return attachments.type === "video" || attachments.video !== undefined
  }

  const normalizeUrl = (url: string | null): string => {
    if (!url) return ""
    if (url.startsWith("http")) return url
    return url.startsWith("/") ? `/api${url}` : `/api/${url}`
  }

  if (!isOpen) return null

  return (
    <>
      {/* Gallery Modal */}
      <div
        className="fixed inset-0 z-50 bg-black bg-opacity-90 flex flex-col"
        onClick={onClose}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <h2 className="text-lg font-semibold text-white">Media Gallery</h2>
            <span className="text-sm text-gray-400">({media.length})</span>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-800 transition-colors text-white"
            aria-label="Yopish"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Filter Tabs */}
        <div className="px-4 py-2 border-b border-gray-700 flex items-center space-x-2">
          {(["all", "image", "video"] as const).map((type) => (
            <button
              key={type}
              onClick={() => setMediaType(type)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                mediaType === type
                  ? "bg-blue-500 text-white"
                  : "bg-gray-800 text-gray-300 hover:bg-gray-700"
              }`}
            >
              {type === "all" ? "Barchasi" : type === "image" ? "Rasmlar" : "Videolar"}
            </button>
          ))}
        </div>

        {/* Media Grid */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-white">Yuklanmoqda...</div>
            </div>
          ) : media.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-gray-400">Media topilmadi</div>
            </div>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-2">
              {media.map((message) => {
                const attachments = message.attachments
                const mediaUrl = getMediaUrl(attachments)
                if (!mediaUrl) return null

                const isImg = isImage(attachments)
                const isVid = isVideo(attachments)

                return (
                  <div
                    key={message.id}
                    className="relative aspect-square bg-gray-800 rounded-lg overflow-hidden cursor-pointer hover:opacity-80 transition-opacity"
                    onClick={() => setSelectedMedia(message)}
                  >
                    {isImg ? (
                      <img
                        src={normalizeUrl(mediaUrl)}
                        alt="Media"
                        className="w-full h-full object-cover"
                      />
                    ) : isVid ? (
                      <div className="w-full h-full flex items-center justify-center bg-gray-900">
                        <svg className="w-12 h-12 text-white" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                      </div>
                    ) : null}
                    {isVid && (
                      <div className="absolute bottom-1 right-1 bg-black bg-opacity-50 px-1.5 py-0.5 rounded text-xs text-white">
                        Video
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Full-screen Preview Modal */}
      {selectedMedia && (
        <div
          className="fixed inset-0 z-[60] bg-black flex items-center justify-center"
          onClick={() => setSelectedMedia(null)}
        >
          <button
            onClick={() => setSelectedMedia(null)}
            className="absolute top-4 right-4 p-2 rounded-lg bg-black bg-opacity-50 hover:bg-opacity-70 text-white z-10"
            aria-label="Yopish"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <div className="max-w-7xl max-h-[90vh] w-full h-full flex items-center justify-center p-4">
            {(() => {
              const attachments = selectedMedia.attachments
              const mediaUrl = getMediaUrl(attachments)
              if (!mediaUrl) return null

              if (isImage(attachments)) {
                return (
                  <img
                    src={normalizeUrl(mediaUrl)}
                    alt="Preview"
                    className="max-w-full max-h-full object-contain"
                    onClick={(e) => e.stopPropagation()}
                  />
                )
              }
              if (isVideo(attachments)) {
                return (
                  <video
                    src={normalizeUrl(mediaUrl)}
                    controls
                    className="max-w-full max-h-full"
                    onClick={(e) => e.stopPropagation()}
                  />
                )
              }
              return null
            })()}
          </div>

          {/* Navigation Arrows */}
          {media.length > 1 && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  const currentIndex = media.findIndex(m => m.id === selectedMedia.id)
                  const prevIndex = currentIndex > 0 ? currentIndex - 1 : media.length - 1
                  setSelectedMedia(media[prevIndex])
                }}
                className="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black bg-opacity-50 hover:bg-opacity-70 text-white z-10"
                aria-label="Oldingi"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  const currentIndex = media.findIndex(m => m.id === selectedMedia.id)
                  const nextIndex = currentIndex < media.length - 1 ? currentIndex + 1 : 0
                  setSelectedMedia(media[nextIndex])
                }}
                className="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black bg-opacity-50 hover:bg-opacity-70 text-white z-10"
                aria-label="Keyingi"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </>
          )}
        </div>
      )}
    </>
  )
}

