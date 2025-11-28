"use client"

import { useState, useEffect } from "react"
import { ChatProvider } from "./context/ChatContext"
import { ThemeProvider } from "./context/ThemeContext"
import ClientDashboard from "./components/client/ClientDashboard"
import CallCenterDashboard from "./components/callcenter/CallCenterDashboard"
import SupervisorDashboard from "./components/callcenter/SupervisorDashboard"
import { getUserRole, getUserInfo, bootstrapUser, fetchRuntimeConfig, getAuthenticatedUser, updateUserStatus, type DatabaseUser } from "./lib/api"
import { setOnlineStatus, setPresenceTelegramId } from "./lib/presence"
import { setRuntimeWsBaseUrl } from "./lib/wsUrl"
import { log } from "@/utils/devLogger"

// Telegram WebApp type definitions
declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void
        expand: () => void
        colorScheme: string
        version?: string
        platform?: string
        initData?: string
        initDataUnsafe?: {
          user?: {
            first_name: string
            last_name: string
            username: string
            id: number
          }
          start_param?: string
          query_id?: string
          auth_date?: number
        }
      }
    }
  }
}

interface TelegramUser {
  first_name: string
  last_name: string
  username: string
  id: number
}

export default function App() {
  const [currentRole, setCurrentRole] = useState<string | null>(null)
  const [telegramUser, setTelegramUser] = useState<TelegramUser | null>(null)
  const [dbUser, setDbUser] = useState<DatabaseUser | null>(null)
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [isWebAppReady, setIsWebAppReady] = useState(false)
  const [loadingError, setLoadingError] = useState(false)
  const [isLoadingRole, setIsLoadingRole] = useState(true)

  const fetchUserRole = async (telegramId: number, telegramUser: TelegramUser | null) => {
    try {
      setIsLoadingRole(true)
      console.log(`🔍 [fetchUserRole] Starting role fetch for telegram_id: ${telegramId}`)
      
      // 1) Try to get authenticated user info directly (no query params - uses initData header)
      let userInfo: DatabaseUser | null = null
      try {
        userInfo = await getAuthenticatedUser()
      } catch (error) {
        console.warn(`⚠️ [fetchUserRole] getAuthenticatedUser failed:`, error)
        // Continue to bootstrap fallback
      }
      
      // 2) If user not found, try bootstrap (create new or get existing)
      if (!userInfo && telegramUser) {
        console.log(`   User not found via /me, attempting to bootstrap user with data:`, telegramUser)
        try {
          const bootstrappedUser = await bootstrapUser({
            id: telegramUser.id,
            first_name: telegramUser.first_name,
            last_name: telegramUser.last_name,
            username: telegramUser.username,
          })
          
          if (bootstrappedUser) {
            // Use bootstrap result directly - it has all the info we need
            userInfo = bootstrappedUser
            console.log(`✅ [fetchUserRole] User bootstrapped successfully:`, {
              id: userInfo.id,
              full_name: userInfo.full_name,
              role: userInfo.role
            })
          }
        } catch (error) {
          console.error(`❌ [fetchUserRole] Bootstrap failed:`, error)
        }
      }
      
      // 3) If still no user, try getUserInfo as final fallback
      if (!userInfo) {
        console.log(`   Trying getUserInfo as fallback...`)
        try {
          userInfo = await getUserInfo(telegramId)
        } catch (error) {
          console.error(`❌ [fetchUserRole] getUserInfo also failed:`, error)
        }
      }
      
      if (!userInfo) {
        console.error(`❌ [fetchUserRole] User not found in database for telegram_id: ${telegramId}`)
        console.error("   Cannot proceed without database record")
        setLoadingError(true)
        setCurrentRole(null)
        setIsLoadingRole(false)
        return
      }
      
      // Add operator_id if missing (for compatibility with new endpoint format)
      if (!userInfo.operator_id && userInfo.role && 
          (userInfo.role === 'callcenter_operator' || userInfo.role === 'callcenter_supervisor')) {
        userInfo.operator_id = userInfo.id
      }
      
      console.log("✅ [fetchUserRole] User authenticated successfully:", {
        id: userInfo.id,
        full_name: userInfo.full_name,
        role: userInfo.role,
        operator_id: userInfo.operator_id,
        telegram_id: userInfo.telegram_id
      })
      console.log(`👤 WEBAPP LOADED - User: ${userInfo.full_name} (ID: ${userInfo.id}, Role: ${userInfo.role})`)
      
      setDbUser(userInfo)
      
      // 4) Set user as online after successful authentication (non-blocking)
      console.log(`🟢 [PRESENCE] Setting user as online`)
      setOnlineStatus(true).catch(err => {
        console.warn("Failed to set online status:", err)
        // Don't block authentication if presence update fails
      })
      
      // Map database roles to component roles
      const role = userInfo.role
      let componentRole: string | null = null
      
      switch (role) {
        case "client":
          componentRole = "client"
          console.log("👤 User is CLIENT - opening Client Dashboard")
          break
        case "callcenter_operator":
          componentRole = "ccoperator"
          console.log("📞 User is CALL CENTER OPERATOR - opening Operator Dashboard")
          break
        case "callcenter_supervisor":
          componentRole = "ccsupervisor"
          console.log("👔 User is CALL CENTER SUPERVISOR - opening Supervisor Dashboard")
          break
        case "admin":
          componentRole = "admin"
          console.log("🔑 User is ADMIN - opening Admin Dashboard")
          break
        default:
          console.warn("⚠️ Unknown role:", role, "- showing error")
          componentRole = null
      }
      
      setCurrentRole(componentRole)
      
    } catch (error) {
      console.error("❌ [fetchUserRole] Error fetching user role:", error)
      if (error instanceof Error) {
        console.error(`   Error: ${error.message}`)
      }
      setCurrentRole(null)
    } finally {
      setIsLoadingRole(false)
    }
  }

  useEffect(() => {
    const initializeApp = async () => {
      // Test client-side logger
      log('Client-side log from page.tsx:', {
        message: 'Hello from client!',
        timestamp: new Date().toISOString(),
        userAgent: typeof window !== 'undefined' ? window.navigator.userAgent : 'N/A'
      })
      
      const tg = window.Telegram?.WebApp
      const urlParams = new URLSearchParams(window.location.search)
      const devTelegramId = urlParams.get('telegram_id')
      const isInTelegram = Boolean(tg?.initData)
      const isDevelopment = !isInTelegram && !!devTelegramId
      const botUsername = process.env.NEXT_PUBLIC_BOT_USERNAME || 'alfaconnect_bot'
      const deeplink = `https://t.me/${botUsername}?start=webapp`

      // 🚫 Block direct browser access (Telegram or explicit dev param only)
      if (!isInTelegram && !isDevelopment) {
        console.error("🔒 [SECURITY] Direct browser access detected!")
        console.error("   This webapp is designed to run ONLY inside Telegram")

        alert(
          "⚠️ Bu ilovani Telegram bot ichidan ochish kerak!\n\n" +
          "Iltimos, Telegram botiga qaytib, WebApp-ni davom ettiring.\n\n" +
          "Linkni bosish uchun OK tugmasini bosing."
        )

        try {
          window.location.href = deeplink
        } catch (e) {
          console.warn("Could not redirect to Telegram")
        }

        setLoadingError(true)
        setIsLoadingRole(false)
        return
      }

      // Run runtime config fetch + Telegram validation in parallel for faster startup
      const runtimeConfigPromise = (async () => {
        console.log("📋 Step 1: Loading runtime configuration...")
        try {
          const config = await fetchRuntimeConfig()
          setRuntimeWsBaseUrl(config.wsBaseUrl)
          console.log("✅ Step 1 Complete: Runtime config loaded", {
            apiBase: config.apiBaseUrl,
            wsBase: config.wsBaseUrl,
          })
          return config
        } catch (error) {
          console.error("❌ Step 1 Failed: Runtime config error:", error)
          return null
        }
      })()

      const telegramUserPromise = (async (): Promise<TelegramUser> => {
        console.log("🎮 Step 2: Initializing Telegram WebApp...")

        if (tg && tg.initData) {
          try {
            tg.ready()
            tg.expand()
            console.log("✅ Telegram WebApp ready")
          } catch (e) {
            console.warn("⚠️ Error calling Telegram WebApp methods:", e)
          }

          if (tg.colorScheme) {
            setIsDarkMode(tg.colorScheme === "dark")
            if (tg.colorScheme === "dark") {
              document.documentElement.classList.add("dark")
            }
          }

          console.log("🔐 Validating Telegram initData with backend...")
          const validateResponse = await fetch(
            `${process.env.NEXT_PUBLIC_API_BASE || '/api'}/webapp/validate?init_data=${encodeURIComponent(tg.initData)}`
          )

          if (!validateResponse.ok) {
            const errorData = await validateResponse.text()
            throw new Error(`initData validation failed: ${errorData}`)
          }

          const validationData = await validateResponse.json()
          const validatedUser = validationData.user

          if (!validatedUser || !validatedUser.id) {
            throw new Error("Telegram foydalanuvchi ma'lumotlari invalid")
          }

          return {
            id: validatedUser.id,
            first_name: validatedUser.first_name || "",
            last_name: validatedUser.last_name || "",
            username: validatedUser.username || "",
          }
        }

        if (isDevelopment && devTelegramId) {
          console.warn("🧪 [DEV MODE] Using telegram_id parameter for testing")
          const telegramId = parseInt(devTelegramId)
          if (Number.isNaN(telegramId)) {
            throw new Error("Invalid telegram_id parameter")
          }
          return {
            id: telegramId,
            first_name: "Test",
            last_name: "User",
            username: "testuser",
          }
        }

        throw new Error("Telegram WebApp ma'lumotlari topilmadi")
      })()

      try {
        const [, telegramUserData] = await Promise.all([
          runtimeConfigPromise,
          telegramUserPromise,
        ])

        console.log("👤 Step 2 Complete: Telegram user validated")
        setTelegramUser(telegramUserData)
        setIsWebAppReady(true)

        console.log("🔍 Step 3: Fetching user role...")
        fetchUserRole(telegramUserData.id, telegramUserData)
      } catch (error) {
        console.error("❌ Telegram initialization failed:", error)
        alert(
          "❌ Telegram ma'lumotlarini yuklashda xatolik. Iltimos, bot orqali qayta urinib ko'ring."
        )
        setLoadingError(true)
        setIsLoadingRole(false)
      }
    };

    // Check if we're in development mode (telegram_id param present)
    const urlParams = new URLSearchParams(window.location.search)
    const devTelegramId = urlParams.get('telegram_id')
    const isInTelegram = Boolean(window.Telegram?.WebApp?.initData)
    const isDevelopment = !isInTelegram && !!devTelegramId
    
    // Use a flag to prevent multiple initializations
    let initialized = false
    
    const tryInitialize = () => {
      if (initialized) {
        console.log("⚠️ [INIT] App already initialized, skipping...")
        return
      }
      
      // In development mode, skip SDK check and initialize immediately
      if (isDevelopment) {
        console.log("🧪 [DEV MODE] Skipping Telegram SDK check, initializing directly...")
        initialized = true
        initializeApp()
        return
      }
      
      // In production (Telegram), wait for SDK
      if (window.Telegram?.WebApp) {
        initialized = true
        initializeApp()
      } else {
        // Try to wait for SDK
        let attempts = 0
        const intervalId = setInterval(() => {
          attempts++
          if (window.Telegram?.WebApp && !initialized) {
            initialized = true
            clearInterval(intervalId)
            initializeApp()
          } else if (attempts > 10) { // Wait for ~1 second
            clearInterval(intervalId)
            // SDK not loaded - cannot proceed
            console.error("❌ Telegram WebApp SDK not available")
            alert("⚠️ Telegram WebApp SDK topilmadi. Iltimos, bot orqali oching.")
            setLoadingError(true)
            setIsLoadingRole(false)
          }
        }, 100)
      }
    }
    
    tryInitialize()
    
    // Cleanup function to reset initialization flag on unmount
    return () => {
      initialized = false
    }
  }, []); // Empty dependency array - only run once on mount

  // Handle presence tracking - heartbeat and offline on leave
  // Works for all roles: client, callcenter_operator, callcenter_supervisor
  useEffect(() => {
    if (!telegramUser?.id || !dbUser) return

    console.log(`🟢 [PRESENCE] Initializing presence tracking for user: ${dbUser.id} (role: ${dbUser.role})`)
    
    // Set telegram_id for dev fallback (used when no Telegram initData available)
    setPresenceTelegramId(telegramUser.id)

    // Initial heartbeat: set online immediately when webapp opens
    setOnlineStatus(true).catch(err => {
      console.warn("[PRESENCE] Initial heartbeat failed:", err)
    })

    // Heartbeat: update last_seen_at every 30 seconds while online
    const heartbeatInterval = setInterval(() => {
      setOnlineStatus(true).catch(err => {
        console.warn("[PRESENCE] Heartbeat failed:", err)
      })
    }, 30000) // 30 seconds

    // Handle visibility change (tab switch, minimize, etc.)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        // Tab is hidden or minimized - set offline
        console.log(`🔴 [PRESENCE] Tab hidden - setting user as offline`)
        setOnlineStatus(false).catch(err => {
          console.warn("[PRESENCE] Failed to set offline status on visibility change:", err)
        })
      } else if (document.visibilityState === 'visible') {
        // Tab is visible again - set online
        console.log(`🟢 [PRESENCE] Tab visible - setting user as online`)
        setOnlineStatus(true).catch(err => {
          console.warn("[PRESENCE] Failed to set online status on visibility change:", err)
        })
      }
    }

    // Set offline when page is closed/unloaded
    const handleBeforeUnload = () => {
      console.log(`🔴 [PRESENCE] Page unloading - setting user as offline`)
      // Use keepalive to ensure request completes even if page is closing
      setOnlineStatus(false).catch(err => {
        console.warn("[PRESENCE] Failed to set offline status on unload:", err)
      })
    }

    // Add event listeners
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('beforeunload', handleBeforeUnload)
    window.addEventListener('pagehide', handleBeforeUnload)

    // Cleanup
    return () => {
      console.log(`🔴 [PRESENCE] Component unmounting - setting user as offline`)
      clearInterval(heartbeatInterval)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('beforeunload', handleBeforeUnload)
      window.removeEventListener('pagehide', handleBeforeUnload)
      // Set offline on cleanup (component unmount)
      setOnlineStatus(false).catch(() => {})
    }
  }, [telegramUser?.id, dbUser])

  // if (!isWebAppReady) {
  //   return (
  //     <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
  //       <div className="text-center">
  //         <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mx-auto mb-4"></div>
  //         <p className="text-lg font-medium text-gray-700 dark:text-gray-300">Alfa Connect yuklanmoqda...</p>
  //         <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">Iltimos, kuting</p>
  //       </div>
  //     </div>
  //   )
  // }

  if (isLoadingRole) {
    return (
      <ThemeProvider isDarkMode={false}>
        <div className="flex items-center justify-center min-h-screen bg-white">
          <div className="text-center">
            <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p className="text-lg font-medium text-blue-900">Alfa Connect yuklanmoqda...</p>
            <p className="text-sm text-blue-700 mt-2">
              {telegramUser ? `Foydalanuvchi: ${telegramUser.first_name} ${telegramUser.last_name || ""}` : "Foydalanuvchi aniqlanmoqda..."}
            </p>
            <p className="text-xs text-blue-600 mt-1">Iltimos, kuting</p>
          </div>
        </div>
      </ThemeProvider>
    )
  }

  if (loadingError) {
    return (
      <ThemeProvider isDarkMode={false}>
        <div className="flex items-center justify-center min-h-screen bg-white">
          <div className="text-center p-6">
            <div className="text-4xl mb-4">⚠️</div>
            <p className="text-lg font-medium text-blue-900 mb-2">Xatolik yuz berdi</p>
            <p className="text-sm text-blue-700">
              {dbUser ? (
                <>User bazada topilmadi yoki roli yo'q.</>
              ) : (
                <>Telegram foydalanuvchi ma'lumotlari topilmadi. Browser console'ni tekshiring (F12).</>
              )}
            </p>
            <p className="text-xs text-blue-600 mt-4">
              <details>
                <summary>📋 Debug Info (Tekshiruv Malumotlari)</summary>
                <div className="text-left mt-2 bg-gray-100 p-3 rounded text-xs font-mono space-y-1">
                  <p>🔑 Telegram ID: <strong>{telegramUser?.id || "❌ topilmadi"}</strong></p>
                  <p>👤 Full Name: <strong>{telegramUser?.first_name} {telegramUser?.last_name || ""}</strong></p>
                  <p>📱 Username: <strong>{telegramUser?.username || "❌ yo'q"}</strong></p>
                  <p>🌐 API Base: <strong>{process.env.NEXT_PUBLIC_API_BASE || "/api"}</strong></p>
                  <p>📍 Location: <strong>{typeof window !== 'undefined' ? window.location.href : "N/A"}</strong></p>
                  <p>📦 Telegram SDK: <strong>{typeof window !== 'undefined' && window.Telegram?.WebApp ? "✅ mavjud" : "❌ topilmadi"}</strong></p>
                  <p>🔐 initData: <strong>{typeof window !== 'undefined' && window.Telegram?.WebApp?.initData ? "✅ mavjud" : "❌ topilmadi"}</strong></p>
                  <p>🗄️ DB User: <strong>{dbUser ? `✅ ${dbUser.full_name} (ID: ${dbUser.id})` : "❌ topilmadi"}</strong></p>
                  <p>🎭 DB Role: <strong>{dbUser?.role || "❌ topilmadi"}</strong></p>
                </div>
              </details>
            </p>
            <p className="text-xs text-blue-600 mt-3">
              <strong>Yo'l-yo'riq:</strong>
              <br/>1. F12 bosib, Console'ni oching va qizil xatolarni tekshiring
              <br/>2. Agar "telegram_id" yo'q bo'lsa, bot orqali oching
              <br/>3. Agar "DB User: topilmadi" bo'lsa, bot orqali ro'yxatdan o'ting
              <br/>4. Agar muammo davom etsa, botga qayta kirib ko'ring
            </p>
          </div>
        </div>
      </ThemeProvider>
    )
  }

  return (
    <ThemeProvider isDarkMode={isDarkMode}>
      <ChatProvider 
        telegramId={telegramUser?.id} 
        userId={dbUser?.id}
        userRole={dbUser?.role}
      >
        <div className="min-h-screen bg-white transition-colors duration-500">
          {!currentRole ? (
            <div className="flex items-center justify-center min-h-screen">
              <div className="text-center p-6">
                <div className="text-4xl mb-4">⚠️</div>
                <p className="text-lg font-medium text-blue-900 mb-2">Rol topilmadi</p>
                <p className="text-sm text-blue-700">
                  Foydalanuvchi bazada topilmadi yoki roli yo'q.
                </p>
                <p className="text-xs text-blue-600 mt-2">
                  Iltimos, bot orqali ro'yxatdan o'ting.
                </p>
              </div>
            </div>
          ) : currentRole === "client" ? (
            <ClientDashboard 
              user={telegramUser!} 
              dbUser={dbUser}
              isDarkMode={false} 
              onRoleChange={() => {}} // Role change disabled
            />
          ) : currentRole === "ccoperator" ? (
            <CallCenterDashboard
              user={telegramUser!}
              dbUser={dbUser}
              isDarkMode={isDarkMode}
              role="operator"
            />
          ) : currentRole === "ccsupervisor" ? (
            <SupervisorDashboard
              user={telegramUser!}
              dbUser={dbUser}
              isDarkMode={false}
            />
          ) : (
            <CallCenterDashboard
              user={telegramUser!}
              dbUser={dbUser}
              isDarkMode={isDarkMode}
            />
          )}
        </div>
      </ChatProvider>
    </ThemeProvider>
  )
}
