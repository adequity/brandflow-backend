-- Add reject_reason column to posts table if it doesn't exist
ALTER TABLE posts ADD COLUMN IF NOT EXISTS reject_reason TEXT;
