import hashlib
from datetime import datetime
import pandas as pd
from sqlalchemy import text
import streamlit as st
from db import get_connection, engine

K_FACTOR = 20.0

class DatabaseManager:
    """Manages all database interactions and business logic for the application."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Returns the SHA-256 hash of a password."""
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    @st.cache_data
    def get_leaderboard():
        """Fetches player statistics ordered by rating."""
        with get_connection() as conn:
            query = text("""
                SELECT name, rating, games, wins, losses, goal_diff
                FROM players
                ORDER BY rating DESC
            """)
            return conn.execute(query).fetchall()

    @staticmethod
    def add_player(name: str):
        """Adds a new player to the database."""
        with engine.begin() as conn:
            query = text("""
                INSERT INTO players (name, rating, games, wins, losses, goal_diff)
                VALUES (:name, 1000, 0, 0, 0, 0)
                ON CONFLICT (name) DO NOTHING
            """)
            conn.execute(query, {"name": name})
        st.cache_data.clear()

    @staticmethod
    @st.cache_data
    def get_match_history(limit=50):
        """Fetches the history of played matches."""
        with get_connection() as conn:
            query = text("""
                SELECT
                    m.date,
                    p1.name AS a1,
                    p2.name AS a2,
                    p3.name AS b1,
                    p4.name AS b2,
                    m.goals_a,
                    m.goals_b,
                    m.delta_a,
                    m.delta_b
                FROM matches m
                JOIN players p1 ON m.a1_id = p1.id
                JOIN players p2 ON m.a2_id = p2.id
                JOIN players p3 ON m.b1_id = p3.id
                JOIN players p4 ON m.b2_id = p4.id
                ORDER BY m.date DESC
                LIMIT :limit
            """)
            return conn.execute(query, {"limit": limit}).fetchall()

    @staticmethod
    @st.cache_data
    def get_elo_history():
        """Fetches the full Elo rating history for all players."""
        with get_connection() as conn:
            query = """
                SELECT
                    h.created_at,
                    p.name AS player,
                    h.rating
                FROM player_ratings_history h
                JOIN players p ON h.player_id = p.id
                ORDER BY h.created_at
            """
            return pd.read_sql(query, conn)

    @staticmethod
    @st.cache_data
    def check_login(username, password):
        """Validates user credentials."""
        with get_connection() as conn:
            query = text("""
                SELECT u.id, u.username, r.name AS role
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.username=:username AND u.password=:password
            """)
            return conn.execute(query, {
                "username": username,
                "password": DatabaseManager.hash_password(password)
            }).fetchone()

    @staticmethod
    @st.cache_data
    def get_player_names():
        """Fetches names of all registered players."""
        with get_connection() as conn:
            query = text("SELECT name FROM players ORDER BY name")
            rows = conn.execute(query).fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def _expected_score(r_team, r_opp):
        """Calculates the expected score based on ratings."""
        return 1.0 / (1.0 + 10 ** ((r_opp - r_team) / 400.0))

    @staticmethod
    def _margin_multiplier(margin):
        """Calculates the Elo margin multiplier based on goal difference."""
        if margin <= 2:
            return 1.0
        elif margin <= 9:
            return 1.0 + (margin - 2) * 0.1
        else:
            return 1.8

    @staticmethod
    def record_match(a1_name, a2_name, b1_name, b2_name, goals_a, goals_b):
        """Records a new match, updates player ratings, and saves history."""
        if goals_a == goals_b:
            raise ValueError("Draws are not allowed.")
        margin = abs(goals_a - goals_b)
        if margin < 2:
            raise ValueError("Minimum goal difference of 2 required.")

        with engine.begin() as conn:
            names = [a1_name, a2_name, b1_name, b2_name]
            # Fetch existing players
            fetch_query = text("""
                SELECT id, name, rating, games, wins, losses, goal_diff
                FROM players WHERE name IN :names
            """)
            res = conn.execute(fetch_query, {"names": tuple(names)})
            existing = {r.name: list(r) for r in res.fetchall()}

            # Ensure all players exist and load data
            players_data = []
            for name in names:
                if name not in existing:
                    insert_query = text("""
                        INSERT INTO players (name, rating, games, wins, losses, goal_diff)
                        VALUES (:name, 1000, 0, 0, 0, 0)
                        RETURNING id, name, rating, games, wins, losses, goal_diff
                    """)
                    row = conn.execute(insert_query, {"name": name}).fetchone()
                    existing[name] = list(row)
                players_data.append(existing[name])

            a1, a2, b1, b2 = players_data

            # Elo Calculation
            r_a = (a1[2] + a2[2]) / 2.0
            r_b = (b1[2] + b2[2]) / 2.0
            e_a = DatabaseManager._expected_score(r_a, r_b)
            s_a = 1.0 if goals_a > goals_b else 0.0
            m = DatabaseManager._margin_multiplier(margin)

            delta_a = round(K_FACTOR * m * (s_a - e_a))
            delta_b = -delta_a  # Zero-sum game logic

            # Update in-memory player data
            a1[2] += delta_a; a2[2] += delta_a
            b1[2] += delta_b; b2[2] += delta_b

            for p in [a1, a2, b1, b2]:
                p[3] += 1  # games count

            if s_a == 1:
                a1[4] += 1; a2[4] += 1; b1[5] += 1; b2[5] += 1  # A wins
            else:
                b1[4] += 1; b2[4] += 1; a1[5] += 1; a2[5] += 1  # B wins

            gd_a = goals_a - goals_b
            a1[6] += gd_a; a2[6] += gd_a; b1[6] -= gd_a; b2[6] -= gd_a

            # Batch Update Players in DB
            update_stmt = text("""
                UPDATE players
                SET rating=:r, games=:g, wins=:w, losses=:l, goal_diff=:gd
                WHERE id=:id
            """)
            conn.execute(update_stmt, [
                {"r": p[2], "g": p[3], "w": p[4], "l": p[5], "gd": p[6], "id": p[0]}
                for p in [a1, a2, b1, b2]
            ])

            # Insert Match record
            match_insert = text("""
                INSERT INTO matches
                (date, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, delta_a, delta_b)
                VALUES (:d, :a1, :a2, :b1, :b2, :ga, :gb, :da, :db)
                RETURNING id
            """)
            match_id = conn.execute(match_insert, {
                "d": datetime.now(),
                "a1": a1[0], "a2": a2[0],
                "b1": b1[0], "b2": b2[0],
                "ga": goals_a, "gb": goals_b,
                "da": delta_a, "db": delta_b
            }).scalar()

            # Batch Save Rating History in DB
            history_insert = text("""
                INSERT INTO player_ratings_history (player_id, match_id, rating)
                VALUES (:pid, :mid, :rating)
            """)
            conn.execute(history_insert, [
                {"pid": p[0], "mid": match_id, "rating": int(p[2])}
                for p in [a1, a2, b1, b2]
            ])
        
        st.cache_data.clear()
