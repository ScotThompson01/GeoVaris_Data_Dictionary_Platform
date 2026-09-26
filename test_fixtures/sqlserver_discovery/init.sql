CREATE DATABASE geovaris_discovery_test;
GO

USE geovaris_discovery_test;
GO

CREATE SCHEMA operations;
GO

CREATE TABLE operations.facilities (
    facility_id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    facility_code VARCHAR(20) NOT NULL UNIQUE,
    facility_name NVARCHAR(100) NOT NULL,
    latitude DECIMAL(8,5) NULL,
    longitude DECIMAL(8,5) NULL,
    status VARCHAR(20) NOT NULL
        CONSTRAINT DF_facilities_status DEFAULT 'ACTIVE',
    opened_date DATE NULL,
    last_updated DATETIME2 NOT NULL
        CONSTRAINT DF_facilities_last_updated DEFAULT SYSDATETIME(),
    notes NVARCHAR(MAX) NULL
);
GO

EXEC sys.sp_addextendedproperty
    @name = N'MS_Description',
    @value = N'Synthetic unique facility identifier.',
    @level0type = N'SCHEMA',
    @level0name = N'operations',
    @level1type = N'TABLE',
    @level1name = N'facilities',
    @level2type = N'COLUMN',
    @level2name = N'facility_code';
GO

EXEC sys.sp_addextendedproperty
    @name = N'MS_Description',
    @value = N'Synthetic latitude used for metadata discovery testing.',
    @level0type = N'SCHEMA',
    @level0name = N'operations',
    @level1type = N'TABLE',
    @level1name = N'facilities',
    @level2type = N'COLUMN',
    @level2name = N'latitude';
GO

CREATE TABLE operations.work_orders (
    work_order_id BIGINT NOT NULL PRIMARY KEY,
    facility_id UNIQUEIDENTIFIER NOT NULL,
    work_order_number VARCHAR(30) NOT NULL UNIQUE,
    description NVARCHAR(MAX) NULL,
    estimated_cost DECIMAL(12,2) NULL,
    is_emergency BIT NOT NULL
        CONSTRAINT DF_work_orders_emergency DEFAULT 0,
    scheduled_date DATE NULL,
    completed_at DATETIME2 NULL
);
GO

CREATE VIEW operations.active_facilities AS
SELECT
    facility_id,
    facility_code,
    facility_name,
    latitude,
    longitude
FROM operations.facilities
WHERE status = 'ACTIVE';
GO

CREATE LOGIN geovaris_discovery_reader
    WITH PASSWORD = 'Discovery_test_only_not_for_deployment_1!';
GO

CREATE USER geovaris_discovery_reader
    FOR LOGIN geovaris_discovery_reader;
GO

GRANT CONNECT TO geovaris_discovery_reader;
GRANT VIEW DEFINITION TO geovaris_discovery_reader;
GO
