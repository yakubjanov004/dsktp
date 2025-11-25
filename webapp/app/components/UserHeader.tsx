"use client"

export default function UserHeader({ user, isDarkMode }) {
  const getInitials = (firstName, lastName) => {
    return `${firstName?.[0] || ""}${lastName?.[0] || ""}`.toUpperCase()
  }

  return (
    <div
      className={`sticky top-0 z-10 px-4 py-3 border-b transition-colors duration-300 ${
        isDarkMode ? "bg-gray-800 border-gray-700 text-white" : "bg-white border-gray-200 text-gray-800"
      }`}
    >
      <div className="flex items-center space-x-3">
        {/* Avatar */}
        <div className="relative">
          {user?.photo_url ? (
            <img
              src={user.photo_url || "/placeholder.svg"}
              alt={`${user.first_name} ${user.last_name}`}
              className="w-10 h-10 rounded-full object-cover"
            />
          ) : (
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold text-sm ${
                isDarkMode ? "bg-blue-600 text-white" : "bg-blue-500 text-white"
              }`}
            >
              {getInitials(user?.first_name, user?.last_name)}
            </div>
          )}
          <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-white dark:border-gray-800"></div>
        </div>

        {/* User Info */}
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-lg truncate">
            {user?.first_name} {user?.last_name}
          </h2>
          {user?.username && (
            <p className={`text-sm truncate ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>@{user.username}</p>
          )}
        </div>

        {/* Status */}
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full bg-green-500 animate-pulse`}></div>
          <span className={`text-sm ${isDarkMode ? "text-gray-400" : "text-gray-500"}`}>Online</span>
        </div>
      </div>
    </div>
  )
}
