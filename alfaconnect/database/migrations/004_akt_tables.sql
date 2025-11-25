-- AKT hujjatlari va reyting tizimi uchun jadvallar
-- Migration: 004_akt_tables.sql
-- Created: 2025-01-14

-- AKT hujjatlari jadvali
CREATE TABLE IF NOT EXISTS akt_documents (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL,
    request_type VARCHAR(20) NOT NULL CHECK (request_type IN ('connection', 'technician', 'staff')),
    akt_number VARCHAR(50) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_to_client_at TIMESTAMP NULL,
    UNIQUE(request_id, request_type)
);

-- AKT reytinglari jadvali
CREATE TABLE IF NOT EXISTS akt_ratings (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL,
    request_type VARCHAR(20) NOT NULL CHECK (request_type IN ('connection', 'technician', 'staff')),
    rating INTEGER NOT NULL CHECK (rating >= 0 AND rating <= 5), -- 0 ga ruxsat berish
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(request_id, request_type)
);

-- Indexlar
CREATE INDEX IF NOT EXISTS idx_akt_documents_request ON akt_documents(request_id, request_type);
CREATE INDEX IF NOT EXISTS idx_akt_documents_created ON akt_documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_akt_documents_sent ON akt_documents(sent_to_client_at);

CREATE INDEX IF NOT EXISTS idx_akt_ratings_request ON akt_ratings(request_id, request_type);
CREATE INDEX IF NOT EXISTS idx_akt_ratings_rating ON akt_ratings(rating);
CREATE INDEX IF NOT EXISTS idx_akt_ratings_created ON akt_ratings(created_at DESC);

-- Material requests jadvaliga yangi ustunlar qo'shish (agar mavjud bo'lmasa)
DO $$ 
BEGIN
    -- connection_order_id ustuni
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' AND column_name = 'connection_order_id') THEN
        ALTER TABLE material_requests ADD COLUMN connection_order_id INTEGER;
    END IF;
    
    -- technician_order_id ustuni
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' AND column_name = 'technician_order_id') THEN
        ALTER TABLE material_requests ADD COLUMN technician_order_id INTEGER;
    END IF;
    
    -- staff_order_id ustuni
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' AND column_name = 'staff_order_id') THEN
        ALTER TABLE material_requests ADD COLUMN staff_order_id INTEGER;
    END IF;
    
    -- quantity ustuni
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' AND column_name = 'quantity') THEN
        ALTER TABLE material_requests ADD COLUMN quantity INTEGER DEFAULT 1;
    END IF;
    
    -- price ustuni
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' AND column_name = 'price') THEN
        ALTER TABLE material_requests ADD COLUMN price DECIMAL(10,2) DEFAULT 0;
    END IF;
    
    -- total_price ustuni
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'material_requests' AND column_name = 'total_price') THEN
        ALTER TABLE material_requests ADD COLUMN total_price DECIMAL(10,2) DEFAULT 0;
    END IF;
END $$;

-- Foreign key constraints (agar mavjud bo'lmasa)
DO $$
BEGIN
    -- connection_orders foreign key
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'fk_material_requests_connection_order') THEN
        ALTER TABLE material_requests 
        ADD CONSTRAINT fk_material_requests_connection_order 
        FOREIGN KEY (connection_order_id) REFERENCES connection_orders(id);
    END IF;
    
    -- technician_orders foreign key
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'fk_material_requests_technician_order') THEN
        ALTER TABLE material_requests 
        ADD CONSTRAINT fk_material_requests_technician_order 
        FOREIGN KEY (technician_order_id) REFERENCES technician_orders(id);
    END IF;
    
    -- staff_orders foreign key
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'fk_material_requests_staff_order') THEN
        ALTER TABLE material_requests 
        ADD CONSTRAINT fk_material_requests_staff_order 
        FOREIGN KEY (staff_order_id) REFERENCES staff_orders(id);
    END IF;
END $$;

-- Comments
COMMENT ON TABLE akt_documents IS 'AKT hujjatlari ma''lumotlari';
COMMENT ON TABLE akt_ratings IS 'AKT reytinglari va izohlari';

COMMENT ON COLUMN akt_documents.request_id IS 'Zayavka ID';
COMMENT ON COLUMN akt_documents.request_type IS 'Zayavka turi (connection, technician, staff)';
COMMENT ON COLUMN akt_documents.akt_number IS 'AKT raqami (AKT-{request_id}-{YYYYMMDD})';
COMMENT ON COLUMN akt_documents.file_path IS 'Fayl yo''li';
COMMENT ON COLUMN akt_documents.file_hash IS 'Fayl SHA256 hash';
COMMENT ON COLUMN akt_documents.sent_to_client_at IS 'Mijozga yuborilgan vaqt';

COMMENT ON COLUMN akt_ratings.request_id IS 'Zayavka ID';
COMMENT ON COLUMN akt_ratings.request_type IS 'Zayavka turi (connection, technician, staff)';
COMMENT ON COLUMN akt_ratings.rating IS 'Reyting (1-5)';
COMMENT ON COLUMN akt_ratings.comment IS 'Mijoz izohi';
