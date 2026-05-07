-- AIO Agents MCP — Postgres schema
-- Database: aio_agents
-- Host: pg-aio-agents-fr (Azure Postgres Flexible Server, France Central)
-- Operator: GreenCore Solutions Corp.

CREATE SCHEMA IF NOT EXISTS aio;

-- Markets (countries)
CREATE TABLE IF NOT EXISTS aio.markets (
    market_id       SERIAL PRIMARY KEY,
    country_iso     CHAR(2) UNIQUE NOT NULL,
    country_name    VARCHAR(80) NOT NULL,
    region          VARCHAR(80),
    banner_count    INTEGER DEFAULT 0,
    confirmed_count INTEGER DEFAULT 0,
    probable_count  INTEGER DEFAULT 0,
    inferred_count  INTEGER DEFAULT 0,
    unknown_count   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Confidence tier lookup
CREATE TABLE IF NOT EXISTS aio.confidence_tiers (
    confidence_id   SERIAL PRIMARY KEY,
    tier            VARCHAR(20) UNIQUE NOT NULL,
    description     TEXT
);

-- ERP systems lookup
CREATE TABLE IF NOT EXISTS aio.erp_systems (
    erp_id          SERIAL PRIMARY KEY,
    erp_name        VARCHAR(120) UNIQUE NOT NULL
);

-- Procurement platforms lookup
CREATE TABLE IF NOT EXISTS aio.procurement_platforms (
    procurement_id  SERIAL PRIMARY KEY,
    procurement_name VARCHAR(120) UNIQUE NOT NULL
);

-- Clouds lookup
CREATE TABLE IF NOT EXISTS aio.clouds (
    cloud_id        SERIAL PRIMARY KEY,
    cloud_name      VARCHAR(120) UNIQUE NOT NULL
);

-- Banners (denormalized for query speed — 2,397 rows, fits comfortably in memory)
CREATE TABLE IF NOT EXISTS aio.banners (
    banner_id       SERIAL PRIMARY KEY,
    banner          VARCHAR(120) NOT NULL,
    country_iso     CHAR(2) NOT NULL REFERENCES aio.markets(country_iso),
    country_name    VARCHAR(80),
    region          VARCHAR(80),
    erp             VARCHAR(120),
    cloud           VARCHAR(120),
    procurement     VARCHAR(120),
    confidence      VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
    raw_notes       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indices for the queries the MCP tools will run
CREATE INDEX IF NOT EXISTS idx_banners_country ON aio.banners(country_iso);
CREATE INDEX IF NOT EXISTS idx_banners_erp     ON aio.banners(erp);
CREATE INDEX IF NOT EXISTS idx_banners_cloud   ON aio.banners(cloud);
CREATE INDEX IF NOT EXISTS idx_banners_proc    ON aio.banners(procurement);
CREATE INDEX IF NOT EXISTS idx_banners_conf    ON aio.banners(confidence);
CREATE INDEX IF NOT EXISTS idx_banners_region  ON aio.banners(region);

-- Full-text search on banner names (for fuzzy lookups)
CREATE INDEX IF NOT EXISTS idx_banners_name_trgm ON aio.banners USING GIN (banner gin_trgm_ops);
-- (requires extension pg_trgm: CREATE EXTENSION IF NOT EXISTS pg_trgm;)

-- View: strike targets (high-confidence banners on cloud-native ERP)
CREATE OR REPLACE VIEW aio.v_strike_targets AS
SELECT
    banner_id,
    banner,
    country_iso,
    country_name,
    region,
    erp,
    cloud,
    procurement,
    confidence,
    CASE
        WHEN confidence = 'CONFIRMED' THEN 100
        WHEN confidence = 'PROBABLE'  THEN 70
        WHEN confidence = 'INFERRED'  THEN 50
        WHEN confidence = 'CONTESTED' THEN 30
        ELSE 10
    END AS strike_score
FROM aio.banners
WHERE erp IS NOT NULL
  AND cloud IS NOT NULL
  AND procurement IS NOT NULL
ORDER BY strike_score DESC, country_iso, banner;

-- View: agentic readiness by region (revenue-weighted proxy via confirmed banner count)
CREATE OR REPLACE VIEW aio.v_agentic_readiness AS
SELECT
    region,
    COUNT(*) AS total_banners,
    SUM(CASE WHEN confidence = 'CONFIRMED' THEN 1 ELSE 0 END) AS confirmed,
    SUM(CASE WHEN confidence IN ('CONFIRMED','PROBABLE','INFERRED') THEN 1 ELSE 0 END) AS attributed,
    ROUND(100.0 * SUM(CASE WHEN confidence IN ('CONFIRMED','PROBABLE','INFERRED') THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0), 1) AS attribution_pct
FROM aio.banners
WHERE region IS NOT NULL
GROUP BY region
ORDER BY attribution_pct DESC NULLS LAST;
