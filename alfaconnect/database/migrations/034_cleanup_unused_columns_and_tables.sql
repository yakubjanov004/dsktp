-- Migration 034: Cleanup unused columns and tables
-- This migration removes unused columns and tables to clean up the database

-- Remove unused columns from technician_orders table
-- The 'diagnostics' column is not being used and can be removed
ALTER TABLE technician_orders DROP COLUMN IF EXISTS diagnostics;

-- Drop unused tables
-- The 'migrations' table is not needed in production
DROP TABLE IF EXISTS migrations;

-- The 'reports' table is not being used
DROP TABLE IF EXISTS reports;

-- Add comments explaining the cleanup
COMMENT ON TABLE technician_orders IS 'Technician orders table - stores technical service requests without unused diagnostics column';
COMMENT ON TABLE connection_orders IS 'Connection orders table - stores new connection requests';
COMMENT ON TABLE staff_orders IS 'Staff orders table - stores staff-created orders';
