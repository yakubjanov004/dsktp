"use client"

import { useState, useEffect, useCallback } from "react"
import { useChat } from "../../context/ChatContext"
import { getLastSeenLabel } from "../../lib/presence"

interface Operator {
  id: number
  telegram_id: number
  full_name: string | null
  username: string | null
  phone: string | null
  role: string
  is_online: boolean
  last_seen_at: string | null
  created_at: string
  active_chats_count: number
  total_answered_chats: number
  today_answered_chats: number
  week_answered_chats: number
  total_messages_sent: number
}

interface Client {
  id: number
  telegram_id: number
  full_name: string | null
  username: string | null
  phone: string | null
  is_online: boolean
  last_seen_at: string | null
  region: string | null
  abonent_id: string | null
  active_chats_count: number
  total_chats_count: number
  last_chat_at: string | null
}

interface Overview {
  total_operators: number
  online_operators: number
  total_supervisors: number
  online_supervisors: number
  total_clients: number
  online_clients: number
  active_chats: number
  inbox_chats: number
  assigned_chats: number
  today_chats: number
  week_chats: number
  month_chats: number
  today_messages: number
  week_messages: number
}

interface DailyTrend {
  date: string
  total_chats: number
  answered_chats: number
  closed_chats: number
}

interface CCSStatistics {
  operators: Operator[]
  clients: Client[]
  overview: Overview
  daily_trends: DailyTrend[]
}

interface CCSStatisticsPanelProps {
  isDarkMode?: boolean
  telegramId: number
}

