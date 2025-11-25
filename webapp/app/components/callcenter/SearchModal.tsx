"use client"

import { useState, useEffect } from "react"
import { useChat } from "../../context/ChatContext"

interface SearchModalProps {
  isOpen: boolean
  onClose: () => void
  isDarkMode: boolean
}

export default function SearchModal({ isOpen, onClose, isDarkMode }: SearchModalProps) {
  const { chatSessions, users } = useChat()
  const [searchTerm, setSearchTerm] = useState("")
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searchType, setSearchType] = useState("all")
  const [isSearching, setIsSearching] = useState(false)

  useEffect(() => {
    if (searchTerm.trim()) {
      performSearch()
    } else {
      setSearchResults([])
    }
  }, [searchTerm, searchType])

  const performSearch = () => {
    setIsSearching(true)
    
    // Simulate search delay
    setTimeout(() => {
      const results = chatSessions.filter(chat => {
        const matchesTerm = 
          (chat.clientName?.toLowerCase().includes(searchTerm.toLowerCase()) || false) ||
          chat.messages.some(msg => msg.text.toLowerCase().includes(searchTerm.toLowerCase()))
        
        if (searchType === "all") return matchesTerm
        if (searchType === "active") return matchesTerm && chat.status === "active"
        if (searchType === "closed") return matchesTerm && chat.status === "closed"
        
        return matchesTerm
      })

      setSearchResults(results)
      setIsSearching(false)
    }, 500)
  }

  const getClientName = (clientId: string) => {
    const client = users.find(u => u.id === clientId)
    return client?.name || "Noma'lum mijoz"
  }

  const formatDate = (date: Date) => {
    return new Date(date).toLocaleDateString("uz-UZ", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    })
  }

  const highlightText = (text: string, term: string) => {
    if (!term) return text
    const regex = new RegExp(`(${term})`, 'gi')
    return text.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-800">$1</mark>')
  }

  const SearchResultCard = ({ chat, index }: { chat: any, index: number }) => {
    const client = users.find(u => u.id === chat.clientId)
    const lastMessage = chat.messages[chat.messages.length - 1]
    
    return (
      <div
        className={`p-4 rounded-xl border transition-all duration-200 hover:shadow-lg ${
          isDarkMode ? "bg-gray-800 border-gray-700 hover:bg-gray-750" : "bg-white border-gray-200 hover:bg-gray-50"
        }`}
        style={{ animationDelay: `${index * 100}ms` }}
      >
        <div className="flex items-start space-x-4">
          {/* Avatar */}
          <div className="relative">
            <img
              src={client?.avatar || "/placeholder.svg"}
              alt={client?.name}
              className="w-12 h-12 rounded-full object-cover"
            />
            <div
              className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 ${
                isDarkMode ? "border-gray-800" : "border-white"
              } ${chat.status === "active" ? "bg-green-500" : "bg-gray-400"}`}
            ></div>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-2">
              <h4 className={`font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                {client?.name || "Noma'lum mijoz"}
              </h4>
              <span
                className={`px-2 py-1 rounded-full text-xs font-medium ${
                  chat.status === "active"
                    ? isDarkMode
                      ? "bg-green-900/30 text-green-400"
                      : "bg-green-100 text-green-800"
                    : isDarkMode
                      ? "bg-gray-700 text-gray-400"
                      : "bg-gray-100 text-gray-600"
                }`}
              >
                {chat.status === "active" ? "Faol" : "Yopilgan"}
              </span>
            </div>

            <p className={`text-sm font-medium mb-1 ${isDarkMode ? "text-gray-300" : "text-gray-700"}`}>
            </p>

            {lastMessage && (
              <p 
                className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}
                dangerouslySetInnerHTML={{
                  __html: highlightText(lastMessage.text, searchTerm)
                }}
              />
            )}

            <div className="flex items-center justify-between mt-2">
              <span className={`text-xs ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>
                {formatDate(chat.lastActivity)}
              </span>
              <span className={`text-xs ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>
                {chat.messages.length} ta xabar
              </span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div
        className={`max-w-4xl w-full max-h-[90vh] overflow-y-auto rounded-xl shadow-2xl ${
          isDarkMode ? "bg-gray-800 text-white" : "bg-white text-gray-900"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className={`text-2xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
            🔍 Chatlarni qidirish
          </h2>
          <button
            onClick={onClose}
            className={`p-2 rounded-lg transition-colors ${
              isDarkMode ? "hover:bg-gray-700 text-gray-400" : "hover:bg-gray-100 text-gray-600"
            }`}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Search Controls */}
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search Input */}
            <div className="flex-1">
              <div className="relative">
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Chat mavzusi yoki xabar matnini kiriting..."
                  className={`w-full px-4 py-3 pl-12 rounded-lg border transition-colors focus:outline-none focus:ring-2 ${
                    isDarkMode
                      ? "bg-gray-700 border-gray-600 text-white placeholder-gray-400 focus:ring-purple-500"
                      : "bg-gray-50 border-gray-300 text-gray-900 placeholder-gray-500 focus:ring-purple-500"
                  }`}
                />
                <div className="absolute left-4 top-1/2 transform -translate-y-1/2">
                  {isSearching ? (
                    <div className="w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  )}
                </div>
              </div>
            </div>

            {/* Filter */}
            <div className="md:w-48">
              <select
                value={searchType}
                onChange={(e) => setSearchType(e.target.value)}
                className={`w-full px-4 py-3 rounded-lg border transition-colors focus:outline-none focus:ring-2 ${
                  isDarkMode
                    ? "bg-gray-700 border-gray-600 text-white focus:ring-purple-500"
                    : "bg-gray-50 border-gray-300 text-gray-900 focus:ring-purple-500"
                }`}
              >
                <option value="all">Barcha chatlar</option>
                <option value="active">Faol chatlar</option>
                <option value="closed">Yopilgan chatlar</option>
              </select>
            </div>
          </div>
        </div>

        {/* Search Results */}
        <div className="p-6">
          {searchTerm ? (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className={`text-lg font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                  Qidiruv natijalari
                </h3>
                <span className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                  {searchResults.length} ta natija topildi
                </span>
              </div>

              {isSearching ? (
                <div className="text-center py-12">
                  <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                  <p className={isDarkMode ? "text-gray-400" : "text-gray-600"}>Qidirilmoqda...</p>
                </div>
              ) : searchResults.length > 0 ? (
                <div className="space-y-4">
                  {searchResults.map((chat, index) => (
                    <SearchResultCard key={chat.id} chat={chat} index={index} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">🔍</div>
                  <h3 className={`text-xl font-semibold mb-2 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                    Natija topilmadi
                  </h3>
                  <p className={isDarkMode ? "text-gray-400" : "text-gray-600"}>
                    "{searchTerm}" uchun hech qanday natija topilmadi. Boshqa so'z bilan urinib ko'ring.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">🔍</div>
              <h3 className={`text-xl font-semibold mb-2 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                Qidirishni boshlang
              </h3>
              <p className={isDarkMode ? "text-gray-400" : "text-gray-600"}>
                Chat mavzusi yoki xabar matnini kiriting va qidirish natijalarini ko'ring.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 dark:border-gray-700">
          <div className="flex justify-between items-center">
            <div className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
              {searchTerm && `"${searchTerm}" uchun ${searchResults.length} ta natija`}
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  setSearchTerm("")
                  setSearchResults([])
                }}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  isDarkMode
                    ? "bg-gray-700 text-gray-300 hover:bg-gray-600"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                Tozalash
              </button>
              <button
                onClick={onClose}
                className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                  isDarkMode
                    ? "bg-purple-600 text-white hover:bg-purple-700"
                    : "bg-purple-500 text-white hover:bg-purple-600"
                }`}
              >
                Yopish
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 