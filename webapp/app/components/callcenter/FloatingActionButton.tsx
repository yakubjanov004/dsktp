"use client"

import { useState } from "react"
import { useChat } from "../../context/ChatContext"

interface FloatingActionButtonProps {
  isDarkMode: boolean
  onNewChat?: () => void
  onSearch?: () => void
  onStatistics?: () => void
}

export default function FloatingActionButton({ 
  isDarkMode, 
  onNewChat, 
  onSearch, 
  onStatistics 
}: FloatingActionButtonProps) {
  const [isOpen, setIsOpen] = useState(false)
  const { startNewChat, chatSessions, users } = useChat()

  const handleNewChat = () => {
    if (onNewChat) {
      onNewChat()
    } else {
      // Fallback to internal logic
      const clients = users.filter(user => user.role === "client")
      const randomClient = clients[Math.floor(Math.random() * clients.length)]
      
      if (randomClient) {
        const chatTypes = [
          "Umumiy yordam so'rovi",
          "Texnik muammo",
          "To'lov savoli", 
          "Funksiya so'rovi"
        ]
        const randomType = chatTypes[Math.floor(Math.random() * chatTypes.length)]
        
        startNewChat(randomClient.id, randomType)
      }
    }
    setIsOpen(false)
  }

  const handleSearch = () => {
    if (onSearch) {
      onSearch()
    } else {
      // Fallback to internal logic
      const searchTerm = prompt("Qidirish so'zini kiriting:")
      if (searchTerm) {
        const filteredChats = chatSessions.filter(chat => 
          (chat.clientName?.toLowerCase().includes(searchTerm.toLowerCase()) || false) ||
          chat.messages.some(msg => msg.text.toLowerCase().includes(searchTerm.toLowerCase()))
        )
        
        alert(`"${searchTerm}" uchun ${filteredChats.length} ta natija topildi`)
      }
    }
    setIsOpen(false)
  }

  const handleReports = () => {
    if (onStatistics) {
      onStatistics()
    } else {
      // Fallback to internal logic
      const totalChats = chatSessions.length
      const activeChats = chatSessions.filter(chat => chat.status === "active").length
      const closedChats = chatSessions.filter(chat => chat.status === "closed").length
      
      const report = `
📊 Call Center Hisoboti

📈 Umumiy statistika:
• Jami chatlar: ${totalChats}
• Faol chatlar: ${activeChats}
• Yopilgan chatlar: ${closedChats}
• O'rtacha javob vaqti: 2.5 daqiqa

📅 Bugungi faoliyat:
• Yangi chatlar: ${Math.floor(Math.random() * 10) + 5}
• Yopilgan chatlar: ${Math.floor(Math.random() * 5) + 2}
• Mijozlar soni: ${users.filter(u => u.role === "client").length}

🎯 KPI ko'rsatkichlari:
• Mijoz mamnuniyati: ${Math.floor(Math.random() * 20) + 80}%
• O'rtacha chat vaqti: ${Math.floor(Math.random() * 30) + 15} daqiqa
• Birinchi javob vaqti: ${Math.floor(Math.random() * 5) + 1} daqiqa
      `
      
      alert(report)
    }
    setIsOpen(false)
  }

  const quickActions = [
    { 
      icon: "➕", 
      label: "Yangi chat", 
      action: handleNewChat,
      color: "bg-blue-500 hover:bg-blue-600"
    },
    { 
      icon: "🔍", 
      label: "Qidirish", 
      action: handleSearch,
      color: "bg-green-500 hover:bg-green-600"
    },
    { 
      icon: "📊", 
      label: "Hisobotlar", 
      action: handleReports,
      color: "bg-purple-500 hover:bg-purple-600"
    },
  ]

  return (
    <div className="fixed bottom-4 sm:bottom-6 left-4 sm:left-6 z-50">
      {/* Quick Actions */}
      {isOpen && (
        <div className="absolute bottom-12 sm:bottom-16 left-0 space-y-2 sm:space-y-3 animate-scale-in">
          {quickActions.map((action, index) => (
            <button
              key={index}
              onClick={action.action}
              className={`
                flex items-center space-x-2 sm:space-x-3 px-3 sm:px-4 py-2 sm:py-3 rounded-full shadow-lg transition-all duration-200 transform hover:scale-105 text-white text-sm sm:text-base
                ${action.color}
              `}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <span className="text-base sm:text-lg">{action.icon}</span>
              <span className="font-medium whitespace-nowrap">{action.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Main FAB */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          w-12 h-12 sm:w-14 sm:h-14 rounded-full shadow-lg transition-all duration-200 transform hover:scale-110 active:scale-95
          ${isDarkMode ? "bg-purple-600 hover:bg-purple-700" : "bg-purple-500 hover:bg-purple-600"}
          text-white text-lg sm:text-xl font-bold
          ${isOpen ? "rotate-45" : "rotate-0"}
        `}
      >
        {isOpen ? "✕" : "⚡"}
      </button>
    </div>
  )
}
