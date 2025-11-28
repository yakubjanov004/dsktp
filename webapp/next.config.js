/** @type {import('next').NextConfig} */
const extraDevOrigins = (process.env.ALLOWED_DEV_ORIGINS || "")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean)

const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    domains: ["t.me", "cdn.telegram.org"],
    unoptimized: true,
  },
  // Production: Run as Next.js server (not static export)
  // Remove output: "export" for server mode
  trailingSlash: false,
  // output: "export", // Commented out for production server mode
  
  // Production optimizations
  compress: true,
  poweredByHeader: false, // Security: hide X-Powered-By header
  
  // Environment variables - explicitly export to client-side
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "/api",
    NEXT_PUBLIC_API_ORIGIN: process.env.NEXT_PUBLIC_API_ORIGIN,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
  },
  
  // Allow dev origins for development (CORS fix)
  // For Windows local development, add your local IP (e.g., "192.168.1.100:3200")
  // For production domain, add it via ALLOWED_DEV_ORIGINS environment variable
  allowedDevOrigins: [
    "localhost",
    "localhost:3200",
    "127.0.0.1",
    "127.0.0.1:3200",
    "*.ngrok-free.dev",
    "*.ngrok.io",
    ...extraDevOrigins,
  ],
  
  // Rewrite API requests to backend
  // Frontend /api/user/info → Backend http://localhost:8001/api/user/info (local backend)
  // In production, backend runs locally on 127.0.0.1:8001
  async rewrites() {
    // Backend runs locally on the same server
    // Use localhost for internal communication
    const apiPort = process.env.API_PORT || '8001'
    let backendUrl = process.env.BACKEND_URL || `http://127.0.0.1:${apiPort}`
    
    // If BACKEND_URL is ngrok URL, fallback to localhost for development
    // This prevents issues when ngrok tunnel is offline
    if (backendUrl && (backendUrl.includes('ngrok') || backendUrl.includes('https://'))) {
      // In development, prefer localhost for reliability
      // Ngrok URLs can be used in production, but localhost is more reliable for dev
      const isDevelopment = process.env.NODE_ENV !== 'production'
      if (isDevelopment) {
        console.log(`[next.config] Development mode detected, using localhost instead of ${backendUrl}`)
        backendUrl = `http://127.0.0.1:${apiPort}`
      }
    }
    
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`, // Keep /api prefix - backend needs it
      },
    ]
  },
  
  // Add custom headers for proxy requests
  async headers() {
    return [
      {
        source: '/api/:path*',
        headers: [
          {
            key: 'Connection',
            value: 'keep-alive',
          },
          {
            key: 'ngrok-skip-browser-warning',
            value: 'true',
          },
        ],
      },
      {
        source: '/:path*',
        headers: [
          {
            key: 'ngrok-skip-browser-warning',
            value: 'true',
          },
        ],
      },
    ]
  },
}

module.exports = nextConfig
