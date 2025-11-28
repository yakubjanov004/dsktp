"use client"

import { useState, useRef, useEffect } from "react"

interface VoiceMessageProps {
  audioUrl: string
  isOwnMessage: boolean
  telegramId?: number
}

export default function VoiceMessage({ audioUrl, isOwnMessage, telegramId }: VoiceMessageProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [audioDuration, setAudioDuration] = useState(0)
  const audioRef = useRef<HTMLAudioElement>(null)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const updateTime = () => setCurrentTime(audio.currentTime)
    const updateDuration = () => setAudioDuration(audio.duration)
    const handleEnded = () => setIsPlaying(false)

    audio.addEventListener("timeupdate", updateTime)
    audio.addEventListener("loadedmetadata", updateDuration)
    audio.addEventListener("ended", handleEnded)

    return () => {
      audio.removeEventListener("timeupdate", updateTime)
      audio.removeEventListener("loadedmetadata", updateDuration)
      audio.removeEventListener("ended", handleEnded)
    }
  }, [])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return

    if (isPlaying) {
      audio.pause()
    } else {
      audio.play()
    }
    setIsPlaying(!isPlaying)
  }

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  const progress = audioDuration > 0 ? (currentTime / audioDuration) * 100 : 0

  // Ensure audio URL is absolute with telegram_id for authorization
  const getAudioSrc = () => {
    if (audioUrl.startsWith("http")) return audioUrl
    let url = audioUrl.startsWith("/api") ? audioUrl : `/api${audioUrl.startsWith("/") ? "" : "/"}${audioUrl}`
    if (telegramId) {
      url += `${url.includes("?") ? "&" : "?"}telegram_id=${telegramId}`
    }
    return url
  }

  return (
    <div className="flex items-center space-x-2 min-w-[200px] max-w-[300px]">
      <audio ref={audioRef} src={getAudioSrc()} preload="metadata" />
      
      <button
        onClick={togglePlay}
        className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
          isOwnMessage
            ? "bg-blue-400 hover:bg-blue-300 text-white"
            : "bg-blue-100 hover:bg-blue-200 text-blue-600"
        }`}
      >
        {isPlaying ? (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
          </svg>
        ) : (
          <svg className="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
        )}
      </button>

      <div className="flex-1 min-w-0">
        <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`absolute top-0 left-0 h-full transition-all ${
              isOwnMessage ? "bg-blue-300" : "bg-blue-400"
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className={`text-xs mt-1 ${isOwnMessage ? "text-blue-100" : "text-blue-600"}`}>
          {formatTime(currentTime)} / {formatTime(audioDuration)}
        </div>
      </div>
    </div>
  )
}

