import hashlib
from datetime import datetime, timedelta
import random
import itertools
import pandas as pd
from sqlalchemy import text
import streamlit as st
from db import get_connection, engine
import scoring

class DatabaseManager:
    """Manages all database interactions and business logic for the application."""
    RECENT_DUPLICATE_MATCH_WINDOW_SECONDS = scoring.RECENT_DUPLICATE_MATCH_WINDOW_SECONDS

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
        return scoring.expected_score(r_team, r_opp)

    @staticmethod
    def _margin_multiplier(margin):
        """Calculates the Elo margin multiplier based on goal difference."""
        return scoring.margin_multiplier(margin)

    @staticmethod
    def _get_k_factor(games):
        """Returns a dynamic K-factor that decreases continuously as games increase."""
        return scoring.get_k_factor(games)

    @staticmethod
    def _calculate_match_updates(players, goals_a, goals_b, rating_diff_threshold):
        """Calculates player stat updates and Elo deltas without touching the database."""
        return scoring.calculate_match_updates(players, goals_a, goals_b, rating_diff_threshold)

    @staticmethod
    def _is_same_match(candidate, existing):
        return scoring.is_same_match(candidate, existing)

    @staticmethod
    def _get_recent_duplicate_match_id(conn, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, leaderboard_id):
        """Returns a recent matching record that likely came from a duplicate submit."""
        cutoff = scoring.recent_duplicate_cutoff(datetime.now())
        recent_matches_query = text("""
            SELECT id, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b
            FROM matches
            WHERE leaderboard_id = :l_id
              AND date >= :cutoff
            ORDER BY date DESC
        """)
        rows = conn.execute(recent_matches_query, {
            "l_id": leaderboard_id,
            "cutoff": cutoff,
        }).fetchall()
        candidate = {
            "a1_id": a1_id,
            "a2_id": a2_id,
            "b1_id": b1_id,
            "b2_id": b2_id,
            "goals_a": goals_a,
            "goals_b": goals_b,
        }

        for row in rows:
            existing = row._mapping if hasattr(row, "_mapping") else row
            if scoring.is_same_match(candidate, existing):
                return existing["id"]

        return None

    @staticmethod
    @st.cache_data
    def get_future_matches(leaderboard_id: int):
        """Fetches scheduled future matches for a specific leaderboard."""
        with get_connection() as conn:
            query = text("""
                SELECT
                    fm.date,
                    p1.name AS a1,
                    p2.name AS a2,
                    p3.name AS b1,
                    p4.name AS b2,
                    fm.id
                FROM future_matches fm
                JOIN players p1 ON fm.a1_id = p1.id
                JOIN players p2 ON fm.a2_id = p2.id
                JOIN players p3 ON fm.b1_id = p3.id
                JOIN players p4 ON fm.b2_id = p4.id
                WHERE fm.leaderboard_id = :l_id
                ORDER BY fm.date ASC
            """)
            return conn.execute(query, {"l_id": leaderboard_id}).fetchall()

    @staticmethod
    def generate_calendar(leaderboard_id: int, matches_per_day: int = 3, days: int = 7):
        """Generates a random schedule of matches for the next few days."""
        players_data = DatabaseManager.get_player_names(leaderboard_id)
        if len(players_data) < 4:
            return False

        player_ids = [p[0] for p in players_data]
        
        # We want to minimize repeat pairings. 
        # A simple approach: track how many times each pair has played together/against.
        # For a random generator, we can just shuffle and pick.
        
        with engine.begin() as conn:
            # Clear existing future matches for this leaderboard
            conn.execute(text("DELETE FROM future_matches WHERE leaderboard_id = :l_id"), {"l_id": leaderboard_id})
            
            start_date = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
            
            future_matches_to_insert = []
            for d in range(days):
                current_day = start_date + timedelta(days=d)
                for m in range(matches_per_day):
                    match_time = current_day + timedelta(minutes=30 * m)
                    selected = random.sample(player_ids, 4)
                    
                    future_matches_to_insert.append({
                        "date": match_time,
                        "a1": selected[0], "a2": selected[1],
                        "b1": selected[2], "b2": selected[3],
                        "l_id": leaderboard_id
                    })
            
            if future_matches_to_insert:
                conn.execute(text("""
                    INSERT INTO future_matches (date, a1_id, a2_id, b1_id, b2_id, leaderboard_id)
                    VALUES (:date, :a1, :a2, :b1, :b2, :l_id)
                """), future_matches_to_insert)
        st.cache_data.clear()
        return True

    @staticmethod
    def get_best_match_for_player(target_player_id: int, available_player_ids: list, leaderboard_id: int):
        """
        Generates the 'best match' for target_player_id from available_player_ids.
        'Best match' means a match where target_player is likely to win AND 
        gain points over rivals (players close in rating).
        """
        
        # 1. Get all player stats for the leaderboard
        with get_connection() as conn:
            query = text("""
                SELECT p.id, p.name, ps.rating, ps.games
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE p.is_active = TRUE AND ps.leaderboard_id = :l_id
            """)
            all_stats = conn.execute(query, {"l_id": leaderboard_id}).fetchall()
            
        stats_dict = {s.id: {"name": s.name, "rating": s.rating, "games": s.games} for s in all_stats}
        
        if target_player_id not in available_player_ids:
            available_player_ids.append(target_player_id)
            
        if len(available_player_ids) < 4:
            return None

        target_rating = stats_dict[target_player_id]["rating"]
        
        # Identify rivals: players with rating close to target (e.g., +/- 100)
        rivals = [s.id for s in all_stats if s.id != target_player_id and abs(s.rating - target_rating) < 150]
        if not rivals:
            # If no close rivals, consider everyone a rival for simplicity
            rivals = [s.id for s in all_stats if s.id != target_player_id]

        best_score = -9999
        best_match = None
        
        # Use a subset if too many players to avoid combinatorial explosion
        # Limit to 10 available players + target
        if len(available_player_ids) > 10:
             # Keep target, and 9 others (prioritize those with ratings close to target or high rating)
             available_player_ids = sorted(available_player_ids, key=lambda x: abs(stats_dict[x]["rating"] - target_rating))[:10]
             if target_player_id not in available_player_ids:
                 available_player_ids[-1] = target_player_id

        # Iterate over all possible combinations of 4 players including target
        other_players = [p for p in available_player_ids if p != target_player_id]
        for combo in itertools.combinations(other_players, 3):
            match_players = [target_player_id] + list(combo)
            
            # For these 4 players, try all possible team splits (3 ways)
            # 1. (T, P1) vs (P2, P3)
            # 2. (T, P2) vs (P1, P3)
            # 3. (T, P3) vs (P1, P2)
            
            p1, p2, p3 = combo
            possible_teams = [
                ((target_player_id, p1), (p2, p3)),
                ((target_player_id, p2), (p1, p3)),
                ((target_player_id, p3), (p1, p2))
            ]
            
            for team_a, team_b in possible_teams:
                # Calculate expected win probability and potential delta
                r_a = (stats_dict[team_a[0]]["rating"] + stats_dict[team_a[1]]["rating"]) / 2.0
                r_b = (stats_dict[team_b[0]]["rating"] + stats_dict[team_b[1]]["rating"]) / 2.0
                
                exp_a = DatabaseManager._expected_score(r_a, r_b)
                
                # We want: 
                # 1. High exp_a (likely to win)
                # 2. Good delta if win (not playing against much weaker players)
                # 3. Rivals in Team B (to take points from them)
                
                # Potential delta for a standard 10-8 win (margin 2)
                # K-factor for target player
                k = DatabaseManager._get_k_factor(stats_dict[target_player_id]["games"])
                delta_if_win = k * 1.0 * (1.0 - exp_a)
                
                # Rival penalty/bonus: if a rival is in team B, it's good. 
                # If a rival is in team A, it might be bad (they gain points too).
                rival_impact = 0
                for p_id in team_b:
                    if p_id in rivals:
                        rival_impact += 1
                for p_id in team_a:
                    if p_id == target_player_id: continue
                    if p_id in rivals:
                        rival_impact -= 0.5
                
                # Heuristic score
                # prioritize probability of winning but also the gain
                # score = (win_prob * 0.7 + normalized_delta * 0.3) + rival_impact
                match_score = (exp_a * 10) + (delta_if_win * 0.5) + (rival_impact * 5)
                
                if match_score > best_score:
                    best_score = match_score
                    best_match = {
                        "team_a": (stats_dict[team_a[0]]["name"], stats_dict[team_a[1]]["name"]),
                        "team_b": (stats_dict[team_b[0]]["name"], stats_dict[team_b[1]]["name"]),
                        "win_prob": exp_a,
                        "est_delta": delta_if_win
                    }
                    
        return best_match

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

            duplicate_match_id = DatabaseManager._get_recent_duplicate_match_id(
                conn, a1[0], a2[0], b1[0], b2[0], goals_a, goals_b, leaderboard_id
            )
            if duplicate_match_id:
                raise ValueError("This match was saved a few seconds ago. Wait before saving the same match again.")

            players, deltas = scoring.calculate_match_updates(
                [a1, a2, b1, b2], goals_a, goals_b, rating_diff_threshold
            )
            a1, a2, b1, b2 = players
            delta_a1, delta_a2, delta_b1, delta_b2 = deltas

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
