"use client"

import { useState, useEffect } from "react"

export default function WelcomeScreen({ onContinue, user, isDarkMode }) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    setIsVisible(true)
  }, [])

  return (
    <div
      className={`min-h-screen flex flex-col items-center justify-center p-6 transition-all duration-1000 ${
        isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
      } ${isDarkMode ? "bg-gray-900 text-white" : "bg-gradient-to-br from-blue-50 to-indigo-100 text-gray-800"}`}
    >
      <div className="text-center max-w-sm">
        {/* Telegram Logo */}
        <div className="mb-8 relative">
          <div
            className={`w-24 h-24 mx-auto rounded-full flex items-center justify-center text-4xl font-bold transition-all duration-500 ${
              isDarkMode ? "bg-blue-600 text-white" : "bg-blue-500 text-white"
            } shadow-lg hover:shadow-xl transform hover:scale-105`}
          >
            <svg viewBox="0 0 24 24" className="w-12 h-12 fill-current">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
            </svg>
          </div>
          <div className="absolute -bottom-2 -right-2 w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
            <span className="text-white text-xs">✓</span>
          </div>
        </div>

        {/* Welcome Text */}
        <h1 className={`text-3xl font-bold mb-4 ${isDarkMode ? "text-white" : "text-gray-800"}`}>
          Telegram Web Chat ga xush kelibsiz
        </h1>

        <p className={`text-lg mb-2 ${isDarkMode ? "text-gray-300" : "text-gray-600"}`}>
          Salom, <span className="font-semibold text-blue-500">{user?.first_name || "Foydalanuvchi"}</span>!
        </p>

        <p className={`mb-8 leading-relaxed ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
          Telegram WebApp uchun maxsus yaratilgan zamonaviy, chiroyli chat interfeysi bilan uzluksiz xabar almashish tajribasini boshqang.
        </p>

        {/* Features */}
        <div className="mb-8 space-y-3">
          {[
            { icon: "💬", text: "Real vaqtda xabar almashish" },
            { icon: "🌙", text: "Qorong'i rejim qo'llab-quvvatlash" },
            { icon: "📱", text: "Mobil qurilmalarga moslashgan" },
          ].map((feature, index) => (
            <div
              key={index}
              className={`flex items-center justify-center space-x-3 p-3 rounded-lg transition-all duration-300 ${
                isDarkMode ? "bg-gray-800 hover:bg-gray-700" : "bg-white hover:bg-gray-50"
              } shadow-sm hover:shadow-md`}
              style={{ animationDelay: `${index * 200}ms` }}
            >
              <span className="text-2xl">{feature.icon}</span>
              <span className={`font-medium ${isDarkMode ? "text-gray-200" : "text-gray-700"}`}>{feature.text}</span>
            </div>
          ))}
        </div>

        {/* Continue Button */}
        <button
          onClick={onContinue}
          className={`w-full py-4 px-6 rounded-xl font-semibold text-lg transition-all duration-300 transform hover:scale-105 active:scale-95 ${
            isDarkMode
              ? "bg-blue-600 hover:bg-blue-700 text-white shadow-lg hover:shadow-xl"
              : "bg-blue-500 hover:bg-blue-600 text-white shadow-lg hover:shadow-xl"
          }`}
        >
          Chatlashishni boshlash
        </button>
      </div>
    </div>
  )
}
