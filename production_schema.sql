-- Extension configuration for spatial search tracking matrices
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Unified master ads schema table reference validation
CREATE TABLE IF NOT EXISTS ads_master (
    ad_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    is_trial_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 1. Job Board Domain Specific Production Table
CREATE TABLE IF NOT EXISTS job_board_ads (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id UUID REFERENCES ads_master(ad_id) ON DELETE CASCADE NOT NULL,
    company_name VARCHAR(150) NOT NULL,
    employment_type VARCHAR(50) NOT NULL, -- Full-Time, Part-Time, Contract
    salary_min NUMERIC(12, 2),
    salary_max NUMERIC(12, 2),
    currency VARCHAR(3) DEFAULT 'NPR',
    workplace_setting VARCHAR(50) NOT NULL -- Remote, Onsite, Hybrid
);

-- 2. Product Launch Domain Specific Production Table
CREATE TABLE IF NOT EXISTS product_launch_ads (
    launch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id UUID REFERENCES ads_master(ad_id) ON DELETE CASCADE NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    suggested_retail_price NUMERIC(14, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'NPR' NOT NULL,
    pre_order_available BOOLEAN DEFAULT FALSE NOT NULL,
    launch_date TIMESTAMPTZ NOT NULL
);

-- 3. Event Specialized Taxonomy Data Table
CREATE TABLE IF NOT EXISTS event_ads (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id UUID REFERENCES ads_master(ad_id) ON DELETE CASCADE NOT NULL,
    venue_name VARCHAR(255) NOT NULL,
    is_virtual BOOLEAN DEFAULT FALSE NOT NULL,
    event_start_time TIMESTAMPTZ NOT NULL,
    organizer_contact_email VARCHAR(255) NOT NULL,
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6)
);

-- 4. Game Specialized Taxonomy Data Table
CREATE TABLE IF NOT EXISTS game_ads (
    game_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id UUID REFERENCES ads_master(ad_id) ON DELETE CASCADE NOT NULL,
    game_title VARCHAR(150) NOT NULL,
    app_store_download_link TEXT NOT NULL,
    minimum_ram_required_gb NUMERIC(4, 2) DEFAULT 4.00,
    contains_in_app_purchases BOOLEAN DEFAULT FALSE NOT NULL
);

-- Performance Optimization Indexing Matrices for the Helio G91 Ultra Chipset
CREATE INDEX IF NOT EXISTS idx_jobs_salary ON job_board_ads(salary_min, salary_max);
CREATE INDEX IF NOT EXISTS idx_launches_price ON product_launch_ads(suggested_retail_price);
CREATE INDEX IF NOT EXISTS idx_events_time ON event_ads(event_start_time);
CREATE INDEX IF NOT EXISTS idx_games_title ON game_ads(game_title);
