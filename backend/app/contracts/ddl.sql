-- backend/app/contracts/ddl.sql  【契约冻结:改/删字段须全队通知,加字段自由】
CREATE TABLE IF NOT EXISTS jd_pool (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source VARCHAR(32), job_title VARCHAR(128), raw_text TEXT,
  duties TEXT, experience VARCHAR(32), quality FLOAT DEFAULT 0,
  dup_group VARCHAR(64), crawled_at DATETIME, status VARCHAR(16) DEFAULT 'raw',
  INDEX idx_status (status), INDEX idx_source (source)
);
CREATE TABLE IF NOT EXISTS `signal` (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  skill_or_job VARCHAR(128), signal_type VARCHAR(16),
  metric VARCHAR(16), value FLOAT, captured_at DATETIME,
  INDEX idx_soj (skill_or_job)
);
CREATE TABLE IF NOT EXISTS skill_dict (
  id INT PRIMARY KEY AUTO_INCREMENT,
  canonical VARCHAR(64) UNIQUE, aliases JSON, category VARCHAR(32),
  INDEX idx_canonical (canonical)
);
CREATE TABLE IF NOT EXISTS job_skill (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  jd_id BIGINT, job_name VARCHAR(128), level VARCHAR(16),
  skills JSON, duties TEXT, extracted_at DATETIME,
  INDEX idx_jobname (job_name)
);
CREATE TABLE IF NOT EXISTS emerging_job (
  id INT PRIMARY KEY AUTO_INCREMENT,
  job_name VARCHAR(128), definition TEXT, core_skills JSON,
  first_seen DATETIME, evolution JSON
);
CREATE TABLE IF NOT EXISTS resume (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  raw_format VARCHAR(8), skills JSON, experience JSON, parsed_at DATETIME
);
CREATE TABLE IF NOT EXISTS talent_raw (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source VARCHAR(32), identity_hint VARCHAR(128), raw_text TEXT,
  skills_hint JSON, experience_hint TEXT,
  quality FLOAT DEFAULT 0, dup_group VARCHAR(64),
  crawled_at DATETIME, status VARCHAR(16) DEFAULT 'raw',
  INDEX idx_status (status), INDEX idx_source (source)
);
