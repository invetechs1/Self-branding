-- ═══════════════════════════════════════════════════════════════════════
-- Dashboard login — real accounts, bcrypt-hashed passwords.
-- Applied after 0001_init.sql. Run scripts/create_user.py to add/update a
-- user (never insert a plaintext password directly).
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);
