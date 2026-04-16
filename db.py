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
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            rating REAL NOT NULL DEFAULT 1000,
            games INTEGER NOT NULL DEFAULT 0,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            goal_diff INTEGER NOT NULL DEFAULT 0,
            trend TEXT
        );
        """))

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
            delta_a REAL NOT NULL,
            delta_b REAL NOT NULL
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS player_ratings_history (
            id SERIAL PRIMARY KEY,
            player_id INTEGER REFERENCES players(id),
            match_id INTEGER REFERENCES matches(id),
            rating INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """))

        conn.execute(text("""
        ALTER TABLE players ADD COLUMN IF NOT EXISTS trend TEXT DEFAULT '';
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role_id INTEGER REFERENCES roles(id)
        );
        """))

        conn.execute(text("""
        INSERT INTO roles (name) VALUES
        ('guest'), ('user')
        ON CONFLICT (name) DO NOTHING;
        """))
