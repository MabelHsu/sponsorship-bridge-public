-- ============================================================
-- Sponsorship Bridge — SQLite Schema
-- ============================================================
-- Run: python backend/db_tools.py
-- This creates the database and inserts mock brand data.
-- ============================================================

-- Brand campaign requirements
CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    industry TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    budget_range TEXT NOT NULL,
    campaign_brief TEXT NOT NULL,
    description TEXT
);

-- Match results (stored by the agent after finding matches)
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    creator_name TEXT,
    fit_score INTEGER,
    match_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Mock brand campaign data — each row carries a brand-voice `description`
-- used as the headline copy on a creator-mode brand match card.
INSERT INTO brands (name, industry, target_audience, budget_range, campaign_brief, description) VALUES
    ('EcoGlow Skincare', 'Beauty',
     '{"gender": "female", "age": "18-35", "interests": ["eco-friendly", "skincare", "vegan"]}',
     '$5k-$10k',
     'Looking for beauty creators who can authentically review our new vegan serum. Target audience is eco-conscious women aged 18-35.',
     'EcoGlow is launching a clean vegan serum line for eco-conscious women 18-35. We are seeking creators who fold the product into authentic skincare routines — long-form integrations, ingredient deep-dives, or before-and-after diaries — rather than unboxing-style reviews.'),

    ('TechFlow Gadgets', 'Technology',
     '{"gender": "all", "age": "25-45", "interests": ["gadgets", "productivity", "software"]}',
     '$10k-$20k',
     'Need tech creators to produce a dedicated unboxing video for our new ergonomic mechanical keyboard. Targeting productivity-focused professionals.',
     'TechFlow ships an ergonomic mechanical keyboard built for long coding and writing sessions. We commission dedicated reviews from desk-setup, productivity, and developer-tooling creators with engaged 25-45 audiences across US, UK, EU, and APAC.'),

    ('FitLife Supplements', 'Fitness',
     '{"gender": "all", "age": "18-30", "interests": ["gym", "workout", "health"]}',
     '$2k-$8k',
     'Looking for fitness influencers to feature our pre-workout supplement in their training videos. Focus on Southeast Asian market.',
     'FitLife is a clean-label pre-workout brand expanding across Southeast Asia. We partner with gym, HIIT, and nutrition creators to demo the product mid-training, with full transparency on ingredients and dosage. SG, MY, TH, ID priority.'),

    ('Wanderlust Stays', 'Travel',
     '{"gender": "all", "age": "20-40", "interests": ["travel", "vlog", "lifestyle"]}',
     '$8k-$15k',
     'Promoting boutique stays in Southeast Asia. Seeking high-quality travel vlog creators with strong engagement.',
     'Wanderlust Stays curates independent boutique hotels across Southeast Asia. We host travel vloggers and lifestyle creators for 3-5 night stays in exchange for a cinematic mini-series. Best fits: slow-travel storytellers, not list-format influencers.'),

    ('GreenHome Co.', 'Home & Living',
     '{"gender": "all", "age": "25-45", "interests": ["eco-living", "home decor", "sustainability"]}',
     '$3k-$12k',
     'Launching a new line of sustainable home products. Need creators who cover eco-living, minimalism, or home organization.',
     'GreenHome Co. is releasing a sustainable home line — refillable cleaning, plant-based textiles, modular storage. We collaborate with zero-waste, minimalist, and home-organization creators on practical swap episodes that show real households adopting the products.'),

    ('Northwind Coffee', 'Food & Beverage',
     '{"gender": "all", "age": "22-45", "interests": ["coffee", "food", "lifestyle"]}',
     '$4k-$10k',
     'Specialty single-origin coffee brand. Looking for coffee, food, and morning-routine creators in North America and Europe.',
     'Northwind Coffee roasts single-origin beans direct from smallholder farms. We work with morning-routine, coffee-geek, and slow-living creators on integrated drink-along videos that highlight origin stories and brewing technique.'),

    ('Lumen Studio Audio', 'Technology',
     '{"gender": "all", "age": "20-40", "interests": ["music", "podcasting", "creator gear"]}',
     '$6k-$14k',
     'Studio-grade USB-C condenser microphones for podcasters and home-studio musicians. Looking for music, podcasting, and creator-economy YouTubers.',
     'Lumen Studio designs studio-grade USB-C condenser microphones for podcasters and home-studio musicians. We sponsor in-depth gear reviews and behind-the-scenes setup tours from music, podcasting, and creator-economy YouTubers.'),

    ('PixelPath Peripherals', 'Gaming',
     '{"gender": "all", "age": "16-30", "interests": ["gaming", "esports", "PC building", "streaming"]}',
     '$5k-$15k',
     'Mechanical gaming keyboards, low-latency mice, and esports-grade peripherals. Looking for gaming, esports, and PC-build creators.',
     'PixelPath builds tournament-tested mechanical keyboards and low-latency mice for competitive players. We work with gaming, esports, and PC-build creators on real-gameplay sponsorships — no scripted unboxings, just the kit in actual matches.'),

    ('Mercato Wealth', 'Finance',
     '{"gender": "all", "age": "22-45", "interests": ["personal finance", "investing", "side hustles", "retirement"]}',
     '$8k-$20k',
     'Personal finance and investing platform. Looking for finance, investing, and side-hustle YouTubers in North America and the UK.',
     'Mercato Wealth is a commission-free investing platform with built-in retirement and tax-optimization tools. We partner with personal finance, investing, and side-hustle creators on educational integrations — explainers, account walkthroughs, and honest comparisons against competitors.'),

    ('Tailtreat Pet Co.', 'Pets',
     '{"gender": "all", "age": "25-50", "interests": ["dogs", "cats", "pet training", "rescue", "raw feeding"]}',
     '$3k-$9k',
     'Premium single-protein pet food and treats. Looking for pet, dog training, and rescue/adoption YouTubers in the US and Canada.',
     'Tailtreat makes single-protein, no-filler pet food sourced from regional farms. We collaborate with pet training, rescue, and lifestyle-with-pets creators on real-feeding diaries — no staged tasting shots, just multi-week trials with the creator''s own animals.')
ON CONFLICT (name) DO NOTHING;
