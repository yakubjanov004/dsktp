"use client"

import { useState, useEffect } from "react"

export default function MessageBubble({ message, isDarkMode, isNew }) {
  const [isVisible, setIsVisible] = useState(!isNew)
  const isUser = message.sender === "user"

  useEffect(() => {
    if (isNew) {
      const timer = setTimeout(() => setIsVisible(true), 100)
      return () => clearTimeout(timer)
    }
  }, [isNew])

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
  }

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} transition-all duration-500 ${
        isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
      }`}
    >
      <div
        className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl shadow-sm relative ${
          isUser
            ? isDarkMode
              ? "bg-blue-600 text-white"
              : "bg-blue-500 text-white"
            : isDarkMode
              ? "bg-gray-700 text-white"
              : "bg-white text-gray-800"
        } ${isUser ? "rounded-br-md" : "rounded-bl-md"}`}
      >
        {/* Message Text */}
        <p className="text-sm leading-relaxed break-words">{message.text}</p>

        {/* Timestamp */}
        <div
          className={`flex items-center justify-end mt-2 space-x-1 ${
            isUser ? "text-blue-100" : isDarkMode ? "text-gray-400" : "text-gray-500"
          }`}
        >
          <span className="text-xs">{formatTime(message.timestamp)}</span>

          {/* Read Receipt for User Messages */}
          {isUser && (
            <svg className="w-4 h-4 opacity-70" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
          )}
        </div>

        {/* Message Tail */}
        <div
          className={`absolute top-0 w-4 h-4 ${
            isUser ? "-right-2 transform rotate-45" : "-left-2 transform -rotate-45"
          } ${isUser ? (isDarkMode ? "bg-blue-600" : "bg-blue-500") : isDarkMode ? "bg-gray-700" : "bg-white"}`}
          style={{
            clipPath: isUser ? "polygon(0 0, 0 100%, 100% 100%)" : "polygon(0 100%, 100% 0, 100% 100%)",
          }}
        ></div>
      </div>
    </div>
  )
}
