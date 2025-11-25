-- staff_orders jadvali uchun indekslar
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_staff_ccs_active_created
    ON staff_orders (created_at, id)
    WHERE status='in_call_center_supervisor' AND is_active=TRUE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_staff_status_active
    ON staff_orders (status, is_active);
