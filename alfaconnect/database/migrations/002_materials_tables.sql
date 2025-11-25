-- Materials va Material Requests jadvallari yaratish

-- Materials jadvali
CREATE TABLE IF NOT EXISTS materials (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    price DECIMAL(10, 2),
    description TEXT,
    quantity INTEGER DEFAULT 0,
    serial_number VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Material requests jadvali
CREATE TABLE IF NOT EXISTS material_requests (
    id SERIAL PRIMARY KEY,
    description TEXT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    applications_id INTEGER,
    status VARCHAR(50) DEFAULT 'pending',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    approved_by INTEGER REFERENCES users(id)
);

-- Indexlar yaratish
CREATE INDEX IF NOT EXISTS idx_materials_name ON materials(name);
CREATE INDEX IF NOT EXISTS idx_materials_serial ON materials(serial_number);
CREATE INDEX IF NOT EXISTS idx_material_requests_user ON material_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_material_requests_status ON material_requests(status);

-- Trigger yaratish - updated_at ni avtomatik yangilash uchun
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_materials_updated_at
    BEFORE UPDATE ON materials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();