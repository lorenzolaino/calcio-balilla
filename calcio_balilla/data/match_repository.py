from datetime import datetime
from sqlalchemy import text
from db import engine as default_engine
import scoring
from calcio_balilla.core.domain import FutureMatchEntry, MatchHistoryEntry, MatchRecord


def _row_dict(row, fields):
    if hasattr(row, "_mapping"):
        return {field: row._mapping[field] for field in fields}
    if hasattr(row, "__dict__"):
        data = row.__dict__
        if all(field in data for field in fields):
            return {field: data[field] for field in fields}
    return {field: row[index] for index, field in enumerate(fields)}

class MatchRepository:
    def __init__(self, engine=None, get_connection=None):
        self.engine = engine or default_engine
        self._get_connection = get_connection or self.engine.connect

    def get_match_history(self, limit=50, player_id=None, leaderboard_id=None):
        with self._get_connection() as conn:
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
            
            rows = conn.execute(text(query_str), params).fetchall()
            fields = (
                "date", "a1", "a2", "b1", "b2", "goals_a", "goals_b",
                "delta_a1", "delta_a2", "delta_b1", "delta_b2", "delta_a", "delta_b", "id",
            )
            return [MatchHistoryEntry(**_row_dict(row, fields)) for row in rows]

    def get_future_matches(self, leaderboard_id: int):
        with self._get_connection() as conn:
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
            rows = conn.execute(query, {"l_id": leaderboard_id}).fetchall()
            fields = ("date", "a1", "a2", "b1", "b2", "id")
            return [FutureMatchEntry(**_row_dict(row, fields)) for row in rows]

    def delete_future_matches(self, conn, leaderboard_id: int):
        conn.execute(text("DELETE FROM future_matches WHERE leaderboard_id = :l_id"), {"l_id": leaderboard_id})

    def insert_future_matches(self, conn, future_matches: list):
        conn.execute(text("""
            INSERT INTO future_matches (date, a1_id, a2_id, b1_id, b2_id, leaderboard_id)
            VALUES (:date, :a1, :a2, :b1, :b2, :l_id)
        """), future_matches)

    def get_match_by_id(self, conn, match_id: int):
        match_query = text("""
            SELECT a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, 
                   delta_a1, delta_a2, delta_b1, delta_b2, leaderboard_id
            FROM matches WHERE id = :mid
        """)
        row = conn.execute(match_query, {"mid": match_id}).fetchone()
        fields = (
            "a1_id", "a2_id", "b1_id", "b2_id", "goals_a", "goals_b",
            "delta_a1", "delta_a2", "delta_b1", "delta_b2", "leaderboard_id",
        )
        return MatchRecord(**_row_dict(row, fields)) if row else None

    def delete_player_ratings_history(self, conn, match_id: int):
        conn.execute(text("DELETE FROM player_ratings_history WHERE match_id = :mid"), {"mid": match_id})

    def delete_match_record(self, conn, match_id: int):
        conn.execute(text("DELETE FROM matches WHERE id = :mid"), {"mid": match_id})

    def insert_match_record(self, conn, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, delta_a1, delta_a2, delta_b1, delta_b2, leaderboard_id: int):
        match_insert = text("""
            INSERT INTO matches
            (date, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, delta_a1, delta_a2, delta_b1, delta_b2, leaderboard_id)
            VALUES (:d, :a1, :a2, :b1, :b2, :ga, :gb, :da1, :da2, :db1, :db2, :l_id)
            RETURNING id
        """)
        return conn.execute(match_insert, {
            "d": datetime.now(),
            "a1": a1_id, "a2": a2_id,
            "b1": b1_id, "b2": b2_id,
            "ga": goals_a, "gb": goals_b,
            "da1": delta_a1, "da2": delta_a2,
            "db1": delta_b1, "db2": delta_b2,
            "l_id": leaderboard_id
        }).scalar()

    def insert_player_ratings_history_batch(self, conn, updates: list):
        history_insert = text("""
            INSERT INTO player_ratings_history (player_id, match_id, rating, leaderboard_id)
            VALUES (:pid, :mid, :rating, :l_id)
        """)
        conn.execute(history_insert, updates)

    def get_recent_duplicate_match_id(self, conn, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, leaderboard_id: int, now=None):
        now = now or datetime.now()
        cutoff = scoring.recent_duplicate_cutoff(now)
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
            existing = _row_dict(row, ("id", "a1_id", "a2_id", "b1_id", "b2_id", "goals_a", "goals_b"))
            if scoring.is_same_match(candidate, existing):
                return existing["id"]

        return None
