-- Migration: Migrate connections table to use application_number
-- Date: 2025-01-20
-- Description: 
-- 1. Add application_number column to connections table
-- 2. Populate application_number from existing connection_id/technician_id/staff_id
-- 3. Add index for performance
-- 4. Keep old columns for backward compatibility (will be removed later)

-- Add application_number column
ALTER TABLE public.connections 
ADD COLUMN IF NOT EXISTS application_number VARCHAR(50);

-- Populate application_number from existing data
UPDATE public.connections c
SET application_number = (
    CASE 
        WHEN c.connection_id IS NOT NULL THEN
            (SELECT co.application_number 
             FROM connection_orders co 
             WHERE co.id = c.connection_id)
        WHEN c.technician_id IS NOT NULL THEN
            (SELECT tech.application_number 
             FROM technician_orders tech 
             WHERE tech.id = c.technician_id)
        WHEN c.staff_id IS NOT NULL THEN
            (SELECT so.application_number 
             FROM staff_orders so 
             WHERE so.id = c.staff_id)
        ELSE NULL
    END
)
WHERE application_number IS NULL;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_connections_application_number 
ON public.connections(application_number);

-- Log the results
DO $$
DECLARE
    total_rows INTEGER;
    filled_rows INTEGER;
    empty_rows INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_rows FROM public.connections;
    SELECT COUNT(*) INTO filled_rows FROM public.connections WHERE application_number IS NOT NULL;
    SELECT COUNT(*) INTO empty_rows FROM public.connections WHERE application_number IS NULL;
    
    RAISE NOTICE 'Migration completed: Total rows = %, Filled = %, Empty = %', 
        total_rows, filled_rows, empty_rows;
END $$;

