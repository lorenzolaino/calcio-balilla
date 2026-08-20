import hashlib
import secrets

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

    @staticmethod
    def _hash_session_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create_session(self, user_id=None) -> str:
        token = secrets.token_urlsafe(32)
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO auth_sessions (token_hash, user_id, is_guest, expires_at)
                VALUES (:token_hash, :user_id, :is_guest, NOW() + INTERVAL '7 days')
            """), {
                "token_hash": self._hash_session_token(token),
                "user_id": user_id,
                "is_guest": user_id is None,
            })
        return token

    def get_session_identity(self, token: str):
        with self._get_connection() as conn:
            row = conn.execute(text("""
                SELECT s.is_guest, u.id, u.username, r.name AS role, r.leaderboard_id
                FROM auth_sessions s
                LEFT JOIN users u ON s.user_id = u.id
                LEFT JOIN roles r ON u.role_id = r.id
                WHERE s.token_hash = :token_hash
                  AND s.expires_at > NOW()
            """), {"token_hash": self._hash_session_token(token)}).fetchone()

        if not row:
            return None

        data = _row_dict(row, ("is_guest", "id", "username", "role", "leaderboard_id"))
        if data["is_guest"]:
            return "guest"
        return UserSession(
            id=data["id"],
            username=data["username"],
            role=data["role"],
            leaderboard_id=data["leaderboard_id"],
        )

    def delete_session(self, token: str):
        with self.engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM auth_sessions WHERE token_hash = :token_hash
            """), {"token_hash": self._hash_session_token(token)})
