-- Migration 033: Validate application_number data integrity before refactoring
-- This migration checks data integrity and reports any issues before the main refactoring

-- Create a temporary table to store validation results
CREATE TEMP TABLE validation_results (
    check_name TEXT,
    status TEXT,
    message TEXT,
    count INTEGER DEFAULT 0
);

-- Check 1: Verify all connection_orders have application_number
INSERT INTO validation_results (check_name, status, message, count)
SELECT 
    'connection_orders_application_number',
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END,
    'Connection orders missing application_number: ' || COUNT(*)::text,
    COUNT(*)
FROM connection_orders 
WHERE application_number IS NULL OR application_number = '';

-- Check 2: Verify all technician_orders have application_number
INSERT INTO validation_results (check_name, status, message, count)
SELECT 
    'technician_orders_application_number',
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END,
    'Technician orders missing application_number: ' || COUNT(*)::text,
    COUNT(*)
FROM technician_orders 
WHERE application_number IS NULL OR application_number = '';

-- Check 3: Verify all staff_orders have application_number
INSERT INTO validation_results (check_name, status, message, count)
SELECT 
    'staff_orders_application_number',
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END,
    'Staff orders missing application_number: ' || COUNT(*)::text,
    COUNT(*)
FROM staff_orders 
WHERE application_number IS NULL OR application_number = '';

-- Check 4: Check for orphaned material_requests (no matching order)
INSERT INTO validation_results (check_name, status, message, count)
SELECT 
    'orphaned_material_requests',
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'WARN'
    END,
    'Material requests without matching orders: ' || COUNT(*)::text,
    COUNT(*)
FROM material_requests mr
LEFT JOIN connection_orders co ON co.application_number = mr.application_number
LEFT JOIN technician_orders to ON to.application_number = mr.application_number
LEFT JOIN staff_orders so ON so.application_number = mr.application_number
WHERE co.id IS NULL AND to.id IS NULL AND so.id IS NULL;

-- Check 5: Check for orphaned akt_documents
INSERT INTO validation_results (check_name, status, message, count)
SELECT 
    'orphaned_akt_documents',
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'WARN'
    END,
    'AKT documents without matching orders: ' || COUNT(*)::text,
    COUNT(*)
FROM akt_documents ad
LEFT JOIN connection_orders co ON co.application_number = ad.application_number
LEFT JOIN technician_orders to ON to.application_number = ad.application_number
LEFT JOIN staff_orders so ON so.application_number = ad.application_number
WHERE co.id IS NULL AND to.id IS NULL AND so.id IS NULL;

-- Check 6: Check for orphaned akt_ratings
INSERT INTO validation_results (check_name, status, message, count)
SELECT 
    'orphaned_akt_ratings',
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'WARN'
    END,
    'AKT ratings without matching orders: ' || COUNT(*)::text,
    COUNT(*)
FROM akt_ratings ar
LEFT JOIN connection_orders co ON co.application_number = ar.application_number
LEFT JOIN technician_orders to ON to.application_number = ar.application_number
LEFT JOIN staff_orders so ON so.application_number = ar.application_number
WHERE co.id IS NULL AND to.id IS NULL AND so.id IS NULL;

-- Check 7: Verify application_number uniqueness across all order types
INSERT INTO validation_results (check_name, status, message, count)
SELECT 
    'duplicate_application_numbers',
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS'
        ELSE 'FAIL'
    END,
    'Duplicate application numbers found: ' || COUNT(*)::text,
    COUNT(*)
FROM (
    SELECT application_number, COUNT(*) as cnt
    FROM (
        SELECT application_number FROM connection_orders
        UNION ALL
        SELECT application_number FROM technician_orders
        UNION ALL
        SELECT application_number FROM staff_orders
    ) all_orders
    GROUP BY application_number
    HAVING COUNT(*) > 1
) duplicates;

-- Display validation results
SELECT 
    check_name,
    status,
    message,
    count
FROM validation_results
ORDER BY 
    CASE status 
        WHEN 'FAIL' THEN 1
        WHEN 'WARN' THEN 2
        WHEN 'PASS' THEN 3
    END,
    check_name;

-- Check if any critical validations failed
DO $$
DECLARE
    fail_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO fail_count
    FROM validation_results
    WHERE status = 'FAIL';
    
    IF fail_count > 0 THEN
        RAISE EXCEPTION 'Validation failed! % critical issues found. Please fix before proceeding.', fail_count;
    ELSE
        RAISE NOTICE 'Validation passed! All critical checks successful.';
    END IF;
END $$;

-- Add comments
COMMENT ON TABLE validation_results IS 'Temporary table for pre-migration validation results';
