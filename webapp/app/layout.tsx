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
    <html lang="en" suppressHydrationWarning>
      <head>
        <script src="https://telegram.org/js/telegram-web-app.js" async></script>
        {/* Meta tag to bypass ngrok warning page */}
        <meta name="ngrok-skip-browser-warning" content="true" />
        {/* Script to bypass ngrok warning page by adding header to all requests */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                // Bypass ngrok warning page - run immediately before page loads
                const isNgrok = window.location.hostname.includes('ngrok-free.dev') || 
                               window.location.hostname.includes('ngrok.io') ||
                               window.location.hostname.includes('ngrok.app');
                
                if (isNgrok) {
                  // Set cookie to skip warning (must be set before any requests)
                  document.cookie = 'ngrok-skip-browser-warning=true; path=/; max-age=31536000; SameSite=None; Secure';
                  
                  // Override fetch to always add header
                  const originalFetch = window.fetch;
                  window.fetch = function(...args) {
                    const [url, options = {}] = args;
                    const headers = new Headers(options.headers || {});
                    headers.set('ngrok-skip-browser-warning', 'true');
                    const newOptions = {
                      ...options,
                      headers: headers,
                    };
                    return originalFetch.apply(this, [url, newOptions]);
                  };
                  
                  // Override XMLHttpRequest to always add header
                  const originalOpen = XMLHttpRequest.prototype.open;
                  const originalSend = XMLHttpRequest.prototype.send;
                  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
                    this._ngrokUrl = url;
                    return originalOpen.apply(this, [method, url, ...rest]);
                  };
                  XMLHttpRequest.prototype.send = function(...args) {
                    try {
                      this.setRequestHeader('ngrok-skip-browser-warning', 'true');
                    } catch (e) {
                      // Header already set or request already sent
                    }
                    return originalSend.apply(this, args);
                  };
                  
                  // Intercept link clicks to add header
                  document.addEventListener('click', function(e) {
                    const target = e.target.closest('a');
                    if (target && target.href) {
                      const url = new URL(target.href, window.location.href);
                      if (url.hostname.includes('ngrok')) {
                        e.preventDefault();
                        window.location.href = url.href;
                      }
                    }
                  }, true);
                }
              })();
              
              // Suppress Telegram SDK WebSocket errors (expected in development/ngrok)
              // These errors occur when Telegram SDK tries to connect to their WebSocket API
              // for file downloads/media handling, which may fail in development environments
              (function() {
                const originalConsoleError = console.error;
                const originalConsoleWarn = console.warn;
                
                // Suppress Telegram SDK WebSocket errors
                const suppressTelegramWsErrors = (args) => {
                  if (args && args.length > 0) {
                    // Check all arguments for Telegram WebSocket error patterns
                    const argString = args.map(arg => {
                      if (typeof arg === 'string') return arg;
                      if (arg && typeof arg === 'object') {
                        try {
                          return JSON.stringify(arg);
                        } catch (e) {
                          return String(arg);
                        }
                      }
                      return String(arg);
                    }).join(' ');
                    
                    // Check if it's a Telegram WebSocket error or Next.js HMR error
                    const isTelegramWsError = 
                      argString.includes('zws') && argString.includes('web.telegram.org') ||
                      argString.includes('WebSocket connection to') && argString.includes('telegram.org') ||
                      argString.includes('WebSocket connection failed') && argString.includes('telegram.org') ||
                      argString.includes('WebSocket connection timeout') ||
                      (argString.includes('WebSocket') && argString.includes('telegram.org')) ||
                      (argString.includes('apiws') && argString.includes('telegram.org'));
                    
                    // Suppress Next.js HMR WebSocket errors (common in development)
                    const isHmrError = 
                      argString.includes('webpack-hmr') ||
                      (argString.includes('WebSocket') && argString.includes('_next'));
                    
                    if (isTelegramWsError || isHmrError) {
                      // Suppress these errors - they're expected in development
                      return;
                    }
                  }
                  // Not a Telegram WS error, log normally
                  originalConsoleError.apply(console, args);
                };
                
                // Override console.error to filter Telegram WebSocket errors
                console.error = function(...args) {
                  suppressTelegramWsErrors(args);
                };
                
                // Also filter console.warn for Telegram WebSocket warnings
                console.warn = function(...args) {
                  if (args && args.length > 0) {
                    const argString = args.map(arg => String(arg)).join(' ');
                    const isTelegramWsWarning = 
                      argString.includes('telegram.org') && argString.includes('WebSocket') ||
                      argString.includes('Using fallback connection');
                    
                    if (isTelegramWsWarning) {
                      // Suppress Telegram WebSocket warnings
                      return;
                    }
                  }
                  originalConsoleWarn.apply(console, args);
                };
              })();
            `,
          }}
        />
      </head>
      <body className={inter.className}>{children}</body>
    </html>
  )
}
