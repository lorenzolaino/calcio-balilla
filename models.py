import hashlib
from datetime import datetime
import pandas as pd
from sqlalchemy import text
import streamlit as st
from db import get_connection, engine

class DatabaseManager:
    """Manages all database interactions and business logic for the application."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Returns the SHA-256 hash of a password."""
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    @st.cache_data
    def get_leaderboards():
        """Fetches all available leaderboards."""
        with get_connection() as conn:
            query = text("SELECT id, name, code FROM leaderboards ORDER BY id")
            return conn.execute(query).fetchall()

    @staticmethod
    @st.cache_data
    def get_leaderboard(leaderboard_id: int):
        """Fetches active player statistics for a specific leaderboard."""
        with get_connection() as conn:
            query = text("""
                SELECT p.name, ps.rating, ps.games, ps.wins, ps.losses, ps.goal_diff, ps.trend
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE p.is_active = TRUE AND ps.leaderboard_id = :l_id
                ORDER BY ps.rating DESC
            """)
            return conn.execute(query, {"l_id": leaderboard_id}).fetchall()

    @staticmethod
    def add_player(name: str, leaderboard_id: int):
        """Adds a new player and initializes stats for the selected leaderboard."""
        with engine.begin() as conn:
            # 1. Ensure player exists globally
            player_id_res = conn.execute(text("""
                INSERT INTO players (name, is_active)
                VALUES (:name, TRUE)
                ON CONFLICT (name) DO UPDATE SET is_active = TRUE
                RETURNING id
            """), {"name": name}).fetchone()
            player_id = player_id_res[0]
            
            # 2. Ensure player_stats exists for this specific leaderboard
            conn.execute(text("""
                INSERT INTO player_stats (player_id, leaderboard_id, rating, games, wins, losses, goal_diff, trend)
                VALUES (:pid, :l_id, 1000, 0, 0, 0, 0, '')
                ON CONFLICT (player_id, leaderboard_id) DO NOTHING
            """), {"pid": player_id, "l_id": leaderboard_id})
            
        st.cache_data.clear()

    @staticmethod
    def toggle_player_status(player_id: int, is_active: bool):
        """Toggles a player's active status."""
        with engine.begin() as conn:
            query = text("UPDATE players SET is_active = :status WHERE id = :pid")
            conn.execute(query, {"status": is_active, "pid": player_id})
        st.cache_data.clear()

    @staticmethod
    @st.cache_data
    def get_match_history(limit=50, player_id=None, leaderboard_id=None):
        """Fetches the history of played matches, optionally filtered by player_id and leaderboard_id."""
        with get_connection() as conn:
            query_str = """
                SELECT
                    m.date,
                    p1.name AS a1,
                    p2.name AS a2,
                    p3.name AS b1,
                    p4.name AS b2,
                    m.goals_a,
                    m.goals_b,
                    m.delta_a1,
                    m.delta_a2,
                    m.delta_b1,
                    m.delta_b2,
                    m.delta_a,
                    m.delta_b,
                    m.id
                FROM matches m
                JOIN players p1 ON m.a1_id = p1.id
                JOIN players p2 ON m.a2_id = p2.id
                JOIN players p3 ON m.b1_id = p3.id
                JOIN players p4 ON m.b2_id = p4.id
            """
            where_clauses = []
            params = {"limit": limit}
            
            if player_id:
                where_clauses.append("(m.a1_id = :pid OR m.a2_id = :pid OR m.b1_id = :pid OR m.b2_id = :pid)")
                params["pid"] = player_id
            
            if leaderboard_id:
                where_clauses.append("m.leaderboard_id = :l_id")
                params["l_id"] = leaderboard_id
                
            if where_clauses:
                query_str += " WHERE " + " AND ".join(where_clauses)
                
            query_str += " ORDER BY m.date DESC LIMIT :limit"
            
            return conn.execute(text(query_str), params).fetchall()

    @staticmethod
    @st.cache_data
    def get_elo_history(leaderboard_id=None):
        """Fetches the full Elo rating history for all players, optionally filtered by leaderboard_id."""
        with get_connection() as conn:
            query = """
                SELECT
                    h.created_at,
                    p.name AS player,
                    h.rating
                FROM player_ratings_history h
                JOIN players p ON h.player_id = p.id
            """
            params = {}
            if leaderboard_id:
                query += " WHERE h.leaderboard_id = :l_id"
                params["l_id"] = leaderboard_id
            
            query += " ORDER BY h.created_at"
            return pd.read_sql(text(query), conn, params=params)

    @staticmethod
    @st.cache_data
    def check_login(username, password):
        """Validates user credentials."""
        with get_connection() as conn:
            query = text("""
                SELECT u.id, u.username, r.name AS role, r.leaderboard_id
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
    def get_player_names(leaderboard_id: int):
        """Fetches IDs and names of active players for a specific leaderboard."""
        with get_connection() as conn:
            query = text("""
                SELECT p.id, p.name 
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE p.is_active = TRUE AND ps.leaderboard_id = :l_id
                ORDER BY p.name
            """)
            rows = conn.execute(query, {"l_id": leaderboard_id}).fetchall()
        return [(r[0], r[1]) for r in rows]

    @staticmethod
    @st.cache_data
    def get_all_players(leaderboard_id: int):
        """Fetches all players (active and inactive) for a specific leaderboard."""
        with get_connection() as conn:
            query = text("""
                SELECT p.id, p.name, p.is_active 
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE ps.leaderboard_id = :l_id
                ORDER BY p.name
            """)
            return conn.execute(query, {"l_id": leaderboard_id}).fetchall()

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
    def _get_k_factor(games):
        """Returns a dynamic K-factor that decreases continuously as games increase."""
        # Starts at 30.0, drops to 20.0 at 40 games, ~15 at 120 games.
        # Asymptotic to 10.0
        return 10.0 + (20.0 / (1.0 + (games / 40.0)))

    @staticmethod
    def delete_match(match_id):
        """Deletes a match and restores player stats efficiently."""
        with engine.begin() as conn:
            # 1. Get match details
            match_query = text("""
                SELECT a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, 
                       delta_a1, delta_a2, delta_b1, delta_b2, leaderboard_id
                FROM matches WHERE id = :mid
            """)
            match = conn.execute(match_query, {"mid": match_id}).fetchone()
            if not match:
                return False

            m = match._asdict() if hasattr(match, "_asdict") else match._mapping
            player_ids = [m["a1_id"], m["a2_id"], m["b1_id"], m["b2_id"]]
            l_id = m["leaderboard_id"]

            # 2. Fetch all involved players' stats for THIS leaderboard
            players_res = conn.execute(
                text("SELECT player_id, rating, games, wins, losses, goal_diff FROM player_stats WHERE player_id IN :ids AND leaderboard_id = :l_id"),
                {"ids": tuple(player_ids), "l_id": l_id}
            ).fetchall()
            players = {p.player_id: list(p) for p in players_res}

            # 3. Calculate restored stats in memory
            roles = [
                (m["a1_id"], m["delta_a1"], m["goals_a"] > m["goals_b"], m["goals_a"] - m["goals_b"]),
                (m["a2_id"], m["delta_a2"], m["goals_a"] > m["goals_b"], m["goals_a"] - m["goals_b"]),
                (m["b1_id"], m["delta_b1"], m["goals_b"] > m["goals_a"], m["goals_b"] - m["goals_a"]),
                (m["b2_id"], m["delta_b2"], m["goals_b"] > m["goals_a"], m["goals_b"] - m["goals_a"]),
            ]

            for pid, delta, is_win, gd_contrib in roles:
                p = players[pid]
                p[1] -= delta        # rating
                p[2] -= 1            # games
                if is_win:
                    p[3] -= 1        # wins
                else:
                    p[4] -= 1        # losses
                p[5] -= gd_contrib   # goal_diff

            # 4. Get new trends for all players in THIS leaderboard
            trend_query = text("""
                SELECT pid, STRING_AGG(result, ' ' ORDER BY date DESC) as trend
                FROM (
                    SELECT 
                        p.id as pid,
                        m.date,
                        CASE 
                            WHEN (m.a1_id = p.id OR m.a2_id = p.id) AND m.goals_a > m.goals_b THEN 'W'
                            WHEN (m.b1_id = p.id OR m.b2_id = p.id) AND m.goals_b > m.goals_a THEN 'W'
                            ELSE 'L'
                        END as result,
                        ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY m.date DESC) as rn
                    FROM players p
                    JOIN matches m ON m.a1_id = p.id OR m.a2_id = p.id OR m.b1_id = p.id OR m.b2_id = p.id
                    WHERE p.id IN :ids AND m.id != :mid AND m.leaderboard_id = :l_id
                ) t 
                WHERE rn <= 5
                GROUP BY pid
            """)
            trends_res = conn.execute(trend_query, {"ids": tuple(player_ids), "mid": match_id, "l_id": l_id}).fetchall()
            trends = {t.pid: t.trend for t in trends_res}

            # 5. Batch Update Player Stats
            update_stmt = text("""
                UPDATE player_stats
                SET rating=:r, games=:g, wins=:w, losses=:l, goal_diff=:gd, trend=:t
                WHERE player_id=:pid AND leaderboard_id=:l_id
            """)
            conn.execute(update_stmt, [
                {
                    "r": players[pid][1], 
                    "g": players[pid][2], 
                    "w": players[pid][3], 
                    "l": players[pid][4], 
                    "gd": players[pid][5], 
                    "t": trends.get(pid, ""),
                    "pid": pid,
                    "l_id": l_id
                }
                for pid in player_ids
            ])

            # 6. Delete match and history
            conn.execute(text("DELETE FROM player_ratings_history WHERE match_id = :mid"), {"mid": match_id})
            conn.execute(text("DELETE FROM matches WHERE id = :mid"), {"mid": match_id})

        st.cache_data.clear()
        return True

    @staticmethod
    def record_match(a1_name, a2_name, b1_name, b2_name, goals_a, goals_b, leaderboard_id):
        """Records a new match, updates player ratings, and saves history."""
        if goals_a == goals_b:
            raise ValueError("Draws are not allowed.")
        margin = abs(goals_a - goals_b)
        if margin < 2:
            raise ValueError("Minimum goal difference of 2 required.")

        with engine.begin() as conn:
            names = [a1_name, a2_name, b1_name, b2_name]
            
            # 1. Ensure all players exist globally (Batch)
            conn.execute(text("""
                INSERT INTO players (name) 
                VALUES (:n1), (:n2), (:n3), (:n4)
                ON CONFLICT (name) DO NOTHING
            """), {"n1": a1_name, "n2": a2_name, "n3": b1_name, "n4": b2_name})

            # 2. Ensure all players have stats entries for this leaderboard (Batch)
            conn.execute(text("""
                INSERT INTO player_stats (player_id, leaderboard_id)
                SELECT id, :l_id FROM players WHERE name IN :names
                ON CONFLICT (player_id, leaderboard_id) DO NOTHING
            """), {"names": tuple(names), "l_id": leaderboard_id})

            # 3. Get rating range for farming threshold (1 call)
            range_res = conn.execute(text("SELECT MAX(rating), MIN(rating) FROM player_stats WHERE leaderboard_id = :l_id"), {"l_id": leaderboard_id}).fetchone()
            max_r, min_r = range_res if range_res and range_res[0] is not None else (1000, 1000)
            rating_diff_threshold = (max_r - min_r) * 0.5 

            # 4. Fetch existing stats for these players in this leaderboard (1 call)
            fetch_query = text("""
                SELECT p.id, p.name, ps.rating, ps.games, ps.wins, ps.losses, ps.goal_diff, ps.trend
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE p.name IN :names AND ps.leaderboard_id = :l_id
            """)
            res = conn.execute(fetch_query, {"names": tuple(names), "l_id": leaderboard_id})
            existing = {r.name: list(r) for r in res.fetchall()}

            a1, a2, b1, b2 = [existing[name] for name in names]

            # Elo Calculation
            r_a = (a1[2] + a2[2]) / 2.0
            r_b = (b1[2] + b2[2]) / 2.0
            e_a = DatabaseManager._expected_score(r_a, r_b)
            s_a = 1.0 if goals_a > goals_b else 0.0
            m = DatabaseManager._margin_multiplier(margin)

            # Farming prevention logic
            multiplier = 1.0
            team_diff = r_a - r_b
            is_a_favored = team_diff > 0
            
            if abs(team_diff) > rating_diff_threshold:
                if (is_a_favored and s_a == 1.0) or (not is_a_favored and s_a == 0.0):
                    # Favored team wins: halved points
                    multiplier = 0.5
                else:
                    # Favored team loses: increased points (penalty)
                    multiplier = 1.5

            # Individual deltas based on player's own K-factor
            delta_a1 = round(DatabaseManager._get_k_factor(a1[3]) * m * multiplier * (s_a - e_a), 1)
            delta_a2 = round(DatabaseManager._get_k_factor(a2[3]) * m * multiplier * (s_a - e_a), 1)
            delta_b1 = round(DatabaseManager._get_k_factor(b1[3]) * m * multiplier * ((1-s_a) - (1-e_a)), 1)
            delta_b2 = round(DatabaseManager._get_k_factor(b2[3]) * m * multiplier * ((1-s_a) - (1-e_a)), 1)

            # Update in-memory player data
            a1[2] += delta_a1; a2[2] += delta_a2
            b1[2] += delta_b1; b2[2] += delta_b2

            for p in [a1, a2, b1, b2]:
                p[3] += 1  # games count

            if s_a == 1:
                a1[4] += 1; a2[4] += 1; b1[5] += 1; b2[5] += 1  # A wins
            else:
                b1[4] += 1; b2[4] += 1; a1[5] += 1; a2[5] += 1  # B wins

            gd_a = goals_a - goals_b
            a1[6] += gd_a; a2[6] += gd_a; b1[6] -= gd_a; b2[6] -= gd_a

            # After updating stats and before DB update, calculate trend for each player
            for i, p in enumerate([a1, a2, b1, b2]):
                # If player was in Team A (i=0,1) and Team A won, or Team B (i=2,3) and Team B won
                is_win = (i < 2 and s_a == 1) or (i >= 2 and s_a == 0)
                res_char = 'W' if is_win else 'L'
                
                current_trend = p[7] if p[7] else ""
                parts = current_trend.split()
                new_parts = ([res_char] + parts)[:5]
                p[7] = " ".join(new_parts)

            # Batch Update Player Stats in DB
            update_stmt = text("""
                UPDATE player_stats
                SET rating=:r, games=:g, wins=:w, losses=:l, goal_diff=:gd, trend=:t
                WHERE player_id=:pid AND leaderboard_id=:l_id
            """)
            conn.execute(update_stmt, [
                {"r": p[2], "g": p[3], "w": p[4], "l": p[5], "gd": p[6], "t": p[7], "pid": p[0], "l_id": leaderboard_id}
                for p in [a1, a2, b1, b2]
            ])

            # Insert Match record
            match_insert = text("""
                INSERT INTO matches
                (date, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, delta_a1, delta_a2, delta_b1, delta_b2, leaderboard_id)
                VALUES (:d, :a1, :a2, :b1, :b2, :ga, :gb, :da1, :da2, :db1, :db2, :l_id)
                RETURNING id
            """)
            match_id = conn.execute(match_insert, {
                "d": datetime.now(),
                "a1": a1[0], "a2": a2[0],
                "b1": b1[0], "b2": b2[0],
                "ga": goals_a, "gb": goals_b,
                "da1": delta_a1, "da2": delta_a2,
                "db1": delta_b1, "db2": delta_b2,
                "l_id": leaderboard_id
            }).scalar()

            # Batch Save Rating History in DB
            history_insert = text("""
                INSERT INTO player_ratings_history (player_id, match_id, rating, leaderboard_id)
                VALUES (:pid, :mid, :rating, :l_id)
            """)
            conn.execute(history_insert, [
                {"pid": p[0], "mid": match_id, "rating": int(p[2]), "l_id": leaderboard_id}
                for p in [a1, a2, b1, b2]
            ])
        
        st.cache_data.clear()
