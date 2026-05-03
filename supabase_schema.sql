-- ═══════════════════════════════════════════════════════════
--   KisanMind — Supabase Database Schema
--   Run this SQL in Supabase → SQL Editor → Run
-- ═══════════════════════════════════════════════════════════

-- Farmers table
CREATE TABLE IF NOT EXISTS farmers (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     TEXT UNIQUE NOT NULL,
    name            TEXT DEFAULT 'Farmer',
    language        TEXT DEFAULT 'hi',
    location        TEXT,           -- JSON: {city, lat, lon}
    land_acres      NUMERIC,
    soil_type       TEXT,
    current_crops   TEXT,           -- JSON array
    crop_history    TEXT,           -- JSON array
    disease_events  TEXT,           -- JSON array (last 50)
    last_active     TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_farmers_telegram_id ON farmers(telegram_id);

-- RLS: each user can only see their own data
ALTER TABLE farmers ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (used by our backend)
CREATE POLICY "service_role_all" ON farmers
    FOR ALL USING (true);

-- ───────────────────────────────────────────────────────────
-- Optional: Disease events log (separate table for analytics)
-- ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS disease_logs (
    id          BIGSERIAL PRIMARY KEY,
    telegram_id TEXT NOT NULL,
    crop        TEXT,
    disease     TEXT,
    confidence  NUMERIC,
    treatment   TEXT,
    latitude    NUMERIC,
    longitude   NUMERIC,
    logged_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_disease_logs_telegram ON disease_logs(telegram_id);
CREATE INDEX IF NOT EXISTS idx_disease_logs_crop     ON disease_logs(crop);
CREATE INDEX IF NOT EXISTS idx_disease_logs_date     ON disease_logs(logged_at);

-- ───────────────────────────────────────────────────────────
-- Optional: Community alert tracking
-- ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS community_alerts (
    id          BIGSERIAL PRIMARY KEY,
    region      TEXT,   -- district/block name
    issue_type  TEXT,   -- disease / pest / weather
    issue_name  TEXT,
    report_count INT DEFAULT 1,
    first_seen  TIMESTAMPTZ DEFAULT NOW(),
    last_seen   TIMESTAMPTZ DEFAULT NOW()
);
