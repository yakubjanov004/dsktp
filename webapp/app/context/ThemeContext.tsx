"use client"

import { createContext, useContext, ReactNode } from "react"

interface ThemeContextType {
  isDark: boolean
  colors: {
    primary: string
    secondary: string
    accent: string
    surface: string
    background: string
    text: string
    textSecondary: string
  }
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

interface ThemeProviderProps {
  children: ReactNode
  isDarkMode: boolean
}

export function ThemeProvider({ children, isDarkMode }: ThemeProviderProps) {
  const theme: ThemeContextType = {
    isDark: isDarkMode,
    colors: isDarkMode
      ? {
          primary: "bg-blue-600",
          secondary: "bg-gray-700",
          accent: "bg-purple-600",
          surface: "bg-gray-800",
          background: "bg-gray-900",
          text: "text-white",
          textSecondary: "text-gray-300",
        }
      : {
          primary: "bg-blue-500",
          secondary: "bg-gray-100",
          accent: "bg-purple-500",
          surface: "bg-white",
          background: "bg-gray-50",
          text: "text-gray-900",
          textSecondary: "text-gray-600",
        },
  }

  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>
}

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider")
  }
  return context
}
