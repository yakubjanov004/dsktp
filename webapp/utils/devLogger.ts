/**
 * Universal development logger
 * Works on both server and client side
 * Server: logs directly to terminal
 * Client: sends logs to /api/dev-log endpoint
 */

// Check if we're on the server side
const isServer = typeof window === 'undefined';

// Helper to process arguments for logging
// Automatically stringifies large objects
const processArgs = (args: any[]): any[] => {
  return args.map((arg) => {
    if (typeof arg === 'object' && arg !== null) {
      try {
        // Stringify objects for better readability
        const stringified = JSON.stringify(arg, null, 2);
        // Return as string for consistent formatting
        return stringified;
      } catch (error) {
        // If stringification fails, return error message
        return `[Stringify Error: ${String(error)}] ${String(arg)}`;
      }
    }
    // Return primitives as-is
    return arg;
  });
};

// Main log function
export const log = (...args: any[]): void => {
  const prefix = '[DEV-LOG]';
  const processedArgs = processArgs(args);

  if (isServer) {
    // Server-side: log directly to terminal
    console.log(prefix, ...processedArgs);
  } else {
    // Client-side: send to API endpoint
    // Convert all args to strings for transmission
    const stringArgs = processedArgs.map((arg) => {
      if (typeof arg === 'string') {
        return arg;
      }
      return String(arg);
    });

    fetch('/api/dev-log', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        args: stringArgs,
      }),
    }).catch((error) => {
      // Silently fail if API is not available (e.g., in production)
      // This prevents console errors in production
      if (process.env.NODE_ENV === 'development') {
        console.warn('[DEV-LOG] Failed to send log to server:', error);
      }
    });
  }
};

