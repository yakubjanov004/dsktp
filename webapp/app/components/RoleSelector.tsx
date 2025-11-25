"use client"

import { useState } from "react"

export default function RoleSelector({ onRoleSelect, user, isDarkMode }) {
  const [selectedRole, setSelectedRole] = useState("")

  const roles = [
    {
      id: "client",
      title: "Mijoz",
      description: "O'zingizning yordam chatlaringiz va chat tarixiga kirish",
      icon: "👤",
      color: "from-blue-500 to-blue-600",
      darkColor: "from-blue-600 to-blue-700",
    },
    {
      id: "callcenter",
      title: "Call Center",
      description: "Bir nechta mijoz suhbatlarini boshqarish",
      icon: "🎧",
      color: "from-purple-500 to-purple-600",
      darkColor: "from-purple-600 to-purple-700",
    },
  ]

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center text-3xl animate-bounce">
            💬
          </div>
          <h1 className={`text-3xl font-bold mb-2 ${isDarkMode ? "text-white" : "text-gray-800"}`}>
            Xush kelibsiz, {user?.first_name}!
          </h1>
          <p className={`${isDarkMode ? "text-gray-300" : "text-gray-600"}`}>Davom etish uchun rolingizni tanlang</p>
        </div>

        {/* Role Cards */}
        <div className="space-y-4 mb-8">
          {roles.map((role) => (
            <div
              key={role.id}
              onClick={() => setSelectedRole(role.id)}
              className={`
                p-6 rounded-xl cursor-pointer transition-all duration-300 transform hover:scale-105 border-2
                ${
                  selectedRole === role.id
                    ? `bg-gradient-to-r ${isDarkMode ? role.darkColor : role.color} text-white border-transparent shadow-xl`
                    : `${isDarkMode ? "bg-gray-800 border-gray-700 hover:bg-gray-750 text-white" : "bg-white border-gray-200 hover:bg-gray-50 text-gray-800"} hover:border-opacity-50`
                }
              `}
            >
              <div className="flex items-center space-x-4">
                <div className="text-4xl">{role.icon}</div>
                <div className="flex-1">
                  <h3 className="text-xl font-semibold mb-1">{role.title}</h3>
                  <p
                    className={`text-sm ${selectedRole === role.id ? "text-white/80" : isDarkMode ? "text-gray-400" : "text-gray-600"}`}
                  >
                    {role.description}
                  </p>
                </div>
                {selectedRole === role.id && (
                  <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center animate-pulse">
                    <div className="w-3 h-3 bg-white rounded-full"></div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Continue Button */}
        <button
          onClick={() => onRoleSelect(selectedRole)}
          disabled={!selectedRole}
          className={`
            w-full py-4 px-6 rounded-xl font-semibold text-lg transition-all duration-300 transform
            ${
              selectedRole
                ? `bg-gradient-to-r ${isDarkMode ? "from-green-600 to-green-700" : "from-green-500 to-green-600"} text-white shadow-lg hover:shadow-xl hover:scale-105 active:scale-95`
                : `${isDarkMode ? "bg-gray-700 text-gray-400" : "bg-gray-300 text-gray-500"} cursor-not-allowed`
            }
          `}
        >
          {selectedRole ? "Davom etish: " + roles.find((r) => r.id === selectedRole)?.title : "Rolni tanlang"}
        </button>
      </div>
    </div>
  )
}
