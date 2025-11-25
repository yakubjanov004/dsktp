import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { log } from '@/utils/devLogger'

/**
 * Next.js middleware
 * Currently minimal - Cloudflare Tunnel handles SSL/TLS termination
 * Can be extended for authentication, rate limiting, etc.
 */
export function middleware(request: NextRequest) {
  // Test server-side logger
  log('Server-side log from middleware:', {
    path: request.nextUrl.pathname,
    method: request.method,
    timestamp: new Date().toISOString()
  })
  
  return NextResponse.next()
}

// Only run middleware on non-static routes
// Exclude WebSocket paths (/api/ws/*) to avoid upgrade request errors in Next.js dev server
export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|api/ws|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}

