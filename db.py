from sqlalchemy import create_engine, text
import os
import streamlit as st

DATABASE_URL = os.environ.get("DATABASE_URL")

# Create a single engine instance
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

def get_connection():
    return engine.connect()

@st.cache_resource
def init_db():
    """Initializes the database schema if it doesn't exist."""
    with engine.begin() as conn:
        # 1. Base Tables
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        );
        """))
        conn.execute(text("ALTER TABLE players ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;"))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS leaderboards (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            code TEXT UNIQUE NOT NULL
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS player_stats (
            id SERIAL PRIMARY KEY,
            player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
            leaderboard_id INTEGER REFERENCES leaderboards(id) ON DELETE CASCADE,
            season_id INTEGER,
            rating REAL NOT NULL DEFAULT 1000,
            games INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            goal_diff INTEGER NOT NULL DEFAULT 0,
            trend TEXT DEFAULT '',
            UNIQUE(player_id, leaderboard_id, season_id)
        );
        """))
        conn.execute(text("ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS season_id INTEGER;"))

        # 2. Match Tables
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS matches (
            id SERIAL PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            a1_id INTEGER REFERENCES players(id),
            a2_id INTEGER REFERENCES players(id),
            b1_id INTEGER REFERENCES players(id),
            b2_id INTEGER REFERENCES players(id),
            goals_a INTEGER NOT NULL,
            goals_b INTEGER NOT NULL,
            delta_a1 REAL DEFAULT 0,
            delta_a2 REAL DEFAULT 0,
            delta_b1 REAL DEFAULT 0,
            delta_b2 REAL DEFAULT 0,
            delta_a REAL,
            delta_b REAL,
            leaderboard_id INTEGER REFERENCES leaderboards(id),
            season_id INTEGER
        );
        """))
        conn.execute(text("ALTER TABLE matches ADD COLUMN IF NOT EXISTS leaderboard_id INTEGER REFERENCES leaderboards(id);"))
        conn.execute(text("ALTER TABLE matches ADD COLUMN IF NOT EXISTS season_id INTEGER;"))

        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_matches_leaderboard_date
        ON matches (leaderboard_id, date DESC);
        """))
        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_matches_leaderboard_season_date
        ON matches (leaderboard_id, season_id, date DESC);
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS future_matches (
            id SERIAL PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            a1_id INTEGER REFERENCES players(id),
            a2_id INTEGER REFERENCES players(id),
            b1_id INTEGER REFERENCES players(id),
            b2_id INTEGER REFERENCES players(id),
            leaderboard_id INTEGER REFERENCES leaderboards(id),
            season_id INTEGER
        );
        """))
        conn.execute(text("ALTER TABLE future_matches ADD COLUMN IF NOT EXISTS season_id INTEGER;"))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS player_ratings_history (
            id SERIAL PRIMARY KEY,
            player_id INTEGER REFERENCES players(id),
            match_id INTEGER REFERENCES matches(id),
            rating REAL NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            leaderboard_id INTEGER REFERENCES leaderboards(id),
            season_id INTEGER
        );
        """))
        conn.execute(text("ALTER TABLE player_ratings_history ADD COLUMN IF NOT EXISTS leaderboard_id INTEGER REFERENCES leaderboards(id);"))
        conn.execute(text("ALTER TABLE player_ratings_history ADD COLUMN IF NOT EXISTS season_id INTEGER;"))
        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_ratings_history_leaderboard_season_created
        ON player_ratings_history (leaderboard_id, season_id, created_at);
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS seasons (
            id SERIAL PRIMARY KEY,
            leaderboard_id INTEGER REFERENCES leaderboards(id) ON DELETE CASCADE,
            number INTEGER NOT NULL,
            name TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            closed_at TIMESTAMP NULL,
            UNIQUE (leaderboard_id, number)
        );
        """))
        conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_seasons_one_active_per_leaderboard
        ON seasons (leaderboard_id)
        WHERE is_active = TRUE;
        """))

        # Tournament graph and the optional link from an ordinary match to a series.
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS tournaments (
            id SERIAL PRIMARY KEY, leaderboard_id INTEGER NOT NULL REFERENCES leaderboards(id) ON DELETE CASCADE,
            season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE RESTRICT, name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed')),
            winner_id INTEGER REFERENCES players(id), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE (leaderboard_id, season_id, name)
        );
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS tournament_participants (
            tournament_id INTEGER REFERENCES tournaments(id) ON DELETE CASCADE,
            player_id INTEGER REFERENCES players(id) ON DELETE RESTRICT,
            PRIMARY KEY (tournament_id, player_id)
        );
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS tournament_series (
            id SERIAL PRIMARY KEY, tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            round_index INTEGER NOT NULL, round_name TEXT NOT NULL, position INTEGER NOT NULL,
            challenger1_id INTEGER REFERENCES players(id), challenger2_id INTEGER REFERENCES players(id),
            is_final BOOLEAN NOT NULL DEFAULT FALSE,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','completed')),
            winner_id INTEGER REFERENCES players(id), next_series_id INTEGER REFERENCES tournament_series(id),
            next_slot INTEGER CHECK (next_slot IN (1,2)), UNIQUE (tournament_id, round_index, position)
        );
        """))
        conn.execute(text("ALTER TABLE matches ADD COLUMN IF NOT EXISTS tournament_series_id INTEGER REFERENCES tournament_series(id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_matches_tournament_series ON matches (tournament_series_id);"))

        # 3. Roles & Users
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            leaderboard_id INTEGER REFERENCES leaderboards(id)
        );
        """))
        conn.execute(text("ALTER TABLE roles ADD COLUMN IF NOT EXISTS leaderboard_id INTEGER REFERENCES leaderboards(id);"))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role_id INTEGER REFERENCES roles(id)
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            id SERIAL PRIMARY KEY,
            token_hash TEXT UNIQUE NOT NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            is_guest BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
            CHECK ((is_guest = TRUE AND user_id IS NULL)
                OR (is_guest = FALSE AND user_id IS NOT NULL))
        );
        """))
        conn.execute(text("""
        ALTER TABLE auth_sessions
        ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP;
        """))
        conn.execute(text("""
        UPDATE auth_sessions
        SET expires_at = created_at + INTERVAL '7 days'
        WHERE expires_at IS NULL;
        """))
        conn.execute(text("""
        ALTER TABLE auth_sessions
        ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '7 days');
        """))
        conn.execute(text("""
        ALTER TABLE auth_sessions
        ALTER COLUMN expires_at SET NOT NULL;
        """))

        # 4. Default Seed Data (Idempotent)
        # Default Leaderboards
        res = conn.execute(text("SELECT count(*) FROM leaderboards")).fetchone()
        if res[0] == 0:
            conn.execute(text("INSERT INTO leaderboards (name, code) VALUES ('Leaderboard DG', 'dg'), ('Leaderboard UT', 'ut')"))

        conn.execute(text("""
        INSERT INTO seasons (leaderboard_id, number, name, is_active, closed_at)
        SELECT id, 1, 'Season 1', FALSE, NOW()
        FROM leaderboards
        ON CONFLICT (leaderboard_id, number) DO NOTHING;
        """))
        conn.execute(text("""
        INSERT INTO seasons (leaderboard_id, number, name, is_active)
        SELECT id, 2, 'Season 2', TRUE
        FROM leaderboards
        ON CONFLICT (leaderboard_id, number) DO NOTHING;
        """))

        conn.execute(text("""
        UPDATE seasons s
        SET is_active = CASE WHEN s.number = 2 THEN TRUE ELSE FALSE END,
            closed_at = CASE WHEN s.number = 1 AND s.closed_at IS NULL THEN NOW() ELSE s.closed_at END
        WHERE s.number IN (1, 2);
        """))

        conn.execute(text("""
        UPDATE player_stats ps
        SET season_id = s.id
        FROM seasons s
        WHERE ps.season_id IS NULL
          AND s.leaderboard_id = ps.leaderboard_id
          AND s.number = 1;
        """))
        conn.execute(text("""
        UPDATE matches m
        SET season_id = s.id
        FROM seasons s
        WHERE m.season_id IS NULL
          AND s.leaderboard_id = m.leaderboard_id
          AND s.number = 1;
        """))
        conn.execute(text("""
        UPDATE player_ratings_history h
        SET season_id = s.id
        FROM seasons s
        WHERE h.season_id IS NULL
          AND s.leaderboard_id = h.leaderboard_id
          AND s.number = 1;
        """))
        conn.execute(text("""
        UPDATE future_matches fm
        SET season_id = s.id
        FROM seasons s
        WHERE fm.season_id IS NULL
          AND s.leaderboard_id = fm.leaderboard_id
          AND s.number = 2;
        """))

        conn.execute(text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'player_stats_player_id_leaderboard_id_key'
            ) THEN
                ALTER TABLE player_stats
                DROP CONSTRAINT player_stats_player_id_leaderboard_id_key;
            END IF;
        END $$;
        """))
        conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_player_stats_player_leaderboard_season
        ON player_stats (player_id, leaderboard_id, season_id);
        """))
        conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_player_stats_leaderboard_season_player
        ON player_stats (leaderboard_id, season_id, player_id);
        """))
        conn.execute(text("ALTER TABLE player_stats ALTER COLUMN season_id SET NOT NULL;"))
        conn.execute(text("ALTER TABLE matches ALTER COLUMN season_id SET NOT NULL;"))
        conn.execute(text("ALTER TABLE player_ratings_history ALTER COLUMN season_id SET NOT NULL;"))

        # Default Global Roles
        conn.execute(text("""
        INSERT INTO roles (name) VALUES ('guest'), ('user'), ('admin')
        ON CONFLICT (name) DO NOTHING;
        """))

        # Leaderboard-specific Manager Roles
        conn.execute(text("""
        INSERT INTO roles (name, leaderboard_id)
        SELECT 'Leader Manager ' || code, id FROM leaderboards
        ON CONFLICT (name) DO NOTHING;
        """))
