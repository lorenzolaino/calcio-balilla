from sqlalchemy import text

from db import engine as default_engine
from calcio_balilla.core.domain import Season


def _row_dict(row, fields):
    if hasattr(row, "_mapping"):
        return {field: row._mapping[field] for field in fields}
    if hasattr(row, "__dict__"):
        data = row.__dict__
        if all(field in data for field in fields):
            return {field: data[field] for field in fields}
    return {field: row[index] for index, field in enumerate(fields)}


class SeasonRepository:
    def __init__(self, engine=None, get_connection=None):
        self.engine = engine or default_engine
        self._get_connection = get_connection or self.engine.connect

    def get_active_season(self, leaderboard_id: int):
        with self._get_connection() as conn:
            return self.get_active_season_for_update(conn, leaderboard_id, lock=False)

    def get_closed_seasons(self, leaderboard_id: int):
        with self._get_connection() as conn:
            query = text("""
                SELECT id, leaderboard_id, number, name, is_active
                FROM seasons
                WHERE leaderboard_id = :l_id AND is_active = FALSE
                ORDER BY number DESC
            """)
            rows = conn.execute(query, {"l_id": leaderboard_id}).fetchall()
            fields = ("id", "leaderboard_id", "number", "name", "is_active")
            return [Season(**_row_dict(row, fields)) for row in rows]

    def get_season_by_id(self, season_id: int):
        with self._get_connection() as conn:
            query = text("""
                SELECT id, leaderboard_id, number, name, is_active
                FROM seasons
                WHERE id = :season_id
            """)
            row = conn.execute(query, {"season_id": season_id}).fetchone()
            fields = ("id", "leaderboard_id", "number", "name", "is_active")
            return Season(**_row_dict(row, fields)) if row else None

    def get_active_season_for_update(self, conn, leaderboard_id: int, lock: bool = True):
        suffix = " FOR UPDATE" if lock else ""
        query = text(f"""
            SELECT id, leaderboard_id, number, name, is_active
            FROM seasons
            WHERE leaderboard_id = :l_id AND is_active = TRUE
            ORDER BY number DESC
            LIMIT 1{suffix}
        """)
        row = conn.execute(query, {"l_id": leaderboard_id}).fetchone()
        fields = ("id", "leaderboard_id", "number", "name", "is_active")
        return Season(**_row_dict(row, fields)) if row else None

    def close_season(self, conn, season_id: int):
        conn.execute(text("""
            UPDATE seasons
            SET is_active = FALSE,
                closed_at = NOW()
            WHERE id = :season_id
        """), {"season_id": season_id})

    def create_season(self, conn, leaderboard_id: int, number: int):
        row = conn.execute(text("""
            INSERT INTO seasons (leaderboard_id, number, name, is_active)
            VALUES (:l_id, :number, :name, TRUE)
            RETURNING id, leaderboard_id, number, name, is_active
        """), {
            "l_id": leaderboard_id,
            "number": number,
            "name": f"Season {number}",
        }).fetchone()
        fields = ("id", "leaderboard_id", "number", "name", "is_active")
        return Season(**_row_dict(row, fields))
