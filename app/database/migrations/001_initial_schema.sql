-- GymConnect AI — Initial Schema
-- Run order: this file is auto-executed by Docker on first start
-- or manually via: psql $DATABASE_URL < migrations/001_initial_schema.sql

-- ─── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ─── Migration Tracking ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    id          SERIAL PRIMARY KEY,
    version     VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── 1. USERS ─────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id                          BIGSERIAL PRIMARY KEY,
    uuid                        UUID UNIQUE DEFAULT gen_random_uuid(),
    email                       VARCHAR(255) UNIQUE,
    phone                       VARCHAR(20),
    full_name                   VARCHAR(255),
    password_hash               VARCHAR(255),
    role                        VARCHAR(50) NOT NULL,
    profile_photo_url           VARCHAR(500),
    date_of_birth               DATE,
    gender                      VARCHAR(20),
    bio                         TEXT,
    city                        VARCHAR(100),
    state                       VARCHAR(100),
    country                     VARCHAR(100) DEFAULT 'India',
    zipcode                     VARCHAR(10),
    profession                  VARCHAR(100),
    experience_years            INTEGER,
    specializations             JSONB,
    certifications              JSONB,
    is_active                   BOOLEAN DEFAULT TRUE,
    email_verified              BOOLEAN DEFAULT FALSE,
    phone_verified              BOOLEAN DEFAULT FALSE,
    profile_completed           BOOLEAN DEFAULT FALSE,
    kyc_verified                BOOLEAN DEFAULT FALSE,
    failed_login_attempts       INTEGER DEFAULT 0,
    is_locked                   BOOLEAN DEFAULT FALSE,
    locked_until                TIMESTAMP,
    last_login_at               TIMESTAMP,
    password_reset_token        VARCHAR(255),
    password_reset_expires_at   TIMESTAMP,
    email_verification_token    VARCHAR(255),
    email_verification_expires_at TIMESTAMP,
    privacy_settings            JSONB DEFAULT '{}',
    notification_preferences    JSONB DEFAULT '{"email": true, "sms": false, "whatsapp": true}',
    timezone                    VARCHAR(50) DEFAULT 'Asia/Kolkata',
    language_preference         VARCHAR(10) DEFAULT 'en',
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_role CHECK (role IN ('SUPER_ADMIN','ADMIN','GYM_OWNER','GYM_MANAGER','TRAINER','LEAD','MEMBER')),
    CONSTRAINT email_or_phone_required CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

-- ─── 2. TRAINERS ──────────────────────────────────────────────────────────────
CREATE TABLE trainers (
    id                              BIGSERIAL PRIMARY KEY,
    user_id                         BIGINT REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    trainer_code                    VARCHAR(50) UNIQUE,
    display_name                    VARCHAR(255) NOT NULL,
    slug                            VARCHAR(255) UNIQUE NOT NULL,
    specializations                 JSONB NOT NULL DEFAULT '{}',
    certifications                  JSONB,
    education_background            TEXT,
    languages_spoken                TEXT[],
    service_types                   JSONB,
    training_locations              JSONB,
    session_duration_options        INTEGER[],
    base_hourly_rate                DECIMAL(8,2),
    rate_structure                  JSONB,
    availability_schedule           JSONB,
    max_clients_per_day             INTEGER DEFAULT 8,
    primary_location                JSONB,
    service_radius_km               INTEGER DEFAULT 10,
    profile_video_url               VARCHAR(500),
    portfolio_images                JSONB,
    client_testimonials             JSONB,
    is_active                       BOOLEAN DEFAULT TRUE,
    is_verified                     BOOLEAN DEFAULT FALSE,
    verification_status             VARCHAR(50) DEFAULT 'PENDING',
    average_rating                  DECIMAL(3,2) DEFAULT 0.0,
    total_reviews                   INTEGER DEFAULT 0,
    total_sessions_completed        INTEGER DEFAULT 0,
    response_time_hours             DECIMAL(5,2) DEFAULT 24.0,
    accepts_new_clients             BOOLEAN DEFAULT TRUE,
    minimum_booking_notice_hours    INTEGER DEFAULT 24,
    cancellation_policy             TEXT,
    subscription_tier               VARCHAR(50) DEFAULT 'FREE',
    created_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_trainer_rating CHECK (average_rating >= 0 AND average_rating <= 5)
);

-- ─── 3. GYMS ──────────────────────────────────────────────────────────────────
CREATE TABLE gyms (
    id                          BIGSERIAL PRIMARY KEY,
    gym_name                    VARCHAR(255) NOT NULL,
    slug                        VARCHAR(255) UNIQUE NOT NULL,
    owner_user_id               BIGINT REFERENCES users(id),
    owner_name                  VARCHAR(255) NOT NULL,
    business_email              VARCHAR(255) UNIQUE NOT NULL,
    phone_number                VARCHAR(20) NOT NULL,
    whatsapp_number             VARCHAR(20),
    website                     VARCHAR(500),
    facebook_url                VARCHAR(500),
    instagram_url               VARCHAR(500),
    youtube_url                 VARCHAR(500),
    full_address                TEXT NOT NULL,
    city                        VARCHAR(100) NOT NULL,
    state                       VARCHAR(100) NOT NULL,
    country                     VARCHAR(100) DEFAULT 'India',
    zipcode                     VARCHAR(10) NOT NULL,
    latitude                    DECIMAL(10,8),
    longitude                   DECIMAL(11,8),
    google_maps_link            TEXT,
    parking_available           BOOLEAN DEFAULT FALSE,
    landmark                    VARCHAR(255),
    gym_type                    VARCHAR(100),
    establishment_year          INTEGER,
    total_area_sqft             INTEGER,
    max_capacity                INTEGER,
    logo_url                    VARCHAR(500),
    banner_images               JSONB,
    video_tour_url              VARCHAR(500),
    gallery_images              JSONB,
    meta_title                  VARCHAR(255),
    meta_description            TEXT,
    meta_keywords               TEXT,
    page_views_count            BIGINT DEFAULT 0,
    amenities                   JSONB,
    safety_measures             JSONB,
    accessibility_features      JSONB,
    subscription_tier           VARCHAR(50) DEFAULT 'FREE',
    is_verified                 BOOLEAN DEFAULT FALSE,
    is_active                   BOOLEAN DEFAULT TRUE,
    featured_listing            BOOLEAN DEFAULT FALSE,
    approval_status             VARCHAR(50) DEFAULT 'PENDING',
    average_rating              DECIMAL(3,2) DEFAULT 0.0,
    total_reviews               INTEGER DEFAULT 0,
    total_members               INTEGER DEFAULT 0,
    gst_number                  VARCHAR(50),
    business_license            VARCHAR(100),
    allows_external_trainers    BOOLEAN DEFAULT TRUE,
    trainer_commission_percentage DECIMAL(5,2) DEFAULT 0,
    rejection_reason            TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_gym_coordinates CHECK (
        (latitude IS NULL AND longitude IS NULL) OR
        (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
    ),
    CONSTRAINT valid_gym_rating CHECK (average_rating >= 0 AND average_rating <= 5)
);

-- ─── 4. GYM ADMINS ────────────────────────────────────────────────────────────
CREATE TABLE gym_admins (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(id) ON DELETE CASCADE,
    gym_id          BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    role            VARCHAR(50) DEFAULT 'OWNER',
    permissions     JSONB NOT NULL DEFAULT '{}',
    access_level    INTEGER DEFAULT 1,
    is_active       BOOLEAN DEFAULT TRUE,
    invited_by      BIGINT REFERENCES users(id),
    joining_date    DATE DEFAULT CURRENT_DATE,
    employment_type VARCHAR(50),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, gym_id)
);

