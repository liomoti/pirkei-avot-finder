-- Migration: Add search_method column to ai_search_log
-- Safe to run on production: nullable column with no default, no data migration needed.
-- Existing rows will have NULL for search_method, which the admin panel handles
-- gracefully by showing an empty cell.
ALTER TABLE ai_search_log ADD COLUMN search_method VARCHAR(20) NULL;
