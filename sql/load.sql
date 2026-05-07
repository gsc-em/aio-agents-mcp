-- AIO Agents MCP — Data load script
-- Run AFTER schema.sql, with CSVs accessible to the Postgres server.
-- Usage from psql: \i load.sql
-- Or via psql -f load.sql -v csv_dir=/path/to/data

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Markets first (banners FK to it)
\copy aio.markets(market_id, country_iso, country_name, region, banner_count, confirmed_count, probable_count, inferred_count, unknown_count) FROM 'data/markets.csv' WITH (FORMAT csv, HEADER true);

-- Lookup tables
\copy aio.confidence_tiers(confidence_id, tier, description) FROM 'data/confidence_tiers.csv' WITH (FORMAT csv, HEADER true);
\copy aio.erp_systems(erp_id, erp_name) FROM 'data/erp_systems.csv' WITH (FORMAT csv, HEADER true);
\copy aio.procurement_platforms(procurement_id, procurement_name) FROM 'data/procurement_platforms.csv' WITH (FORMAT csv, HEADER true);
\copy aio.clouds(cloud_id, cloud_name) FROM 'data/clouds.csv' WITH (FORMAT csv, HEADER true);

-- Banners last
\copy aio.banners(banner_id, banner, country_iso, country_name, region, erp, cloud, procurement, confidence, raw_notes) FROM 'data/banners.csv' WITH (FORMAT csv, HEADER true);

-- Reset sequences after explicit-id loads
SELECT setval('aio.markets_market_id_seq', (SELECT MAX(market_id) FROM aio.markets));
SELECT setval('aio.confidence_tiers_confidence_id_seq', (SELECT MAX(confidence_id) FROM aio.confidence_tiers));
SELECT setval('aio.erp_systems_erp_id_seq', (SELECT MAX(erp_id) FROM aio.erp_systems));
SELECT setval('aio.procurement_platforms_procurement_id_seq', (SELECT MAX(procurement_id) FROM aio.procurement_platforms));
SELECT setval('aio.clouds_cloud_id_seq', (SELECT MAX(cloud_id) FROM aio.clouds));
SELECT setval('aio.banners_banner_id_seq', (SELECT MAX(banner_id) FROM aio.banners));

-- Validate
SELECT 'markets' AS tbl, COUNT(*) AS rows FROM aio.markets
UNION ALL SELECT 'banners', COUNT(*) FROM aio.banners
UNION ALL SELECT 'erp_systems', COUNT(*) FROM aio.erp_systems
UNION ALL SELECT 'procurement', COUNT(*) FROM aio.procurement_platforms
UNION ALL SELECT 'clouds', COUNT(*) FROM aio.clouds;
