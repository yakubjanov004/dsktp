-- yangi status qiymatlarini qo‘shamiz
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'technician_order_status'
          AND e.enumlabel = 'in_call_center_supervisor'
    ) THEN
        ALTER TYPE technician_order_status ADD VALUE 'in_call_center_supervisor';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'technician_order_status'
          AND e.enumlabel = 'in_call_center_operator'
    ) THEN
        ALTER TYPE technician_order_status ADD VALUE 'in_call_center_operator';
    END IF;
END$$;
