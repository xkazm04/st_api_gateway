CREATE TABLE IF NOT EXISTS api_health_tests (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    test_name VARCHAR(255) NOT NULL, 
    last_status VARCHAR(20) NOT NULL,  -- OK, ERROR, NA
    error_message TEXT,
    duration_ms INTEGER,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_service_test UNIQUE(service_name, test_name)
);

-- Index for faster queries when retrieving dashboard data
CREATE INDEX IF NOT EXISTS idx_health_tests_service_name ON api_health_tests(service_name);
CREATE INDEX IF NOT EXISTS idx_health_tests_updated_at ON api_health_tests(updated_at);