-- =========================
-- SEQUENTIAL USER ID SYSTEM
-- =========================

-- Create a custom sequence for sequential user IDs
CREATE SEQUENCE IF NOT EXISTS user_sequential_id_seq START 1;

-- Function to get next sequential user ID
CREATE OR REPLACE FUNCTION get_next_sequential_user_id()
RETURNS INTEGER AS $$
DECLARE
    next_id INTEGER;
BEGIN
    -- Get the next value from our custom sequence
    SELECT nextval('user_sequential_id_seq') INTO next_id;
    
    -- Check if this ID already exists in users table
    WHILE EXISTS (SELECT 1 FROM users WHERE id = next_id) LOOP
        SELECT nextval('user_sequential_id_seq') INTO next_id;
    END LOOP;
    
    RETURN next_id;
END;
$$ LANGUAGE plpgsql;

-- Drop existing function if it exists
DROP FUNCTION IF EXISTS create_user_sequential(BIGINT, TEXT, TEXT, TEXT, user_role);

-- Function to create user with sequential ID
CREATE OR REPLACE FUNCTION create_user_sequential(
    p_telegram_id BIGINT,
    p_username TEXT DEFAULT NULL,
    p_full_name TEXT DEFAULT NULL,
    p_phone TEXT DEFAULT NULL,
    p_role user_role DEFAULT 'client'
)
RETURNS TABLE(
    user_id INTEGER,
    user_telegram_id BIGINT,
    user_username TEXT,
    user_full_name TEXT,
    user_phone TEXT,
    user_role user_role,
    user_created_at TIMESTAMPTZ
) AS $$
DECLARE
    new_user_id INTEGER;
    ret_user_id INTEGER;
    ret_telegram_id BIGINT;
    ret_username TEXT;
    ret_full_name TEXT;
    ret_phone TEXT;
    ret_role user_role;
    ret_created_at TIMESTAMPTZ;
BEGIN
    -- Get next sequential ID
    SELECT get_next_sequential_user_id() INTO new_user_id;
    
    -- Insert user with sequential ID
    INSERT INTO users (id, telegram_id, username, full_name, phone, role)
    VALUES (new_user_id, p_telegram_id, p_username, p_full_name, p_phone, p_role)
    ON CONFLICT (telegram_id) DO UPDATE SET
        username = EXCLUDED.username,
        full_name = EXCLUDED.full_name,
        phone = EXCLUDED.phone,
        updated_at = NOW()
    RETURNING users.id, users.telegram_id, users.username, users.full_name, users.phone, users.role, users.created_at
    INTO ret_user_id, ret_telegram_id, ret_username, ret_full_name, ret_phone, ret_role, ret_created_at;
    
    create_user_sequential.user_id := ret_user_id;
    create_user_sequential.user_telegram_id := ret_telegram_id;
    create_user_sequential.user_username := ret_username;
    create_user_sequential.user_full_name := ret_full_name;
    create_user_sequential.user_phone := ret_phone;
    create_user_sequential.user_role := ret_role;
    create_user_sequential.user_created_at := ret_created_at;
    
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to reset sequence to match existing data
CREATE OR REPLACE FUNCTION reset_user_sequential_sequence()
RETURNS VOID AS $$
DECLARE
    max_id INTEGER;
BEGIN
    -- Get the maximum existing user ID
    SELECT COALESCE(MAX(id), 0) + 1 INTO max_id FROM users;
    
    -- Reset the sequence to start from the next available ID
    PERFORM setval('user_sequential_id_seq', max_id, false);
END;
$$ LANGUAGE plpgsql;

-- Reset the sequence to match existing data
SELECT reset_user_sequential_sequence();

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_users_id ON users(id);

COMMENT ON SEQUENCE user_sequential_id_seq IS 'Sequential ID generator for users table';
COMMENT ON FUNCTION get_next_sequential_user_id() IS 'Returns next available sequential user ID';
COMMENT ON FUNCTION create_user_sequential(BIGINT, TEXT, TEXT, TEXT, user_role) IS 'Creates user with sequential ID';
COMMENT ON FUNCTION reset_user_sequential_sequence() IS 'Resets sequence to match existing data';