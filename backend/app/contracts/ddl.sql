-- backend/app/contracts/ddl.sql  【契约冻结:改/删字段须全队通知,加字段自由】
-- 数据分层: 原始层(jd_pool/talent_raw/signal, M1 产出) / 分析层(skill_dict/job_definition/job_skill/job_change_log/resume)
CREATE TABLE IF NOT EXISTS jd_pool (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source VARCHAR(32), source_detail VARCHAR(128),  -- source: 来源平台(D17，当前 linkedin)；source_detail: posting_domain/数据集标识(D39 2026-08-17)
  job_title VARCHAR(128), raw_text TEXT,
  duties TEXT, experience VARCHAR(255), quality FLOAT DEFAULT 0,  -- 2026-08-15 扩容 32->255 (D33); 2026-08-16 cleaner 提取上限 255（单行描述曾捕获整段致 1406）
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
-- 岗位技能证据链明细: 每条技能带 weight/confidence/evidence(反幻觉), is_required 区分必备/加分
CREATE TABLE IF NOT EXISTS job_skill (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  jd_id BIGINT, job_name VARCHAR(128), level VARCHAR(16),
  skills JSON, -- [{skill_id,name,weight,confidence,evidence,is_required}]
  duties TEXT, extracted_at DATETIME,
  INDEX idx_jobname (job_name)
);
-- 岗位定义主表(取代 emerging_job; 对应 PDF 岗位定义五要素 + 收集时间/来源, 无 status 见决策 D14)
CREATE TABLE IF NOT EXISTS job_definition (
  id INT PRIMARY KEY AUTO_INCREMENT,
  job_name VARCHAR(128) NOT NULL,
  core_duties TEXT,                -- 核心职责
  required_skills JSON,            -- 必备技能: [skill_dict.canonical, ...]
  bonus_skills JSON,               -- 加分技能: [skill_dict.canonical, ...]
  scenarios JSON,                  -- 典型行业应用场景: [string, ...]
  source JSON,                     -- 来源平台: ["Boss直聘","猎聘"] (仅记录平台, 见决策 D17)
  quality FLOAT DEFAULT 0,         -- 交叉验证质量分 0-1 (M1 机制, 独立于 source)
  is_emerging TINYINT(1) DEFAULT 0, -- 是否新岗位 (M2 聚类+LLM 判定+人工确认, 见决策 D12)
  evolution JSON,                  -- 演化阶段 {stage: 萌芽/增长/成熟/衰退, ...} (无数据不编造数字, 见 D13)
  first_seen DATETIME,             -- 首次出现时间 (演化分析依据)
  collected_at DATETIME,           -- 收集时间
  updated_at DATETIME,             -- 人工优化/最近修改时间
  INDEX idx_jobname (job_name),
  INDEX idx_is_emerging (is_emerging)
);
-- 既有岗位能力变更审计 (对应 PDF: 新增/删除/修改能力项 + 更新说明 + 数据源)
CREATE TABLE IF NOT EXISTS job_change_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  job_id BIGINT,                   -- 关联 job_definition.id
  change_type VARCHAR(32),         -- added/removed/modified/duties_changed/scenarios_added/scenarios_removed/evolution_changed (D32; 2026-08-15 扩容 16->32 以容纳 17 字符枚举, 见 P4)
  skill_name VARCHAR(128),         -- 变更技能 (对齐 skill_dict.canonical)
  detail JSON,                     -- 变更内容 {before?, after?}
  source VARCHAR(128),             -- 数据源/依据
  reason TEXT,                     -- 更新说明
  created_at DATETIME,
  INDEX idx_job (job_id)
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
