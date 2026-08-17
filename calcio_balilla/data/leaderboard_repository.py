from sqlalchemy import text
from db import engine as default_engine
from calcio_balilla.core.domain import Leaderboard


def _row_dict(row, fields):
    if hasattr(row, "_mapping"):
        return {field: row._mapping[field] for field in fields}
    if hasattr(row, "__dict__"):
        data = row.__dict__
        if all(field in data for field in fields):
            return {field: data[field] for field in fields}
    return {field: row[index] for index, field in enumerate(fields)}


class LeaderboardRepository:
    def __init__(self, engine=None, get_connection=None):
        self.engine = engine or default_engine
        self._get_connection = get_connection or self.engine.connect

    def get_leaderboards(self):
        with self._get_connection() as conn:
            query = text("SELECT id, name, code FROM leaderboards ORDER BY id")
            rows = conn.execute(query).fetchall()
            fields = ("id", "name", "code")
            return [Leaderboard(**_row_dict(row, fields)) for row in rows]
