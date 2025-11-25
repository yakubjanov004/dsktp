-- =========================
-- ADD USER ONLINE STATUS (TTL-based)
-- =========================
-- Migration: Add last_seen_at column to users table
-- Purpose: Track user last seen timestamp for TTL-based online status calculation
-- 
-- Note: is_online is NOT stored in database. It is calculated from last_seen_at:
--   - If (now - last_seen_at) <= 60 seconds → online
--   - Otherwise → offline
--
-- This ensures: webapp open = heartbeat active = last_seen_at fresh = online
--                webapp closed = heartbeat stops = last_seen_at stale = offline

-- Add last_seen_at column (nullable, will be set by heartbeat)
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP WITH TIME ZONE;

-- Add is_online column (kept for backward compatibility, but not actively used)
-- TTL-based calculation takes precedence
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS is_online BOOLEAN NOT NULL DEFAULT FALSE;

-- Create index for last_seen_at queries (most important for TTL calculation)
CREATE INDEX IF NOT EXISTS idx_users_last_seen_at ON users(last_seen_at) WHERE last_seen_at IS NOT NULL;

-- Create index for faster queries on online status (for backward compatibility)
CREATE INDEX IF NOT EXISTS idx_users_is_online ON users(is_online) WHERE is_online = TRUE;

-- Add comment to columns
COMMENT ON COLUMN users.last_seen_at IS 'Timestamp when user was last seen. Used to calculate is_online: if (now - last_seen_at) <= 60s then online, else offline';
COMMENT ON COLUMN users.is_online IS 'DEPRECATED: Use TTL calculation from last_seen_at instead. Kept for backward compatibility.';

