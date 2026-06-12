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
            rating REAL NOT NULL DEFAULT 1000,
            games INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            goal_diff INTEGER NOT NULL DEFAULT 0,
            trend TEXT DEFAULT '',
            UNIQUE(player_id, leaderboard_id)
        );
        """))

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
            leaderboard_id INTEGER REFERENCES leaderboards(id)
        );
        """))
        conn.execute(text("ALTER TABLE matches ADD COLUMN IF NOT EXISTS leaderboard_id INTEGER REFERENCES leaderboards(id);"))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS future_matches (
            id SERIAL PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            a1_id INTEGER REFERENCES players(id),
            a2_id INTEGER REFERENCES players(id),
            b1_id INTEGER REFERENCES players(id),
            b2_id INTEGER REFERENCES players(id),
            leaderboard_id INTEGER REFERENCES leaderboards(id)
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS player_ratings_history (
            id SERIAL PRIMARY KEY,
            player_id INTEGER REFERENCES players(id),
            match_id INTEGER REFERENCES matches(id),
            rating REAL NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            leaderboard_id INTEGER REFERENCES leaderboards(id)
        );
        """))
        conn.execute(text("ALTER TABLE player_ratings_history ADD COLUMN IF NOT EXISTS leaderboard_id INTEGER REFERENCES leaderboards(id);"))

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

        # 4. Default Seed Data (Idempotent)
        # Default Leaderboards
        res = conn.execute(text("SELECT count(*) FROM leaderboards")).fetchone()
        if res[0] == 0:
            conn.execute(text("INSERT INTO leaderboards (name, code) VALUES ('Leaderboard DG', 'dg'), ('Leaderboard UT', 'ut')"))

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
