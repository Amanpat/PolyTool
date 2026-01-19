-- PolyTool ClickHouse Initialization Script
-- Creates database and readonly user for Grafana

-- Create polyttool database (may already exist via CLICKHOUSE_DB env)
CREATE DATABASE IF NOT EXISTS polyttool;

-- Create Grafana user with sha256_password
-- Password: grafana_readonly_local
-- Note: Grafana ClickHouse datasource sets max_execution_time, which is blocked by readonly=1
CREATE USER IF NOT EXISTS grafana_ro
IDENTIFIED WITH sha256_password BY 'grafana_readonly_local'
SETTINGS readonly = 0;

-- Grant SELECT access on polyttool database to grafana_ro
GRANT SELECT ON polyttool.* TO grafana_ro;

-- Grant access to system tables needed for ClickHouse datasource health checks
GRANT SELECT ON system.* TO grafana_ro;