-- ─── 5. TRAINER-GYM ASSOCIATIONS ─────────────────────────────────────────────
CREATE TABLE trainer_gym_associations (
    id                  BIGSERIAL PRIMARY KEY,
    trainer_id          BIGINT REFERENCES trainers(id) ON DELETE CASCADE,
    gym_id              BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    association_type    VARCHAR(50) NOT NULL,
    status              VARCHAR(50) DEFAULT 'ACTIVE',
    start_date          DATE DEFAULT CURRENT_DATE,
    end_date            DATE,
    compensation_type   VARCHAR(50),
    rate_amount         DECIMAL(10,2),
    commission_percentage DECIMAL(5,2),
    gym_schedule        JSONB,
    can_add_members     BOOLEAN DEFAULT FALSE,
    sessions_at_gym     INTEGER DEFAULT 0,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trainer_id, gym_id),
    CONSTRAINT valid_association_type CHECK (association_type IN ('EMPLOYEE','FREELANCE','PARTNER','VISITING','CONTRACTOR'))
);

-- ─── 6. GYM OPERATING HOURS ───────────────────────────────────────────────────
CREATE TABLE gym_operating_hours (
    id                  BIGSERIAL PRIMARY KEY,
    gym_id              BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    day_of_week         INTEGER NOT NULL,
    is_open             BOOLEAN DEFAULT TRUE,
    opening_time        TIME,
    closing_time        TIME,
    break_start_time    TIME,
    break_end_time      TIME,
    special_hours_note  VARCHAR(255),
    is_24_hours         BOOLEAN DEFAULT FALSE,
    effective_from      DATE DEFAULT CURRENT_DATE,
    effective_until     DATE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_day CHECK (day_of_week BETWEEN 0 AND 6),
    UNIQUE(gym_id, day_of_week, effective_from)
);

