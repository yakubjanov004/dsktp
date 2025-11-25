-- Create reports table for storing manager reports
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    created_by BIGINT REFERENCES users(telegram_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_reports_created_by ON reports(created_by);

-- Add comment to the table
COMMENT ON TABLE reports IS 'Stores reports created by managers for various purposes';
