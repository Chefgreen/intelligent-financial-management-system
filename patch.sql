-- ============================================================
-- IFMS Database Patch — Run this ONCE in MySQL Workbench
-- Fixes "Unknown column" errors without losing any data
-- ============================================================

USE ifms_db;

-- ── Patch users table (add new columns if missing) ───────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone           VARCHAR(30)   DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_salary  DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS currency        VARCHAR(10)   DEFAULT 'ZMW';
ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret      VARCHAR(64)   DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled     TINYINT(1)    NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS jwt_version     INT           NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- ── Create financial_goals table if missing ───────────────────────
CREATE TABLE IF NOT EXISTS financial_goals (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT            NOT NULL,
    name        VARCHAR(150)   NOT NULL,
    target      DECIMAL(12,2)  NOT NULL,
    saved       DECIMAL(12,2)  NOT NULL DEFAULT 0,
    deadline    DATE           DEFAULT NULL,
    created_at  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Patch financial_goals if it existed without saved column ──────
ALTER TABLE financial_goals ADD COLUMN IF NOT EXISTS saved    DECIMAL(12,2) NOT NULL DEFAULT 0;
ALTER TABLE financial_goals ADD COLUMN IF NOT EXISTS deadline DATE DEFAULT NULL;

-- ── Create budget_plans table if missing ──────────────────────────
CREATE TABLE IF NOT EXISTS budget_plans (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT            NOT NULL,
    month           CHAR(7)        NOT NULL,
    income_basis    DECIMAL(12,2)  NOT NULL,
    needs_budget    DECIMAL(12,2)  NOT NULL,
    wants_budget    DECIMAL(12,2)  NOT NULL,
    savings_budget  DECIMAL(12,2)  NOT NULL,
    created_at      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_budget_user_month (user_id, month),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Create audit_log table if missing ────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT            DEFAULT NULL,
    event_type  VARCHAR(60)    NOT NULL,
    ip_address  VARCHAR(45)    DEFAULT NULL,
    user_agent  VARCHAR(255)   DEFAULT NULL,
    detail      TEXT           DEFAULT NULL,
    created_at  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_type (event_type),
    INDEX idx_audit_time (created_at)
);

-- ── Verify ────────────────────────────────────────────────────────
SELECT 'Patch complete!' AS status;
SHOW TABLES;
DESCRIBE users;
DESCRIBE financial_goals;