-- ─── 7. GYM FACILITIES ────────────────────────────────────────────────────────
CREATE TABLE gym_facilities (
    id              BIGSERIAL PRIMARY KEY,
    gym_id          BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    category        VARCHAR(100) NOT NULL,
    subcategory     VARCHAR(100),
    facility_name   VARCHAR(255) NOT NULL,
    description     TEXT,
    quantity        INTEGER DEFAULT 1,
    brand_model     VARCHAR(255),
    is_available    BOOLEAN DEFAULT TRUE,
    is_premium      BOOLEAN DEFAULT FALSE,
    additional_cost DECIMAL(8,2) DEFAULT 0,
    tags            JSONB,
    image_url       VARCHAR(500),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── 8. GYM PLANS ─────────────────────────────────────────────────────────────
CREATE TABLE gym_plans (
    id                          BIGSERIAL PRIMARY KEY,
    gym_id                      BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    plan_name                   VARCHAR(255) NOT NULL,
    plan_code                   VARCHAR(50),
    duration_months             INTEGER NOT NULL,
    duration_days               INTEGER,
    original_price              DECIMAL(10,2) NOT NULL,
    discounted_price            DECIMAL(10,2),
    registration_fee            DECIMAL(10,2) DEFAULT 0,
    security_deposit            DECIMAL(10,2) DEFAULT 0,
    features                    JSONB NOT NULL DEFAULT '{}',
    restrictions                JSONB,
    included_services           TEXT[],
    trainer_sessions_included   INTEGER DEFAULT 0,
    trial_available             BOOLEAN DEFAULT FALSE,
    trial_duration_days         INTEGER DEFAULT 0,
    trial_cost                  DECIMAL(8,2) DEFAULT 0,
    discount_percentage         DECIMAL(5,2) DEFAULT 0,
    offer_valid_until           DATE,
    is_active                   BOOLEAN DEFAULT TRUE,
    is_popular                  BOOLEAN DEFAULT FALSE,
    max_enrollments             INTEGER,
    current_enrollments         INTEGER DEFAULT 0,
    plan_category               VARCHAR(100),
    target_audience             VARCHAR(100),
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_plan_price CHECK (
        original_price > 0 AND (discounted_price IS NULL OR discounted_price <= original_price)
    )
);

-- ─── 9. GYM CLASSES ───────────────────────────────────────────────────────────
CREATE TABLE gym_classes (
    id                          BIGSERIAL PRIMARY KEY,
    gym_id                      BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    trainer_id                  BIGINT REFERENCES trainers(id),
    class_name                  VARCHAR(255) NOT NULL,
    class_type                  VARCHAR(100) NOT NULL,
    description                 TEXT,
    difficulty_level            VARCHAR(50),
    day_of_week                 INTEGER NOT NULL,
    start_time                  TIME NOT NULL,
    end_time                    TIME NOT NULL,
    duration_minutes            INTEGER NOT NULL,
    max_participants            INTEGER NOT NULL,
    current_bookings            INTEGER DEFAULT 0,
    advance_booking_required    BOOLEAN DEFAULT FALSE,
    cost_per_session            DECIMAL(8,2) DEFAULT 0,
    included_in_membership      BOOLEAN DEFAULT TRUE,
    is_active                   BOOLEAN DEFAULT TRUE,
    is_recurring                BOOLEAN DEFAULT TRUE,
    cancelled_dates             DATE[],
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_class_day CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT valid_class_times CHECK (end_time > start_time)
);

-- ─── 10. GYM MEMBERS ──────────────────────────────────────────────────────────
CREATE TABLE gym_members (
    id                          BIGSERIAL PRIMARY KEY,
    gym_id                      BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    user_id                     BIGINT REFERENCES users(id),
    member_code                 VARCHAR(50) UNIQUE,
    member_name                 VARCHAR(255) NOT NULL,
    phone                       VARCHAR(20) NOT NULL,
    email                       VARCHAR(255),
    date_of_birth               DATE,
    gender                      VARCHAR(20),
    occupation                  VARCHAR(255),
    address                     JSONB,
    emergency_contact_name      VARCHAR(255),
    emergency_contact_phone     VARCHAR(20),
    height_cm                   INTEGER,
    weight_kg                   DECIMAL(5,2),
    medical_conditions          JSONB,
    fitness_goals               JSONB,
    dietary_restrictions        TEXT[],
    membership_status           VARCHAR(50) DEFAULT 'ACTIVE',
    joined_date                 DATE DEFAULT CURRENT_DATE,
    referral_source             VARCHAR(255),
    referred_by                 BIGINT REFERENCES gym_members(id),
    primary_trainer_id          BIGINT REFERENCES trainers(id),
    trainer_assignment_date     DATE,
    preferred_workout_time      VARCHAR(50),
    interested_classes          TEXT[],
    whatsapp_notifications      BOOLEAN DEFAULT TRUE,
    email_notifications         BOOLEAN DEFAULT TRUE,
    sms_notifications           BOOLEAN DEFAULT FALSE,
    custom_fields               JSONB DEFAULT '{}',
    notes                       TEXT,
    tags                        TEXT[],
    is_active                   BOOLEAN DEFAULT TRUE,
    last_visit_date             DATE,
    total_visits                INTEGER DEFAULT 0,
    qr_code                     VARCHAR(255) UNIQUE,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_member_status CHECK (
        membership_status IN ('ACTIVE','INACTIVE','SUSPENDED','EXPIRED','TRANSFERRED')
    )
);

-- ─── 11. MEMBERSHIP HISTORY ───────────────────────────────────────────────────
CREATE TABLE membership_history (
    id                          BIGSERIAL PRIMARY KEY,
    member_id                   BIGINT REFERENCES gym_members(id) ON DELETE CASCADE,
    plan_id                     BIGINT REFERENCES gym_plans(id),
    start_date                  DATE NOT NULL,
    end_date                    DATE NOT NULL,
    actual_end_date             DATE,
    plan_price                  DECIMAL(10,2) NOT NULL,
    discount_applied            DECIMAL(10,2) DEFAULT 0,
    additional_charges          DECIMAL(10,2) DEFAULT 0,
    total_amount                DECIMAL(10,2) NOT NULL,
    payment_method              VARCHAR(50),
    payment_status              VARCHAR(50) DEFAULT 'PAID',
    payment_date                DATE,
    transaction_reference       VARCHAR(255),
    status                      VARCHAR(50) DEFAULT 'ACTIVE',
    cancellation_reason         TEXT,
    cancelled_by                BIGINT REFERENCES users(id),
    freeze_start_date           DATE,
    freeze_end_date             DATE,
    freeze_days_used            INTEGER DEFAULT 0,
    trainer_sessions_allocated  INTEGER DEFAULT 0,
    trainer_sessions_used       INTEGER DEFAULT 0,
    created_by                  BIGINT REFERENCES users(id),
    notes                       TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_membership_dates CHECK (end_date > start_date)
);

-- ─── 12. GYM VISITS ───────────────────────────────────────────────────────────
CREATE TABLE gym_visits (
    id              BIGSERIAL PRIMARY KEY,
    member_id       BIGINT REFERENCES gym_members(id) ON DELETE CASCADE,
    gym_id          BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    visit_date      DATE DEFAULT CURRENT_DATE,
    check_in_time   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    check_out_time  TIMESTAMP,
    duration_minutes INTEGER,
    visit_type      VARCHAR(50) DEFAULT 'REGULAR',
    purpose         VARCHAR(100),
    entry_method    VARCHAR(50),
    is_valid_visit  BOOLEAN DEFAULT TRUE,
    facilities_used JSONB,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── 13. TRAINER SERVICES ─────────────────────────────────────────────────────
CREATE TABLE trainer_services (
    id                  BIGSERIAL PRIMARY KEY,
    trainer_id          BIGINT REFERENCES trainers(id) ON DELETE CASCADE,
    service_name        VARCHAR(255) NOT NULL,
    service_type        VARCHAR(100) NOT NULL,
    category            VARCHAR(100),
    description         TEXT,
    duration_minutes    INTEGER NOT NULL,
    max_participants    INTEGER DEFAULT 1,
    difficulty_level    VARCHAR(50),
    price_per_session   DECIMAL(8,2) NOT NULL,
    package_prices      JSONB,
    currency            VARCHAR(10) DEFAULT 'INR',
    equipment_required  JSONB,
    space_requirements  TEXT,
    available_locations JSONB,
    travel_charge       DECIMAL(8,2) DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE,
    is_featured         BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── 14. TRAINER AVAILABILITY ─────────────────────────────────────────────────
CREATE TABLE trainer_availability (
    id                      BIGSERIAL PRIMARY KEY,
    trainer_id              BIGINT REFERENCES trainers(id) ON DELETE CASCADE,
    gym_id                  BIGINT REFERENCES gyms(id),
    day_of_week             INTEGER NOT NULL,
    start_time              TIME NOT NULL,
    end_time                TIME NOT NULL,
    schedule_type           VARCHAR(50) DEFAULT 'REGULAR',
    effective_from          DATE DEFAULT CURRENT_DATE,
    effective_until         DATE,
    is_bookable             BOOLEAN DEFAULT TRUE,
    max_bookings_per_slot   INTEGER DEFAULT 1,
    location_type           VARCHAR(50),
    special_rate            DECIMAL(8,2),
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_avail_day CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT valid_avail_times CHECK (end_time > start_time)
);

-- ─── 15. TRAINING SESSIONS ────────────────────────────────────────────────────
CREATE TABLE training_sessions (
    id                  BIGSERIAL PRIMARY KEY,
    trainer_id          BIGINT REFERENCES trainers(id) ON DELETE RESTRICT,
    client_user_id      BIGINT REFERENCES users(id),
    gym_id              BIGINT REFERENCES gyms(id),
    service_id          BIGINT REFERENCES trainer_services(id),
    client_name         VARCHAR(255),
    client_phone        VARCHAR(20),
    client_email        VARCHAR(255),
    session_date        DATE NOT NULL,
    start_time          TIME NOT NULL,
    end_time            TIME NOT NULL,
    duration_minutes    INTEGER NOT NULL,
    booking_id          VARCHAR(100) UNIQUE,
    session_type        VARCHAR(100),
    location_type       VARCHAR(50),
    location_details    JSONB,
    quoted_price        DECIMAL(8,2) NOT NULL,
    actual_price        DECIMAL(8,2),
    discount_applied    DECIMAL(8,2) DEFAULT 0,
    payment_status      VARCHAR(50) DEFAULT 'PENDING',
    payment_method      VARCHAR(50),
    status              VARCHAR(50) DEFAULT 'CONFIRMED',
    cancellation_reason TEXT,
    cancelled_by        VARCHAR(50),
    attendance_status   VARCHAR(50),
    session_rating      INTEGER,
    trainer_rating      INTEGER,
    session_notes       TEXT,
    trainer_feedback    TEXT,
    client_feedback     TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_session_status CHECK (status IN ('CONFIRMED','CANCELLED','COMPLETED','NO_SHOW','RESCHEDULED','IN_PROGRESS')),
    CONSTRAINT valid_session_ratings CHECK (
        (session_rating IS NULL OR session_rating BETWEEN 1 AND 5) AND
        (trainer_rating IS NULL OR trainer_rating BETWEEN 1 AND 5)
    )
);

-- ─── 16. CLASS BOOKINGS ───────────────────────────────────────────────────────
CREATE TABLE class_bookings (
    id                  BIGSERIAL PRIMARY KEY,
    class_id            BIGINT REFERENCES gym_classes(id) ON DELETE CASCADE,
    member_id           BIGINT REFERENCES gym_members(id) ON DELETE CASCADE,
    booking_date        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    class_date          DATE NOT NULL,
    booking_status      VARCHAR(50) DEFAULT 'CONFIRMED',
    amount_paid         DECIMAL(8,2) DEFAULT 0,
    payment_method      VARCHAR(50),
    payment_status      VARCHAR(50) DEFAULT 'NOT_REQUIRED',
    attendance_status   VARCHAR(50),
    check_in_time       TIMESTAMP,
    feedback_rating     INTEGER,
    feedback_comments   TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(class_id, member_id, class_date),
    CONSTRAINT valid_booking_status CHECK (booking_status IN ('CONFIRMED','CANCELLED','WAITLIST','NO_SHOW','COMPLETED'))
);

-- ─── 17. CHAT LEADS ───────────────────────────────────────────────────────────
CREATE TABLE chat_leads (
    id                  BIGSERIAL PRIMARY KEY,
    gym_id              BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    trainer_id          BIGINT REFERENCES trainers(id),
    lead_name           VARCHAR(255),
    phone               VARCHAR(20),
    email               VARCHAR(255),
    age_range           VARCHAR(20),
    gender              VARCHAR(20),
    location            VARCHAR(255),
    initial_query       TEXT,
    chat_transcript     JSONB,
    lead_source         VARCHAR(100) DEFAULT 'CHATBOT',
    source_details      JSONB,
    status              VARCHAR(50) DEFAULT 'NEW',
    lead_quality        VARCHAR(20) DEFAULT 'MEDIUM',
    lead_score          INTEGER DEFAULT 0,
    interested_services JSONB,
    budget_range        VARCHAR(50),
    preferred_timing    VARCHAR(100),
    fitness_goals       JSONB,
    assigned_to         BIGINT REFERENCES users(id),
    priority            VARCHAR(20) DEFAULT 'MEDIUM',
    follow_up_date      DATE,
    follow_up_notes     TEXT,
    last_contact_date   DATE,
    contact_attempts    INTEGER DEFAULT 0,
    converted_to_member BOOLEAN DEFAULT FALSE,
    member_id           BIGINT REFERENCES gym_members(id),
    conversion_date     DATE,
    conversion_value    DECIMAL(10,2),
    utm_source          VARCHAR(255),
    utm_medium          VARCHAR(255),
    utm_campaign        VARCHAR(255),
    prefers_whatsapp    BOOLEAN DEFAULT TRUE,
    prefers_email       BOOLEAN DEFAULT TRUE,
    prefers_calls       BOOLEAN DEFAULT FALSE,
    first_contact_date  DATE DEFAULT CURRENT_DATE,
    days_in_pipeline    INTEGER DEFAULT 0,
    custom_fields       JSONB DEFAULT '{}',
    tags                TEXT[],
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_lead_status CHECK (status IN ('NEW','CONTACTED','INTERESTED','DEMO_SCHEDULED','CONVERTED','LOST','NURTURING')),
    CONSTRAINT valid_lead_score CHECK (lead_score >= 0 AND lead_score <= 100)
);

-- ─── 18. LEAD INTERACTIONS ────────────────────────────────────────────────────
CREATE TABLE lead_interactions (
    id                  BIGSERIAL PRIMARY KEY,
    lead_id             BIGINT REFERENCES chat_leads(id) ON DELETE CASCADE,
    user_id             BIGINT REFERENCES users(id),
    interaction_type    VARCHAR(50) NOT NULL,
    interaction_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_minutes    INTEGER,
    subject             VARCHAR(255),
    content             TEXT,
    outcome             VARCHAR(100),
    next_action         VARCHAR(255),
    next_action_date    DATE,
    trainer_introduced  BIGINT REFERENCES trainers(id),
    interaction_data    JSONB,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── 19. GYM CHATBOT CONFIG ───────────────────────────────────────────────────
CREATE TABLE gym_chatbot_config (
    id                              BIGSERIAL PRIMARY KEY,
    gym_id                          BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    bot_name                        VARCHAR(100) DEFAULT 'GymBot',
    greeting_message                TEXT DEFAULT 'Hi! 👋 Welcome! How can I help you today?',
    response_tone                   VARCHAR(50) DEFAULT 'FRIENDLY',
    bot_avatar_url                  VARCHAR(500),
    collect_leads                   BOOLEAN DEFAULT TRUE,
    escalate_to_human               BOOLEAN DEFAULT TRUE,
    suggest_trainers                BOOLEAN DEFAULT FALSE,
    custom_faqs                     JSONB,
    knowledge_base                  JSONB,
    response_templates              JSONB,
    supported_languages             TEXT[] DEFAULT ARRAY['en'],
    can_book_demos                  BOOLEAN DEFAULT TRUE,
    can_check_availability          BOOLEAN DEFAULT TRUE,
    can_share_pricing               BOOLEAN DEFAULT TRUE,
    primary_cta                     TEXT DEFAULT 'Want to visit us? Share your name and number below!',
    secondary_cta                   TEXT DEFAULT 'Would you like to schedule a free demo?',
    active_hours                    JSONB,
    conversation_timeout_minutes    INTEGER DEFAULT 30,
    is_active                       BOOLEAN DEFAULT TRUE,
    created_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gym_id)
);

-- ─── 20. TRAINER CHATBOT CONFIG ───────────────────────────────────────────────
CREATE TABLE trainer_chatbot_config (
    id                      BIGSERIAL PRIMARY KEY,
    trainer_id              BIGINT REFERENCES trainers(id) ON DELETE CASCADE,
    bot_name                VARCHAR(100) DEFAULT 'TrainerBot',
    greeting_message        TEXT DEFAULT 'Hi! I am your fitness assistant.',
    response_tone           VARCHAR(50) DEFAULT 'FRIENDLY',
    can_book_sessions       BOOLEAN DEFAULT TRUE,
    can_show_availability   BOOLEAN DEFAULT TRUE,
    can_share_rates         BOOLEAN DEFAULT TRUE,
    booking_flow_enabled    BOOLEAN DEFAULT FALSE,
    trainer_bio_sharing     BOOLEAN DEFAULT TRUE,
    testimonial_sharing     BOOLEAN DEFAULT TRUE,
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trainer_id)
);

-- ─── 21. COMMUNICATION LOGS ───────────────────────────────────────────────────
CREATE TABLE communication_logs (
    id                  BIGSERIAL PRIMARY KEY,
    gym_id              BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    trainer_id          BIGINT REFERENCES trainers(id),
    recipient_type      VARCHAR(50) NOT NULL,
    recipient_id        BIGINT,
    recipient_phone     VARCHAR(20),
    recipient_email     VARCHAR(255),
    recipient_name      VARCHAR(255),
    communication_type  VARCHAR(50) NOT NULL,
    subject             VARCHAR(255),
    message_content     TEXT NOT NULL,
    template_used       VARCHAR(255),
    status              VARCHAR(50) DEFAULT 'SENT',
    external_message_id VARCHAR(255),
    failure_reason      TEXT,
    purpose             VARCHAR(100),
    sent_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered_at        TIMESTAMP,
    read_at             TIMESTAMP,
    cost_per_message    DECIMAL(6,4) DEFAULT 0,
    CONSTRAINT valid_comm_type CHECK (communication_type IN ('EMAIL','WHATSAPP','SMS','PUSH_NOTIFICATION')),
    CONSTRAINT valid_recipient_type CHECK (recipient_type IN ('MEMBER','LEAD','TRAINER','GYM_ADMIN'))
);

-- ─── 22. COMMUNICATION TEMPLATES ──────────────────────────────────────────────
CREATE TABLE communication_templates (
    id                  BIGSERIAL PRIMARY KEY,
    gym_id              BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    trainer_id          BIGINT REFERENCES trainers(id),
    template_name       VARCHAR(255) NOT NULL,
    template_type       VARCHAR(50) NOT NULL,
    category            VARCHAR(100),
    subject             VARCHAR(255),
    content             TEXT NOT NULL,
    variables           JSONB,
    is_active           BOOLEAN DEFAULT TRUE,
    is_system_template  BOOLEAN DEFAULT FALSE,
    usage_count         INTEGER DEFAULT 0,
    last_used_at        TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── 23. SUBSCRIPTION PLANS ───────────────────────────────────────────────────
CREATE TABLE subscription_plans (
    id                          BIGSERIAL PRIMARY KEY,
    plan_name                   VARCHAR(100) NOT NULL,
    plan_code                   VARCHAR(50) UNIQUE NOT NULL,
    plan_type                   VARCHAR(50) NOT NULL,
    target_user_type            VARCHAR(50) NOT NULL,
    base_price                  DECIMAL(10,2) NOT NULL,
    setup_fee                   DECIMAL(10,2) DEFAULT 0,
    currency                    VARCHAR(10) DEFAULT 'INR',
    billing_cycle_months        INTEGER,
    trial_period_days           INTEGER DEFAULT 0,
    max_gyms                    INTEGER DEFAULT 1,
    max_leads_per_month         INTEGER DEFAULT -1,
    max_members                 INTEGER DEFAULT -1,
    max_trainers                INTEGER DEFAULT -1,
    max_chatbot_interactions    INTEGER DEFAULT -1,
    max_whatsapp_messages       INTEGER DEFAULT -1,
    max_email_messages          INTEGER DEFAULT -1,
    max_storage_gb              DECIMAL(8,2) DEFAULT -1,
    max_trainer_profiles        INTEGER DEFAULT 1,
    max_bookings_per_month      INTEGER DEFAULT -1,
    features                    JSONB NOT NULL DEFAULT '{}',
    api_access                  BOOLEAN DEFAULT FALSE,
    white_label_options         BOOLEAN DEFAULT FALSE,
    priority_support            BOOLEAN DEFAULT FALSE,
    advanced_analytics          BOOLEAN DEFAULT FALSE,
    is_active                   BOOLEAN DEFAULT TRUE,
    is_featured                 BOOLEAN DEFAULT FALSE,
    sort_order                  INTEGER DEFAULT 0,
    description                 TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_sub_plan_type CHECK (plan_type IN ('MONTHLY','QUARTERLY','YEARLY','LIFETIME','PAY_PER_USE')),
    CONSTRAINT valid_target_type CHECK (target_user_type IN ('GYM','TRAINER','BOTH'))
);

-- ─── 24. USER SUBSCRIPTIONS ───────────────────────────────────────────────────
CREATE TABLE user_subscriptions (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT REFERENCES users(id) ON DELETE CASCADE,
    gym_id                  BIGINT REFERENCES gyms(id),
    trainer_id              BIGINT REFERENCES trainers(id),
    plan_id                 BIGINT REFERENCES subscription_plans(id),
    subscription_code       VARCHAR(100) UNIQUE,
    status                  VARCHAR(50) DEFAULT 'ACTIVE',
    current_period_start    DATE NOT NULL,
    current_period_end      DATE NOT NULL,
    trial_start             DATE,
    trial_end               DATE,
    amount_per_cycle        DECIMAL(10,2) NOT NULL,
    discount_applied        DECIMAL(10,2) DEFAULT 0,
    tax_amount              DECIMAL(10,2) DEFAULT 0,
    total_amount            DECIMAL(10,2) NOT NULL,
    leads_used              INTEGER DEFAULT 0,
    members_count           INTEGER DEFAULT 0,
    trainers_count          INTEGER DEFAULT 0,
    bookings_made           INTEGER DEFAULT 0,
    chatbot_interactions    INTEGER DEFAULT 0,
    whatsapp_messages_sent  INTEGER DEFAULT 0,
    email_messages_sent     INTEGER DEFAULT 0,
    storage_used_gb         DECIMAL(8,2) DEFAULT 0,
    auto_renewal            BOOLEAN DEFAULT TRUE,
    next_billing_date       DATE,
    last_billing_date       DATE,
    failed_payment_attempts INTEGER DEFAULT 0,
    cancellation_reason     TEXT,
    cancellation_date       DATE,
    cancelled_by            BIGINT REFERENCES users(id),
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_sub_status CHECK (status IN ('ACTIVE','EXPIRED','CANCELLED','SUSPENDED','TRIAL','PAST_DUE'))
);

-- ─── 25. PAYMENT TRANSACTIONS ─────────────────────────────────────────────────
CREATE TABLE payment_transactions (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT REFERENCES users(id) ON DELETE CASCADE,
    subscription_id         BIGINT REFERENCES user_subscriptions(id),
    training_session_id     BIGINT REFERENCES training_sessions(id),
    transaction_id          VARCHAR(255) UNIQUE NOT NULL,
    external_transaction_id VARCHAR(255),
    invoice_number          VARCHAR(100) UNIQUE,
    transaction_type        VARCHAR(50) NOT NULL,
    amount                  DECIMAL(10,2) NOT NULL,
    currency                VARCHAR(10) DEFAULT 'INR',
    base_amount             DECIMAL(10,2) NOT NULL,
    discount_amount         DECIMAL(10,2) DEFAULT 0,
    tax_amount              DECIMAL(10,2) DEFAULT 0,
    processing_fee          DECIMAL(10,2) DEFAULT 0,
    platform_commission     DECIMAL(10,2) DEFAULT 0,
    payment_method          VARCHAR(50),
    payment_gateway         VARCHAR(50),
    gateway_transaction_id  VARCHAR(255),
    gateway_response        JSONB,
    status                  VARCHAR(50) DEFAULT 'PENDING',
    payment_date            TIMESTAMP,
    due_date                DATE,
    billing_name            VARCHAR(255),
    billing_email           VARCHAR(255),
    billing_address         JSONB,
    reconciled              BOOLEAN DEFAULT FALSE,
    reconciliation_date     DATE,
    description             TEXT,
    failure_reason          TEXT,
    retry_count             INTEGER DEFAULT 0,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_txn_type CHECK (transaction_type IN ('SUBSCRIPTION','TRAINER_SESSION','SETUP_FEE','REFUND','ADJUSTMENT','COMMISSION')),
    CONSTRAINT valid_payment_status CHECK (status IN ('PENDING','SUCCESS','FAILED','REFUNDED','CANCELLED','PROCESSING'))
);

-- ─── 26. ANALYTICS EVENTS ─────────────────────────────────────────────────────
CREATE TABLE analytics_events (
    id              BIGSERIAL PRIMARY KEY,
    gym_id          BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    trainer_id      BIGINT REFERENCES trainers(id),
    user_id         BIGINT REFERENCES users(id),
    event_category  VARCHAR(100) NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    event_name      VARCHAR(255) NOT NULL,
    event_data      JSONB DEFAULT '{}',
    event_value     DECIMAL(10,2),
    session_id      UUID,
    user_agent      TEXT,
    ip_address      INET,
    referrer        VARCHAR(500),
    device_type     VARCHAR(50),
    browser         VARCHAR(100),
    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_created    DATE DEFAULT CURRENT_DATE,
    CONSTRAINT valid_event_category CHECK (event_category IN ('PAGE_VIEW','USER_ACTION','SYSTEM','CONVERSION','ENGAGEMENT'))
);

-- ─── 27. DAILY ANALYTICS SUMMARY ─────────────────────────────────────────────
CREATE TABLE daily_analytics_summary (
    id                          BIGSERIAL PRIMARY KEY,
    gym_id                      BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    trainer_id                  BIGINT REFERENCES trainers(id),
    analytics_date              DATE NOT NULL,
    total_page_views            INTEGER DEFAULT 0,
    unique_visitors             INTEGER DEFAULT 0,
    bounce_rate                 DECIMAL(5,2) DEFAULT 0,
    chatbot_conversations       INTEGER DEFAULT 0,
    chatbot_leads_generated     INTEGER DEFAULT 0,
    chatbot_completion_rate     DECIMAL(5,2) DEFAULT 0,
    total_leads                 INTEGER DEFAULT 0,
    qualified_leads             INTEGER DEFAULT 0,
    converted_leads             INTEGER DEFAULT 0,
    lead_conversion_rate        DECIMAL(5,2) DEFAULT 0,
    new_members                 INTEGER DEFAULT 0,
    new_bookings                INTEGER DEFAULT 0,
    active_members              INTEGER DEFAULT 0,
    member_visits               INTEGER DEFAULT 0,
    daily_revenue               DECIMAL(12,2) DEFAULT 0,
    membership_revenue          DECIMAL(12,2) DEFAULT 0,
    trainer_session_revenue     DECIMAL(12,2) DEFAULT 0,
    emails_sent                 INTEGER DEFAULT 0,
    whatsapp_sent               INTEGER DEFAULT 0,
    sms_sent                    INTEGER DEFAULT 0,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(gym_id, trainer_id, analytics_date)
);

-- ─── 28. REVIEWS ──────────────────────────────────────────────────────────────
CREATE TABLE reviews (
    id                  BIGSERIAL PRIMARY KEY,
    gym_id              BIGINT REFERENCES gyms(id) ON DELETE CASCADE,
    trainer_id          BIGINT REFERENCES trainers(id) ON DELETE CASCADE,
    reviewer_user_id    BIGINT REFERENCES users(id),
    session_id          BIGINT REFERENCES training_sessions(id),
    membership_id       BIGINT REFERENCES membership_history(id),
    rating              INTEGER NOT NULL,
    review_title        VARCHAR(255),
    review_content      TEXT,
    review_type         VARCHAR(50) DEFAULT 'GENERAL',
    reviewer_name       VARCHAR(255),
    reviewer_email      VARCHAR(255),
    is_verified_purchase BOOLEAN DEFAULT FALSE,
    status              VARCHAR(50) DEFAULT 'PENDING',
    moderation_notes    TEXT,
    moderated_by        BIGINT REFERENCES users(id),
    moderated_at        TIMESTAMP,
    helpful_votes       INTEGER DEFAULT 0,
    unhelpful_votes     INTEGER DEFAULT 0,
    response_content    TEXT,
    response_date       TIMESTAMP,
    responded_by        BIGINT REFERENCES users(id),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_review_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT valid_review_status CHECK (status IN ('PENDING','APPROVED','REJECTED','HIDDEN'))
);

-- ─── 29. NOTIFICATIONS ────────────────────────────────────────────────────────
CREATE TABLE notifications (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT REFERENCES users(id) ON DELETE CASCADE,
    notification_type       VARCHAR(100) NOT NULL,
    title                   VARCHAR(255) NOT NULL,
    message                 TEXT NOT NULL,
    related_entity_type     VARCHAR(50),
    related_entity_id       BIGINT,
    send_email              BOOLEAN DEFAULT FALSE,
    send_whatsapp           BOOLEAN DEFAULT FALSE,
    send_sms                BOOLEAN DEFAULT FALSE,
    send_push               BOOLEAN DEFAULT TRUE,
    is_read                 BOOLEAN DEFAULT FALSE,
    is_delivered            BOOLEAN DEFAULT FALSE,
    scheduled_for           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at                 TIMESTAMP,
    delivered_at            TIMESTAMP,
    action_url              VARCHAR(500),
    action_button_text      VARCHAR(100),
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── 30. SYSTEM SETTINGS ──────────────────────────────────────────────────────
CREATE TABLE system_settings (
    id              BIGSERIAL PRIMARY KEY,
    setting_key     VARCHAR(255) UNIQUE NOT NULL,
    setting_value   JSONB NOT NULL,
    setting_type    VARCHAR(50) NOT NULL,
    category        VARCHAR(100),
    description     TEXT,
    is_public       BOOLEAN DEFAULT FALSE,
    updated_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_setting_type CHECK (setting_type IN ('STRING','INTEGER','BOOLEAN','JSON','ARRAY','DECIMAL'))
);

-- ─── INDEXES ──────────────────────────────────────────────────────────────────
CREATE INDEX idx_users_role_active ON users(role, is_active);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_phone ON users(phone);

CREATE INDEX idx_gyms_city_state ON gyms(city, state, is_active, approval_status);
CREATE INDEX idx_gyms_slug ON gyms(slug);
CREATE INDEX idx_gyms_owner ON gyms(owner_user_id);
CREATE INDEX idx_gyms_featured ON gyms(featured_listing DESC, average_rating DESC);
CREATE INDEX idx_gyms_search ON gyms USING gin(to_tsvector('english', gym_name || ' ' || COALESCE(meta_description, '')));

CREATE INDEX idx_members_gym_status ON gym_members(gym_id, membership_status, is_active);
CREATE INDEX idx_members_phone ON gym_members(phone);
CREATE INDEX idx_members_code ON gym_members(member_code);

CREATE INDEX idx_leads_gym_status ON chat_leads(gym_id, status);
CREATE INDEX idx_leads_score ON chat_leads(lead_score DESC);
CREATE INDEX idx_leads_follow_up ON chat_leads(follow_up_date, assigned_to);
CREATE INDEX idx_leads_phone ON chat_leads(phone);
CREATE INDEX idx_leads_created ON chat_leads(gym_id, created_at DESC);

CREATE INDEX idx_visits_gym_date ON gym_visits(gym_id, visit_date);
CREATE INDEX idx_visits_member ON gym_visits(member_id, visit_date);

CREATE INDEX idx_membership_member ON membership_history(member_id, status);
CREATE INDEX idx_membership_end_date ON membership_history(end_date, status);

CREATE INDEX idx_sessions_trainer_date ON training_sessions(trainer_id, session_date, status);
CREATE INDEX idx_sessions_client ON training_sessions(client_user_id, session_date);

CREATE INDEX idx_comms_gym ON communication_logs(gym_id, sent_at DESC);
CREATE INDEX idx_comms_type ON communication_logs(communication_type, status);

CREATE INDEX idx_analytics_gym_date ON analytics_events(gym_id, date_created, event_category);

CREATE INDEX idx_subscriptions_gym_status ON user_subscriptions(gym_id, status);
CREATE INDEX idx_subscriptions_billing ON user_subscriptions(next_billing_date, status);

CREATE INDEX idx_notifications_user ON notifications(user_id, is_read, created_at DESC);

-- ─── TRIGGERS ─────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_gyms_updated_at BEFORE UPDATE ON gyms FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_trainers_updated_at BEFORE UPDATE ON trainers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_members_updated_at BEFORE UPDATE ON gym_members FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_leads_updated_at BEFORE UPDATE ON chat_leads FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_plans_updated_at BEFORE UPDATE ON gym_plans FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_membership_updated_at BEFORE UPDATE ON membership_history FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-generate member codes
CREATE OR REPLACE FUNCTION generate_member_code()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.member_code IS NULL THEN
        NEW.member_code := 'MEM' || LPAD(NEW.gym_id::TEXT, 4, '0') || LPAD(NEW.id::TEXT, 5, '0');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_generate_member_code BEFORE INSERT ON gym_members
    FOR EACH ROW EXECUTE FUNCTION generate_member_code();

-- Auto-calculate gym visit duration
CREATE OR REPLACE FUNCTION calculate_visit_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.check_out_time IS NOT NULL AND NEW.check_in_time IS NOT NULL THEN
        NEW.duration_minutes := EXTRACT(EPOCH FROM (NEW.check_out_time - NEW.check_in_time)) / 60;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_visit_duration BEFORE INSERT OR UPDATE ON gym_visits
    FOR EACH ROW EXECUTE FUNCTION calculate_visit_duration();

-- Auto-update gym rating when review is approved
CREATE OR REPLACE FUNCTION update_rating_on_review()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'APPROVED' THEN
        IF NEW.gym_id IS NOT NULL THEN
            UPDATE gyms SET
                average_rating = (SELECT ROUND(AVG(rating)::NUMERIC, 2) FROM reviews WHERE gym_id = NEW.gym_id AND status = 'APPROVED'),
                total_reviews = (SELECT COUNT(*) FROM reviews WHERE gym_id = NEW.gym_id AND status = 'APPROVED')
            WHERE id = NEW.gym_id;
        END IF;
        IF NEW.trainer_id IS NOT NULL THEN
            UPDATE trainers SET
                average_rating = (SELECT ROUND(AVG(rating)::NUMERIC, 2) FROM reviews WHERE trainer_id = NEW.trainer_id AND status = 'APPROVED'),
                total_reviews = (SELECT COUNT(*) FROM reviews WHERE trainer_id = NEW.trainer_id AND status = 'APPROVED')
            WHERE id = NEW.trainer_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_rating AFTER INSERT OR UPDATE ON reviews
    FOR EACH ROW EXECUTE FUNCTION update_rating_on_review();

-- ─── SEED DATA ────────────────────────────────────────────────────────────────
INSERT INTO subscription_plans (plan_name, plan_code, plan_type, target_user_type, base_price, max_leads_per_month, max_members, max_whatsapp_messages, features, sort_order, description) VALUES
('Gym Starter (Free)', 'GYM_STARTER', 'MONTHLY', 'GYM', 0, 25, 100, 50,
 '{"chatbot": true, "basic_analytics": true, "email_support": true, "member_management": true}',
 1, 'Free forever with basic features'),
('Gym Pro', 'GYM_PRO', 'MONTHLY', 'GYM', 1499, 200, 1000, 500,
 '{"chatbot": true, "whatsapp_bulk": true, "email": true, "advanced_analytics": true, "priority_support": true, "member_management": true}',
 2, 'Best for growing gyms'),
('Gym Premium', 'GYM_PREMIUM', 'MONTHLY', 'GYM', 2999, -1, -1, -1,
 '{"chatbot": true, "whatsapp_bulk": true, "email": true, "advanced_analytics": true, "api_access": true, "white_label": true, "member_management": true, "priority_support": true}',
 3, 'Unlimited everything'),
('Trainer Basic (Free)', 'TRAINER_BASIC', 'MONTHLY', 'TRAINER', 0, -1, -1, 50,
 '{"profile_listing": true, "basic_booking": true}',
 1, 'Free trainer profile'),
('Trainer Pro', 'TRAINER_PRO', 'MONTHLY', 'TRAINER', 999, -1, -1, 200,
 '{"profile_listing": true, "advanced_booking": true, "analytics": true, "priority_listing": true}',
 2, 'For serious trainers');

INSERT INTO system_settings (setting_key, setting_value, setting_type, category, description, is_public) VALUES
('platform_name',               '"GymConnect AI"',  'STRING',  'GENERAL',   'Platform display name',                    true),
('default_currency',            '"INR"',             'STRING',  'PAYMENT',   'Default currency',                         true),
('max_file_upload_size_mb',     '5',                 'INTEGER', 'FILES',     'Max file upload size in MB',               false),
('enable_trainer_marketplace',  'true',              'BOOLEAN', 'FEATURES',  'Enable independent trainer marketplace',   true),
('chatbot_enabled',             'true',              'BOOLEAN', 'FEATURES',  'Enable AI chatbot globally',               false),
('email_verification_required', 'true',              'BOOLEAN', 'SECURITY',  'Require email verification on signup',     false),
('trainer_commission_default',  '15.0',              'DECIMAL', 'PAYMENT',   'Default platform commission % for trainers', false);

INSERT INTO schema_migrations (version, description) VALUES ('001', 'Initial complete schema with all tables, indexes, triggers, and seed data');
