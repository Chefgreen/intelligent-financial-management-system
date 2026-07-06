-- ============================================================
-- IFMS — Complete Database Schema v2
-- All 10 functional modules covered.
-- Run this in MySQL Workbench to set up the database.
-- ============================================================

CREATE DATABASE IF NOT EXISTS ifms_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ifms_db;

-- ── MODULE 1 & 2: USERS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100)  NOT NULL,
    email           VARCHAR(150)  NOT NULL UNIQUE,
    password        VARCHAR(255)  NOT NULL,
    phone           VARCHAR(30)   DEFAULT NULL,
    monthly_salary  DECIMAL(12,2) DEFAULT NULL,
    currency        VARCHAR(10)   DEFAULT 'ZMW',
    mfa_secret      VARCHAR(64)   DEFAULT NULL,
    mfa_enabled     TINYINT(1)    NOT NULL DEFAULT 0,
    jwt_version     INT           NOT NULL DEFAULT 1,
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- ── MODULE 2: FINANCIAL GOALS ─────────────────────────────────────
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

-- ── MODULE 3: TRANSACTIONS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT            NOT NULL,
    type        ENUM('income','expense') NOT NULL,
    category    VARCHAR(100)   NOT NULL,
    amount      DECIMAL(12,2)  NOT NULL,
    description VARCHAR(255)   DEFAULT NULL,
    date        DATE           NOT NULL,
    created_at  DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_txn_user_date (user_id, date DESC),
    INDEX idx_txn_type (user_id, type)
);

-- ── MODULE 7: BUDGET PLANS ────────────────────────────────────────
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

-- ── MODULE 9: AUDIT LOG ───────────────────────────────────────────
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
