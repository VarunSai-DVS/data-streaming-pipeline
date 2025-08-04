-- Database Schema for Clickstream Analytics Pipeline
-- Run this in DBeaver or any PostgreSQL client

-- Drop existing tables if they exist
DROP TABLE IF EXISTS clickstream_events CASCADE;
DROP TABLE IF EXISTS realtime_metrics CASCADE;
DROP TABLE IF EXISTS page_metrics CASCADE;
DROP TABLE IF EXISTS user_behavior CASCADE;
DROP TABLE IF EXISTS device_analytics CASCADE;

-- Create clickstream_events table
CREATE TABLE clickstream_events (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50),
    page_url VARCHAR(500),
    event_type VARCHAR(50),
    timestamp TIMESTAMP,
    session_id VARCHAR(100),
    device VARCHAR(50),
    region VARCHAR(50),
    referrer VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create realtime_metrics table
CREATE TABLE realtime_metrics (
    id SERIAL PRIMARY KEY,
    metric_timestamp TIMESTAMP,
    total_events INTEGER,
    unique_users INTEGER,
    unique_sessions INTEGER,
    page_views INTEGER,
    purchases INTEGER,
    cart_additions INTEGER,
    bounce_rate DECIMAL(5,2),
    avg_session_duration INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create page_metrics table
CREATE TABLE page_metrics (
    id SERIAL PRIMARY KEY,
    page_url VARCHAR(500),
    view_count INTEGER,
    unique_visitors INTEGER,
    avg_time_on_page INTEGER,
    bounce_rate DECIMAL(5,2),
    conversion_rate DECIMAL(5,2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_behavior table
CREATE TABLE user_behavior (
    user_id VARCHAR(50) PRIMARY KEY,
    sessions INTEGER,
    events INTEGER,
    purchases INTEGER,
    last_active TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create device_analytics table
CREATE TABLE device_analytics (
    id SERIAL PRIMARY KEY,
    dimension_type VARCHAR(50),
    dimension_value VARCHAR(100),
    event_count INTEGER,
    unique_users INTEGER,
    conversion_rate DECIMAL(5,2),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(dimension_type, dimension_value)
);

-- Create indexes for better performance
CREATE INDEX idx_clickstream_user_id ON clickstream_events(user_id);
CREATE INDEX idx_clickstream_session_id ON clickstream_events(session_id);
CREATE INDEX idx_clickstream_timestamp ON clickstream_events(timestamp);
CREATE INDEX idx_realtime_timestamp ON realtime_metrics(metric_timestamp);
CREATE INDEX idx_page_metrics_url ON page_metrics(page_url);

-- Verify tables were created
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;