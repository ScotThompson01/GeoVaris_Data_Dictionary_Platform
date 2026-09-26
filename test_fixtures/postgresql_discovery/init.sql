CREATE SCHEMA operations;

CREATE TABLE operations.facilities (
    facility_id UUID PRIMARY KEY,
    facility_code VARCHAR(20) NOT NULL UNIQUE,
    facility_name VARCHAR(100) NOT NULL,
    latitude NUMERIC(8,5),
    longitude NUMERIC(8,5),
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    opened_date DATE,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

COMMENT ON TABLE operations.facilities IS
    'Synthetic facilities used for GeoVaris discovery validation.';

COMMENT ON COLUMN operations.facilities.facility_code IS
    'Synthetic unique facility identifier.';

COMMENT ON COLUMN operations.facilities.latitude IS
    'Synthetic latitude used for metadata discovery testing.';

CREATE TABLE operations.work_orders (
    work_order_id BIGINT PRIMARY KEY,
    facility_id UUID NOT NULL,
    work_order_number VARCHAR(30) NOT NULL UNIQUE,
    description TEXT,
    estimated_cost NUMERIC(12,2),
    is_emergency BOOLEAN NOT NULL DEFAULT FALSE,
    scheduled_date DATE,
    completed_at TIMESTAMP
);

CREATE VIEW operations.active_facilities AS
SELECT
    facility_id,
    facility_code,
    facility_name,
    latitude,
    longitude
FROM operations.facilities
WHERE status = 'ACTIVE';

CREATE ROLE geovaris_discovery_reader
    LOGIN
    PASSWORD 'discovery_test_only_not_for_deployment';

GRANT CONNECT ON DATABASE geovaris_discovery_test
    TO geovaris_discovery_reader;

GRANT USAGE ON SCHEMA operations
    TO geovaris_discovery_reader;

GRANT SELECT ON ALL TABLES IN SCHEMA operations
    TO geovaris_discovery_reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA operations
    GRANT SELECT ON TABLES TO geovaris_discovery_reader;

ALTER ROLE geovaris_discovery_reader
    SET default_transaction_read_only = on;
