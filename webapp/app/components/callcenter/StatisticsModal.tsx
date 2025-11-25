"use client"

import { useState } from "react"
import { useChat } from "../../context/ChatContext"

interface StatisticsModalProps {
  isOpen: boolean
  onClose: () => void
  isDarkMode: boolean
}

export default function StatisticsModal({ isOpen, onClose, isDarkMode }: StatisticsModalProps) {
  const { chatSessions, users } = useChat()
  const [selectedPeriod, setSelectedPeriod] = useState("today")

  if (!isOpen) return null

  const totalChats = chatSessions.length
  const activeChats = chatSessions.filter(chat => chat.status === "active").length
  const closedChats = chatSessions.filter(chat => chat.status === "closed").length
  const totalClients = users.filter(u => u.role === "client").length
  const totalAgents = users.filter(u => u.role === "support").length

  // Mock data for different periods
  const getPeriodData = (period: string) => {
    const baseData = {
      newChats: Math.floor(Math.random() * 20) + 10,
      closedChats: Math.floor(Math.random() * 15) + 5,
      avgResponseTime: Math.floor(Math.random() * 5) + 1,
      customerSatisfaction: Math.floor(Math.random() * 20) + 80,
      avgChatDuration: Math.floor(Math.random() * 30) + 15,
      firstResponseTime: Math.floor(Math.random() * 5) + 1
    }

    switch (period) {
      case "today":
        return { ...baseData, period: "Bugun" }
      case "week":
        return { 
          ...baseData, 
          newChats: baseData.newChats * 7,
          closedChats: baseData.closedChats * 7,
          period: "Bu hafta"
        }
      case "month":
        return { 
          ...baseData, 
          newChats: baseData.newChats * 30,
          closedChats: baseData.closedChats * 30,
          period: "Bu oy"
        }
      default:
        return { ...baseData, period: "Bugun" }
    }
  }

  const periodData = getPeriodData(selectedPeriod)

  const StatCard = ({ title, value, subtitle, icon, color }: any) => (
    <div className={`p-6 rounded-xl border-2 ${isDarkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className={`text-sm font-medium ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>{title}</p>
          <p className={`text-2xl font-bold mt-1 ${isDarkMode ? "text-white" : "text-gray-900"}`}>{value}</p>
          <p className={`text-xs mt-1 ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>{subtitle}</p>
        </div>
        <div className={`w-12 h-12 rounded-full flex items-center justify-center text-2xl ${color}`}>
          {icon}
        </div>
      </div>
    </div>
  )

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
            📊 Call Center Statistika
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

        {/* Period Selector */}
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex space-x-2">
            {[
              { id: "today", label: "Bugun" },
              { id: "week", label: "Bu hafta" },
              { id: "month", label: "Bu oy" },
            ].map((period) => (
              <button
                key={period.id}
                onClick={() => setSelectedPeriod(period.id)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  selectedPeriod === period.id
                    ? isDarkMode
                      ? "bg-purple-600 text-white"
                      : "bg-purple-500 text-white"
                    : isDarkMode
                      ? "text-gray-400 hover:text-white hover:bg-gray-700"
                      : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                }`}
              >
                {period.label}
              </button>
            ))}
          </div>
        </div>

        {/* Statistics Grid */}
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            <StatCard
              title="Jami chatlar"
              value={totalChats}
              subtitle="Barcha vaqtlar bo'yicha"
              icon="💬"
              color="bg-blue-500 text-white"
            />
            <StatCard
              title="Faol chatlar"
              value={activeChats}
              subtitle="Hozir faol"
              icon="🟢"
              color="bg-green-500 text-white"
            />
            <StatCard
              title="Yopilgan chatlar"
              value={closedChats}
              subtitle="Tugatilgan"
              icon="🔴"
              color="bg-red-500 text-white"
            />
            <StatCard
              title="Mijozlar"
              value={totalClients}
              subtitle="Jami mijozlar"
              icon="👥"
              color="bg-purple-500 text-white"
            />
            <StatCard
              title="Agentlar"
              value={totalAgents}
              subtitle="Yordam agentlari"
              icon="🎧"
              color="bg-indigo-500 text-white"
            />
            <StatCard
              title="O'rtacha javob vaqti"
              value={`${periodData.avgResponseTime}min`}
              subtitle="Agent javobi"
              icon="⏱️"
              color="bg-yellow-500 text-white"
            />
          </div>

          {/* Detailed Statistics */}
          <div className="space-y-6">
            <h3 className={`text-xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
              {periodData.period} faoliyati
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className={`p-6 rounded-xl ${isDarkMode ? "bg-gray-700" : "bg-gray-50"}`}>
                <h4 className={`font-semibold mb-4 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                  📈 Faoliyat ko'rsatkichlari
                </h4>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className={isDarkMode ? "text-gray-300" : "text-gray-600"}>Yangi chatlar:</span>
                    <span className={`font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                      {periodData.newChats}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className={isDarkMode ? "text-gray-300" : "text-gray-600"}>Yopilgan chatlar:</span>
                    <span className={`font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                      {periodData.closedChats}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className={isDarkMode ? "text-gray-300" : "text-gray-600"}>O'rtacha chat vaqti:</span>
                    <span className={`font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                      {periodData.avgChatDuration}min
                    </span>
                  </div>
                </div>
              </div>

              <div className={`p-6 rounded-xl ${isDarkMode ? "bg-gray-700" : "bg-gray-50"}`}>
                <h4 className={`font-semibold mb-4 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                  🎯 KPI ko'rsatkichlari
                </h4>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className={isDarkMode ? "text-gray-300" : "text-gray-600"}>Mijoz mamnuniyati:</span>
                    <span className={`font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                      {periodData.customerSatisfaction}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className={isDarkMode ? "text-gray-300" : "text-gray-600"}>Birinchi javob vaqti:</span>
                    <span className={`font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                      {periodData.firstResponseTime}min
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className={isDarkMode ? "text-gray-300" : "text-gray-600"}>O'rtacha javob vaqti:</span>
                    <span className={`font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                      {periodData.avgResponseTime}min
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Performance Chart */}
            <div className={`p-6 rounded-xl ${isDarkMode ? "bg-gray-700" : "bg-gray-50"}`}>
              <h4 className={`font-semibold mb-4 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                📊 Faoliyat grafigi
              </h4>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className={isDarkMode ? "text-gray-300" : "text-gray-600"}>Yangi chatlar</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-blue-500 rounded-full" 
                        style={{ width: `${(periodData.newChats / 100) * 100}%` }}
                      ></div>
                    </div>
                    <span className={`text-sm font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                      {periodData.newChats}
                    </span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className={isDarkMode ? "text-gray-300" : "text-gray-600"}>Yopilgan chatlar</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-green-500 rounded-full" 
                        style={{ width: `${(periodData.closedChats / 100) * 100}%` }}
                      ></div>
                    </div>
                    <span className={`text-sm font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                      {periodData.closedChats}
                    </span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className={isDarkMode ? "text-gray-300" : "text-gray-600"}>Mijoz mamnuniyati</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-purple-500 rounded-full" 
                        style={{ width: `${periodData.customerSatisfaction}%` }}
                      ></div>
                    </div>
                    <span className={`text-sm font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                      {periodData.customerSatisfaction}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 dark:border-gray-700">
          <div className="flex justify-end space-x-3">
            <button
              onClick={onClose}
              className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                isDarkMode
                  ? "bg-gray-700 text-gray-300 hover:bg-gray-600"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              Yopish
            </button>
          </div>
        </div>
      </div>
    </div>
  )
} 