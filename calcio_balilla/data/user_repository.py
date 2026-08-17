from sqlalchemy import text
from db import engine as default_engine
from calcio_balilla.core.domain import UserSession


def _row_dict(row, fields):
    if hasattr(row, "_mapping"):
        return {field: row._mapping[field] for field in fields}
    if hasattr(row, "__dict__"):
        data = row.__dict__
        if all(field in data for field in fields):
            return {field: data[field] for field in fields}
    return {field: row[index] for index, field in enumerate(fields)}


class UserRepository:
    def __init__(self, engine=None, get_connection=None):
        self.engine = engine or default_engine
        self._get_connection = get_connection or self.engine.connect

    def check_login(self, username, hashed_password):
        with self._get_connection() as conn:
            query = text("""
                SELECT u.id, u.username, r.name AS role, r.leaderboard_id
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.username=:username AND u.password=:password
            """)
            r = conn.execute(query, {
                "username": username,
                "password": hashed_password
            }).fetchone()
            fields = ("id", "username", "role", "leaderboard_id")
            return UserSession(**_row_dict(r, fields)) if r else None
