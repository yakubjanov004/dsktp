import { NextRequest, NextResponse } from 'next/server';

/**
 * Development log API endpoint
 * Only works in development environment
 * Receives logs from client-side and outputs them to terminal
 */
export async function POST(request: NextRequest) {
  // Only allow in development
  if (process.env.NODE_ENV === 'production') {
    return NextResponse.json(
      { error: 'Logging disabled in production' },
      { status: 403 }
    );
  }

  try {
    const body = await request.json();
    const { args } = body;

    if (!Array.isArray(args)) {
      return NextResponse.json(
        { error: 'Invalid request: args must be an array' },
        { status: 400 }
      );
    }

    // Log to terminal with prefix
    // Args are already formatted as strings from client
    console.log('[DEV-LOG]', ...args);

    return NextResponse.json({ success: true });
  } catch (error) {
    // In development, log the error
    if (process.env.NODE_ENV === 'development') {
      console.error('[DEV-LOG] Error processing log request:', error);
    }
    return NextResponse.json(
      { error: 'Failed to process log request' },
      { status: 500 }
    );
  }
}

