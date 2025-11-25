"use client"

export default function ClosedChats({ chats, users, onChatSelect, isDarkMode, currentUserId }) {
  const formatDate = (timestamp) => {
    if (!timestamp) return "Noma'lum"
    const date = new Date(timestamp)
    return date.toLocaleDateString("uz-UZ", {
      year: "numeric",
      month: "short",
      day: "numeric",
    })
  }

  const formatDuration = (createdAt, closedAt) => {
    if (!createdAt || !closedAt) return "Noma'lum"
    const duration = new Date(closedAt) - new Date(createdAt)
    const minutes = Math.floor(duration / (1000 * 60))
    if (minutes < 60) return `${minutes}min`
    const hours = Math.floor(minutes / 60)
    const remainingMinutes = minutes % 60
    return `${hours}soat ${remainingMinutes}min`
  }

  const getOtherUserId = (chat) => {
    const currentUserIdNum = typeof currentUserId === "string" ? parseInt(currentUserId) : currentUserId
    const chatClientId = parseInt(chat.clientId)
    return currentUserIdNum === chatClientId ? (chat.operatorId ? parseInt(chat.operatorId) : null) : chatClientId
  }

  const groupedChats = chats.reduce((groups, chat) => {
    const date = formatDate(chat.closedAt)
    if (!groups[date]) groups[date] = []
    groups[date].push(chat)
    return groups
  }, {})

  return (
    <div className="space-y-6 sm:space-y-8 pb-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl sm:text-2xl font-bold text-blue-900">Chat tarixi</h2>
        <span className="text-xs sm:text-sm text-blue-700">
          {chats.length} ta yopilgan sessiya
        </span>
      </div>

      {Object.keys(groupedChats).length === 0 ? (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">📝</div>
          <h3 className="text-xl font-semibold mb-2 text-blue-900">Yopilgan chatlar yo'q</h3>
          <p className="text-blue-700">Tugatilgan suhbatlar ma'lumot uchun bu yerda ko'rinadi.</p>
        </div>
      ) : (
        Object.entries(groupedChats)
          .sort(([a], [b]) => new Date(b) - new Date(a))
          .map(([date, dateChats]) => (
            <div key={date} className="space-y-3 sm:space-y-4">
              <h3 className="text-base sm:text-lg font-semibold text-blue-800">{date}</h3>
              <div className="space-y-3">
                {dateChats.map((chat, index) => {
                  const otherUserId = getOtherUserId(chat)
                  const otherUser = users.find((u) => u.id === otherUserId)
                  return (
                    <div
                      key={chat.id}
                      onClick={() => onChatSelect(chat.id)}
                      className="p-3 sm:p-4 rounded-xl cursor-pointer transition-all duration-200 transform active:scale-[0.98] hover:scale-[1.02] hover:shadow-lg bg-white hover:bg-blue-50 active:bg-blue-100 border border-blue-200 animate-slide-in touch-manipulation"
                      style={{ animationDelay: `${index * 50}ms`, touchAction: "manipulation" }}
                    >
                      <div className="flex items-start space-x-3 sm:space-x-4">
                        {/* Avatar */}
                        <div className="w-10 h-10 sm:w-10 sm:h-10 rounded-full bg-gray-400 flex items-center justify-center text-white font-bold opacity-75 flex-shrink-0 text-sm sm:text-base">
                          {otherUser?.full_name?.[0]?.toUpperCase() || chat.clientName?.[0]?.toUpperCase() || chat.operatorName?.[0]?.toUpperCase() || "?"}
                        </div>

                        {/* Chat Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <h4 className="font-semibold text-blue-900 text-sm sm:text-base truncate">
                              {otherUser?.full_name || chat.operatorName || chat.clientName || "Noma'lum foydalanuvchi"}
                            </h4>
                            <div className="flex items-center space-x-2">
                              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
                                🔒 Yopilgan
                              </span>
                              {chat.closedAt && (
                                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                  {formatDuration(chat.createdAt, chat.closedAt)}
                                </span>
                              )}
                            </div>
                          </div>


                          <div className="flex items-center justify-between">
                            <p className="text-sm truncate text-blue-600">
                              {chat.messages?.length || 0} ta xabar
                            </p>
                            <span className="text-xs text-blue-600">
                              {chat.closedAt ? `Yopilgan ${formatDate(chat.closedAt)}` : "Yopilgan"}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))
      )}
    </div>
  )
}
