import pandas as pd
from sqlalchemy import text
from db import engine as default_engine
from calcio_balilla.core.domain import Player, PlayerStandings, PlayerStats, PlayerMatchStats


def _row_dict(row, fields):
    if hasattr(row, "_mapping"):
        return {field: row._mapping[field] for field in fields}
    if hasattr(row, "__dict__"):
        data = row.__dict__
        if all(field in data for field in fields):
            return {field: data[field] for field in fields}
    return {field: row[index] for index, field in enumerate(fields)}


class PlayerRepository:
    def __init__(self, engine=None, get_connection=None):
        self.engine = engine or default_engine
        self._get_connection = get_connection or self.engine.connect

    def get_leaderboard(self, leaderboard_id: int):
        with self._get_connection() as conn:
            query = text("""
                SELECT p.name, ps.rating, ps.games, ps.wins, ps.losses, ps.goal_diff, ps.trend
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE p.is_active = TRUE AND ps.leaderboard_id = :l_id
                ORDER BY ps.rating DESC
            """)
            rows = conn.execute(query, {"l_id": leaderboard_id}).fetchall()
            fields = ("name", "rating", "games", "wins", "losses", "goal_diff", "trend")
            return [PlayerStandings(**_row_dict(row, fields)) for row in rows]

    def add_player(self, name: str, leaderboard_id: int):
        with self.engine.begin() as conn:
            # 1. Ensure player exists globally
            player_id_res = conn.execute(text("""
                INSERT INTO players (name, is_active)
                VALUES (:name, TRUE)
                ON CONFLICT (name) DO UPDATE SET is_active = TRUE
                RETURNING id
            """), {"name": name}).fetchone()
            player_id = _row_dict(player_id_res, ("id",))["id"]
            
            # 2. Ensure player_stats exists for this specific leaderboard
            conn.execute(text("""
                INSERT INTO player_stats (player_id, leaderboard_id, rating, games, wins, losses, goal_diff, trend)
                VALUES (:pid, :l_id, 1000, 0, 0, 0, 0, '')
                ON CONFLICT (player_id, leaderboard_id) DO NOTHING
            """), {"pid": player_id, "l_id": leaderboard_id})
            return player_id

    def toggle_player_status(self, player_id: int, is_active: bool):
        with self.engine.begin() as conn:
            query = text("UPDATE players SET is_active = :status WHERE id = :pid")
            conn.execute(query, {"status": is_active, "pid": player_id})

    def get_player_names(self, leaderboard_id: int):
        with self._get_connection() as conn:
            query = text("""
                SELECT p.id, p.name 
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE p.is_active = TRUE AND ps.leaderboard_id = :l_id
                ORDER BY p.name
            """)
            rows = conn.execute(query, {"l_id": leaderboard_id}).fetchall()
        return [Player(id=_row_dict(row, ("id", "name"))["id"], name=_row_dict(row, ("id", "name"))["name"], is_active=True) for row in rows]

    def get_all_players(self, leaderboard_id: int):
        with self._get_connection() as conn:
            query = text("""
                SELECT p.id, p.name, p.is_active 
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE ps.leaderboard_id = :l_id
                ORDER BY p.name
            """)
            rows = conn.execute(query, {"l_id": leaderboard_id}).fetchall()
            fields = ("id", "name", "is_active")
            return [Player(**_row_dict(row, fields)) for row in rows]

    def get_elo_history(self, leaderboard_id: int = None):
        with self._get_connection() as conn:
            query = """
                SELECT
                    h.created_at,
                    p.name AS player,
                    h.rating
                FROM player_ratings_history h
                JOIN players p ON h.player_id = p.id
            """
            params = {}
            if leaderboard_id is not None:
                query += " WHERE h.leaderboard_id = :l_id"
                params["l_id"] = leaderboard_id
            
            query += " ORDER BY h.created_at"
            return pd.read_sql(text(query), conn, params=params)

    def get_player_stats_for_match(self, conn, names: tuple, leaderboard_id: int):
        fetch_query = text("""
            SELECT p.id, p.name, ps.rating, ps.games, ps.wins, ps.losses, ps.goal_diff, ps.trend
            FROM players p
            JOIN player_stats ps ON p.id = ps.player_id
            WHERE p.name IN :names AND ps.leaderboard_id = :l_id
        """)
        rows = conn.execute(fetch_query, {"names": names, "l_id": leaderboard_id}).fetchall()
        fields = ("id", "name", "rating", "games", "wins", "losses", "goal_diff", "trend")
        return [PlayerMatchStats(**_row_dict(row, fields)) for row in rows]

    def ensure_players_exist_globally(self, conn, names: list):
        conn.execute(text("""
            INSERT INTO players (name) 
            VALUES (:n1), (:n2), (:n3), (:n4)
            ON CONFLICT (name) DO NOTHING
        """), {"n1": names[0], "n2": names[1], "n3": names[2], "n4": names[3]})

    def ensure_player_stats_exist_for_leaderboard(self, conn, names: tuple, leaderboard_id: int):
        conn.execute(text("""
            INSERT INTO player_stats (player_id, leaderboard_id)
            SELECT id, :l_id FROM players WHERE name IN :names
            ON CONFLICT (player_id, leaderboard_id) DO NOTHING
        """), {"names": names, "l_id": leaderboard_id})

    def get_rating_range(self, conn, leaderboard_id: int):
        range_res = conn.execute(text("""
            SELECT MAX(rating), MIN(rating) 
            FROM player_stats 
            WHERE leaderboard_id = :l_id
        """), {"l_id": leaderboard_id}).fetchone()
        if not range_res:
            return (1000.0, 1000.0)
        values = tuple(_row_dict(range_res, ("max", "min")).values())
        return values if values[0] is not None else (1000.0, 1000.0)

    def update_player_stats_batch(self, conn, updates: list):
        update_stmt = text("""
            UPDATE player_stats
            SET rating=:r, games=:g, wins=:w, losses=:l, goal_diff=:gd, trend=:t
            WHERE player_id=:pid AND leaderboard_id=:l_id
        """)
        conn.execute(update_stmt, updates)

    def get_player_stats_by_ids(self, conn, player_ids: tuple, leaderboard_id: int):
        rows = conn.execute(
            text("""
                SELECT player_id, rating, games, wins, losses, goal_diff 
                FROM player_stats 
                WHERE player_id IN :ids AND leaderboard_id = :l_id
            """),
            {"ids": player_ids, "l_id": leaderboard_id}
        ).fetchall()
        fields = ("player_id", "rating", "games", "wins", "losses", "goal_diff")
        return [PlayerStats(**_row_dict(row, fields)) for row in rows]

    def get_player_trends_excluding_match(self, conn, player_ids: tuple, match_id: int, leaderboard_id: int):
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
        return conn.execute(trend_query, {"ids": player_ids, "mid": match_id, "l_id": leaderboard_id}).fetchall()

    def get_active_players_ratings_games(self, leaderboard_id: int):
        with self._get_connection() as conn:
            query = text("""
                SELECT p.id, p.name, ps.rating, ps.games
                FROM players p
                JOIN player_stats ps ON p.id = ps.player_id
                WHERE p.is_active = TRUE AND ps.leaderboard_id = :l_id
            """)
            rows = conn.execute(query, {"l_id": leaderboard_id}).fetchall()
            return [
                PlayerMatchStats(
                    id=_row_dict(row, ("id", "name", "rating", "games"))["id"],
                    name=_row_dict(row, ("id", "name", "rating", "games"))["name"],
                    rating=_row_dict(row, ("id", "name", "rating", "games"))["rating"],
                    games=_row_dict(row, ("id", "name", "rating", "games"))["games"],
                    wins=0,
                    losses=0,
                    goal_diff=0,
                    trend="",
                )
                for row in rows
            ]
