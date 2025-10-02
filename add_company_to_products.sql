-- Add company field to products table for data segregation
-- This script should be run on the Railway production database

-- Add the company column
ALTER TABLE products ADD COLUMN company VARCHAR(200);

-- Update existing products to use a default company name
-- (You may want to update this to appropriate company values)
UPDATE products SET company = 'default_company' WHERE company IS NULL;

-- Make the column NOT NULL after setting default values
ALTER TABLE products ALTER COLUMN company SET NOT NULL;

-- Add index for performance
CREATE INDEX idx_products_company ON products(company);

-- Optional: Create a unique constraint for SKU per company
-- (This replaces the global unique constraint if desired)
-- ALTER TABLE products DROP CONSTRAINT IF EXISTS products_sku_key;
-- CREATE UNIQUE INDEX idx_products_sku_company ON products(sku, company) WHERE sku IS NOT NULL;