export default function CCSStatisticsPanel({ isDarkMode = false, telegramId }: CCSStatisticsPanelProps) {
  const { onlineUsers } = useChat()
  const [statistics, setStatistics] = useState<CCSStatistics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<"overview" | "operators" | "clients">("overview")
  const [refreshing, setRefreshing] = useState(false)
  
  // State to force re-render every 30 seconds for "last seen" update
  const [, setTick] = useState(0)
  
  // Update every 30 seconds to keep "last seen" labels accurate
  useEffect(() => {
    const interval = setInterval(() => {
      setTick(prev => prev + 1)
    }, 30000) // 30 seconds
    
    return () => clearInterval(interval)
  }, [])

  // Fetch statistics from API
  const fetchStatistics = useCallback(async (showRefreshIndicator = false) => {
    if (showRefreshIndicator) {
      setRefreshing(true)
    }
    
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || "/api"
      const response = await fetch(`${apiBase}/chat/ccs/statistics?telegram_id=${telegramId}`, {
        headers: {
          "Content-Type": "application/json",
        },
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch statistics: ${response.status}`)
      }

      const data = await response.json()
      setStatistics(data)
      setError(null)
    } catch (err) {
      console.error("[CCSStatisticsPanel] Error fetching statistics:", err)
      setError(err instanceof Error ? err.message : "Failed to fetch statistics")
    } finally {
      setIsLoading(false)
      setRefreshing(false)
    }
  }, [telegramId])

  // Initial load
  useEffect(() => {
    fetchStatistics()
  }, [fetchStatistics])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchStatistics()
    }, 30000)

    return () => clearInterval(interval)
  }, [fetchStatistics])

  // Update online status from WebSocket
  useEffect(() => {
    if (!statistics) return

    // Update operators online status
    setStatistics((prev) => {
      if (!prev) return prev
      
      const updatedOperators = prev.operators.map((op) => ({
        ...op,
        is_online: onlineUsers.has(op.id),
      }))

      const updatedClients = prev.clients.map((client) => ({
        ...client,
        is_online: onlineUsers.has(client.id),
      }))

      return {
        ...prev,
        operators: updatedOperators,
        clients: updatedClients,
      }
    })
  }, [onlineUsers])

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center py-12 ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
        <div className="text-center">
          <div className="text-4xl mb-4 animate-pulse">📊</div>
          <p>Statistika yuklanmoqda...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`text-center py-12 ${isDarkMode ? "text-red-400" : "text-red-600"}`}>
        <div className="text-4xl mb-4">❌</div>
        <p className="mb-4">{error}</p>
        <button
          onClick={() => fetchStatistics()}
          className={`px-4 py-2 rounded-lg ${
            isDarkMode ? "bg-gray-700 hover:bg-gray-600" : "bg-gray-200 hover:bg-gray-300"
          }`}
        >
          Qayta urinish
        </button>
      </div>
    )
  }

  if (!statistics) return null

  const { operators, clients, overview, daily_trends } = statistics

  // Stats cards data
  const overviewCards = [
    {
      title: "Operatorlar",
      value: `${overview.online_operators}/${overview.total_operators}`,
      subtitle: "Onlayn / Jami",
      icon: "🎧",
      color: "bg-purple-500",
    },
    {
      title: "Supervisorlar",
      value: `${overview.online_supervisors}/${overview.total_supervisors}`,
      subtitle: "Onlayn / Jami",
      icon: "👔",
      color: "bg-indigo-500",
    },
    {
      title: "Mijozlar",
      value: `${overview.online_clients}/${overview.total_clients}`,
      subtitle: "Onlayn / Jami",
      icon: "👥",
      color: "bg-blue-500",
    },
    {
      title: "Faol chatlar",
      value: overview.active_chats,
      subtitle: `${overview.inbox_chats} inbox, ${overview.assigned_chats} tayinlangan`,
      icon: "💬",
      color: "bg-green-500",
    },
    {
      title: "Bugungi chatlar",
      value: overview.today_chats,
      subtitle: `${overview.today_messages} xabar`,
      icon: "📅",
      color: "bg-orange-500",
    },
    {
      title: "Haftalik chatlar",
      value: overview.week_chats,
      subtitle: `${overview.week_messages} xabar`,
      icon: "📈",
      color: "bg-teal-500",
    },
  ]

  return (
    <div className="h-full flex flex-col min-h-0 overflow-hidden">
      {/* Header with tabs */}
      <div className="flex-shrink-0 mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className={`text-lg font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
            📊 CCS Statistika
          </h2>
          <button
            onClick={() => fetchStatistics(true)}
            disabled={refreshing}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              isDarkMode
                ? "bg-gray-700 hover:bg-gray-600 text-gray-300"
                : "bg-gray-100 hover:bg-gray-200 text-gray-700"
            } ${refreshing ? "opacity-50 cursor-not-allowed" : ""}`}
          >
            {refreshing ? "⏳ Yangilanmoqda..." : "🔄 Yangilash"}
          </button>
        </div>

        {/* Tabs */}
        <div className="flex space-x-2 overflow-x-auto pb-1 scrollbar-hide">
          {[
            { id: "overview" as const, label: "Umumiy ko'rinish", icon: "📊" },
            { id: "operators" as const, label: "Operatorlar", icon: "🎧", count: operators.length },
            { id: "clients" as const, label: "Mijozlar", icon: "👥", count: clients.length },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap flex items-center ${
                activeTab === tab.id
                  ? isDarkMode
                    ? "bg-purple-600 text-white"
                    : "bg-purple-500 text-white"
                  : isDarkMode
                    ? "bg-gray-700 text-gray-300 hover:bg-gray-600"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              <span className="mr-1.5">{tab.icon}</span>
              {tab.label}
              {tab.count !== undefined && (
                <span className={`ml-2 px-1.5 py-0.5 rounded-full text-xs ${
                  activeTab === tab.id ? "bg-white/20" : isDarkMode ? "bg-gray-600" : "bg-gray-200"
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto min-h-0 scrollbar-hide">
        {activeTab === "overview" && (
          <div className="space-y-4">
            {/* Stats cards grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {overviewCards.map((card, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-xl border ${
                    isDarkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-2xl">{card.icon}</span>
                    <div className={`w-8 h-8 rounded-full ${card.color} flex items-center justify-center text-white text-xs font-bold`}>
                      {typeof card.value === "number" ? card.value : ""}
                    </div>
                  </div>
                  <div className={`text-xl font-bold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                    {card.value}
                  </div>
                  <div className={`text-xs ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                    {card.title}
                  </div>
                  <div className={`text-xs mt-1 ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>
                    {card.subtitle}
                  </div>
                </div>
              ))}
            </div>

            {/* Daily trends */}
            {daily_trends.length > 0 && (
              <div className={`p-4 rounded-xl border ${isDarkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"}`}>
                <h3 className={`text-sm font-semibold mb-3 ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                  📈 Oxirgi 7 kun
                </h3>
                <div className="space-y-2">
                  {daily_trends.map((trend, index) => (
                    <div
                      key={index}
                      className={`flex items-center justify-between p-2 rounded-lg ${
                        isDarkMode ? "bg-gray-700" : "bg-gray-50"
                      }`}
                    >
                      <span className={`text-sm ${isDarkMode ? "text-gray-300" : "text-gray-600"}`}>
                        {new Date(trend.date).toLocaleDateString("uz-UZ", {
                          weekday: "short",
                          day: "numeric",
                          month: "short",
                        })}
                      </span>
                      <div className="flex items-center space-x-4">
                        <span className={`text-sm ${isDarkMode ? "text-blue-400" : "text-blue-600"}`}>
                          💬 {trend.total_chats}
                        </span>
                        <span className={`text-sm ${isDarkMode ? "text-green-400" : "text-green-600"}`}>
                          ✅ {trend.answered_chats}
                        </span>
                        <span className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                          📪 {trend.closed_chats}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "operators" && (
          <div className="space-y-3">
            {operators.length === 0 ? (
              <div className={`text-center py-8 ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                <div className="text-4xl mb-2">🎧</div>
                <p>Operatorlar topilmadi</p>
              </div>
            ) : (
              operators.map((operator) => (
                <div
                  key={operator.id}
                  className={`p-4 rounded-xl border transition-all ${
                    isDarkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="relative">
                        <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold ${
                          operator.role === "callcenter_supervisor" ? "bg-indigo-500" : "bg-purple-500"
                        }`}>
                          {operator.full_name?.[0]?.toUpperCase() || "?"}
                        </div>
                        <div className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 ${
                          isDarkMode ? "border-gray-800" : "border-white"
                        } ${operator.is_online ? "bg-green-500" : "bg-gray-400"}`}></div>
                      </div>
                      <div>
                        <div className={`font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                          {operator.full_name || operator.username || "Noma'lum"}
                          {operator.role === "callcenter_supervisor" && (
                            <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
                              Supervisor
                            </span>
                          )}
                        </div>
                        <div className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                          {operator.is_online ? (
                            <span className="text-green-500">🟢 Onlayn</span>
                          ) : (
                            <span>{getLastSeenLabel(false, operator.last_seen_at)}</span>
                          )}
                        </div>
                        {operator.phone && (
                          <div className={`text-xs ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>
                            📱 {operator.phone}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Statistics row */}
                  <div className="mt-3 grid grid-cols-4 gap-2">
                    <div className={`text-center p-2 rounded-lg ${isDarkMode ? "bg-gray-700" : "bg-gray-50"}`}>
                      <div className={`text-lg font-bold ${isDarkMode ? "text-green-400" : "text-green-600"}`}>
                        {operator.active_chats_count}
                      </div>
                      <div className={`text-xs ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                        Faol
                      </div>
                    </div>
                    <div className={`text-center p-2 rounded-lg ${isDarkMode ? "bg-gray-700" : "bg-gray-50"}`}>
                      <div className={`text-lg font-bold ${isDarkMode ? "text-blue-400" : "text-blue-600"}`}>
                        {operator.today_answered_chats}
                      </div>
                      <div className={`text-xs ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                        Bugun
                      </div>
                    </div>
                    <div className={`text-center p-2 rounded-lg ${isDarkMode ? "bg-gray-700" : "bg-gray-50"}`}>
                      <div className={`text-lg font-bold ${isDarkMode ? "text-purple-400" : "text-purple-600"}`}>
                        {operator.week_answered_chats}
                      </div>
                      <div className={`text-xs ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                        Hafta
                      </div>
                    </div>
                    <div className={`text-center p-2 rounded-lg ${isDarkMode ? "bg-gray-700" : "bg-gray-50"}`}>
                      <div className={`text-lg font-bold ${isDarkMode ? "text-orange-400" : "text-orange-600"}`}>
                        {operator.total_answered_chats}
                      </div>
                      <div className={`text-xs ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                        Jami
                      </div>
                    </div>
                  </div>

                  {/* Messages sent */}
                  <div className={`mt-2 text-xs ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>
                    💬 Jami {operator.total_messages_sent} xabar yuborilgan
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "clients" && (
          <div className="space-y-3">
            {clients.length === 0 ? (
              <div className={`text-center py-8 ${isDarkMode ? "text-gray-400" : "text-gray-600"}`}>
                <div className="text-4xl mb-2">👥</div>
                <p>Mijozlar topilmadi</p>
              </div>
            ) : (
              clients.map((client) => (
                <div
                  key={client.id}
                  className={`p-4 rounded-xl border transition-all ${
                    isDarkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="relative">
                        <div className="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold">
                          {client.full_name?.[0]?.toUpperCase() || "?"}
                        </div>
                        <div className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 ${
                          isDarkMode ? "border-gray-800" : "border-white"
                        } ${client.is_online ? "bg-green-500" : "bg-gray-400"}`}></div>
                      </div>
                      <div>
                        <div className={`font-medium ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                          {client.full_name || client.username || "Noma'lum mijoz"}
                        </div>
                        <div className={`text-xs ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>
                          {client.is_online ? (
                            <span className="text-green-500">🟢 Onlayn</span>
                          ) : (
                            <span>{getLastSeenLabel(false, client.last_seen_at)}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-sm font-semibold ${isDarkMode ? "text-white" : "text-gray-900"}`}>
                        {client.total_chats_count} chat
                      </div>
                      {client.active_chats_count > 0 && (
                        <div className="text-xs text-green-500">
                          {client.active_chats_count} faol
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Client details */}
                  <div className={`mt-2 flex flex-wrap gap-2 text-xs ${isDarkMode ? "text-gray-500" : "text-gray-400"}`}>
                    {client.phone && (
                      <span>📱 {client.phone}</span>
                    )}
                    {client.region && (
                      <span>📍 {client.region}</span>
                    )}
                    {client.abonent_id && (
                      <span>🆔 {client.abonent_id}</span>
                    )}
                    {client.last_chat_at && (
                      <span>
                        💬 Oxirgi chat: {new Date(client.last_chat_at).toLocaleDateString("uz-UZ", {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

