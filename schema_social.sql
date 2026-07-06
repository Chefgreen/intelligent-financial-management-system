-- ============================================================
-- IFMS — Schema Additions for Social + Passkey Update
-- Run AFTER the original schema.sql
-- ============================================================

USE ifms_db;

-- ── Extend users table ────────────────────────────────────────────────
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS avatar       VARCHAR(255) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS bio          VARCHAR(300) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS is_verified  TINYINT(1)   NOT NULL DEFAULT 0;

-- ── PASSKEYS (WebAuthn) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS passkeys (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT          NOT NULL,
    credential_id VARCHAR(512) NOT NULL UNIQUE,
    public_key    TEXT         NOT NULL,
    sign_count    INT          NOT NULL DEFAULT 0,
    device_name   VARCHAR(100) DEFAULT 'device',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_passkeys_user (user_id)
);

-- ── TIPS FEED ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tips (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT          NOT NULL,
    body       VARCHAR(500) NOT NULL,
    tip_type   ENUM('tip','question','milestone') NOT NULL DEFAULT 'tip',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_tips_user (user_id),
    INDEX idx_tips_time (created_at DESC)
);

-- ── TIP LIKES ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tip_likes (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    tip_id     INT NOT NULL,
    user_id    INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_tip_like (tip_id, user_id),
    FOREIGN KEY (tip_id)  REFERENCES tips(id)  ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── TIP REPLIES ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tip_replies (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    tip_id     INT          NOT NULL,
    user_id    INT          NOT NULL,
    body       VARCHAR(300) NOT NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tip_id)  REFERENCES tips(id)  ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_replies_tip (tip_id)
);

-- ── FOLLOWS ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS follows (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    follower_id INT NOT NULL,
    followed_id INT NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_follow (follower_id, followed_id),
    FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (followed_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_follows_follower (follower_id),
    INDEX idx_follows_followed (followed_id)
);
