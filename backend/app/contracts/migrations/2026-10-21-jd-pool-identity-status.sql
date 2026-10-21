-- Additive migration only. Do not execute until the pre-migration backup and
-- isolated restore verification described in the design document are approved.
ALTER TABLE jd_pool
  ADD COLUMN identity_status VARCHAR(16) NOT NULL DEFAULT 'unknown',
  ADD COLUMN content_eligible TINYINT(1) NULL DEFAULT NULL,
  ADD COLUMN identity_evidence TEXT NULL,
  ADD INDEX idx_identity_status (identity_status);
