-- ============================================================================
-- 07_fix_payment_methods.sql
-- Fix payment_methods table: add missing columns, remove Stripe columns
-- Run this if payment_methods was created before card_brand was added.
-- ============================================================================

-- Add card_brand if it doesn't exist
SET @exist := (SELECT COUNT(*) FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME = 'payment_methods'
               AND COLUMN_NAME = 'card_brand');
SET @sql := IF(@exist = 0,
    'ALTER TABLE payment_methods ADD COLUMN card_brand VARCHAR(20) DEFAULT ''unknown'' AFTER card_last4',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add card_name if it doesn't exist
SET @exist := (SELECT COUNT(*) FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME = 'payment_methods'
               AND COLUMN_NAME = 'card_name');
SET @sql := IF(@exist = 0,
    'ALTER TABLE payment_methods ADD COLUMN card_name VARCHAR(60) NOT NULL DEFAULT ''Titular'' AFTER card_brand',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add card_expiry if it doesn't exist
SET @exist := (SELECT COUNT(*) FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME = 'payment_methods'
               AND COLUMN_NAME = 'card_expiry');
SET @sql := IF(@exist = 0,
    'ALTER TABLE payment_methods ADD COLUMN card_expiry VARCHAR(5) NOT NULL DEFAULT ''00/00'' AFTER card_name',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add updated_at if it doesn't exist
SET @exist := (SELECT COUNT(*) FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME = 'payment_methods'
               AND COLUMN_NAME = 'updated_at');
SET @sql := IF(@exist = 0,
    'ALTER TABLE payment_methods ADD COLUMN updated_at DATETIME AFTER created_at',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Remove Stripe columns if they exist
SET @exist := (SELECT COUNT(*) FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME = 'payment_methods'
               AND COLUMN_NAME = 'stripe_customer_id');
SET @sql := IF(@exist > 0,
    'ALTER TABLE payment_methods DROP COLUMN stripe_customer_id',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @exist := (SELECT COUNT(*) FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
               AND TABLE_NAME = 'payment_methods'
               AND COLUMN_NAME = 'stripe_pm_id');
SET @sql := IF(@exist > 0,
    'ALTER TABLE payment_methods DROP COLUMN stripe_pm_id',
    'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'payment_methods table fixed successfully' AS result;
