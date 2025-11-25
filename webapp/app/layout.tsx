import type React from "react"
import type { Metadata, Viewport } from "next"
import { Inter } from "next/font/google"
import "../styles/globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Alfa Connect - Telegram CRM",
  description: "Modern Telegram CRM application with multi-role support for client and call center interfaces",
  generator: 'v0.dev',
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Alfa Connect",
  },
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover", // Support for safe area insets (notch)
  themeColor: "#3b82f6", // Blue color for mobile browser UI
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <script src="https://telegram.org/js/telegram-web-app.js" async></script>
        {/* Script to bypass ngrok warning page by adding header to all requests */}
      </head>
      <body className={inter.className}>{children}</body>
    </html>
  )
}
