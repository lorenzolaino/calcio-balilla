from sqlalchemy import text

from db import engine as default_engine


class TournamentRepository:
    def __init__(self, engine=None, get_connection=None):
        self.engine = engine or default_engine
        self._get_connection = get_connection or self.engine.connect

    def previous_ranking(self, conn, leaderboard_id):
        return [row[0] for row in conn.execute(text("""
            SELECT ps.player_id FROM player_stats ps
            JOIN seasons s ON s.id = ps.season_id
            WHERE s.leaderboard_id = :lid AND s.id = (
                SELECT id FROM seasons WHERE leaderboard_id=:lid AND is_active=FALSE
                AND closed_at IS NOT NULL ORDER BY number DESC LIMIT 1
            )
            ORDER BY ps.rating DESC, ps.wins DESC, ps.goal_diff DESC, ps.player_id
        """), {"lid": leaderboard_id}).fetchall()]

    def create(self, conn, leaderboard_id, season_id, name, participant_ids, specs):
        tournament_id = conn.execute(text("""
            INSERT INTO tournaments (leaderboard_id, season_id, name)
            VALUES (:lid, :sid, :name) RETURNING id
        """), {"lid": leaderboard_id, "sid": season_id, "name": name.strip()}).scalar()
        conn.execute(text("""
            INSERT INTO tournament_participants (tournament_id, player_id)
            VALUES (:tid, :pid)
        """), [{"tid": tournament_id, "pid": pid} for pid in participant_ids])
        ids = {}
        for spec in specs:
            ids[spec.key] = conn.execute(text("""
                INSERT INTO tournament_series
                    (tournament_id, round_index, round_name, position, challenger1_id,
                     challenger2_id, is_final, status)
                VALUES (:tid, :ri, :rn, :pos, :c1, :c2, :final,
                        CASE WHEN :c1 IS NOT NULL AND :c2 IS NOT NULL THEN 'active' ELSE 'pending' END)
                RETURNING id
            """), {"tid": tournament_id, "ri": spec.round_index, "rn": spec.round_name,
                     "pos": spec.position, "c1": spec.challenger1_id, "c2": spec.challenger2_id,
                     "final": spec.is_final}).scalar()
        for spec in specs:
            for slot, source in ((1, spec.source1_key), (2, spec.source2_key)):
                if source:
                    conn.execute(text("""
                        UPDATE tournament_series SET next_series_id=:next, next_slot=:slot WHERE id=:source
                    """), {"next": ids[spec.key], "slot": slot, "source": ids[source]})
        return tournament_id

    def list_tournaments(self, leaderboard_id, season_id=None):
        with self._get_connection() as conn:
            sql = """SELECT id, name, season_id, status, winner_id, created_at
                     FROM tournaments WHERE leaderboard_id=:lid"""
            params = {"lid": leaderboard_id}
            if season_id is not None:
                sql += " AND season_id=:sid"
                params["sid"] = season_id
            return conn.execute(text(sql + " ORDER BY created_at DESC, id DESC"), params).fetchall()

    def get_series(self, tournament_id, active_only=False):
        with self._get_connection() as conn:
            return self.get_series_with_conn(conn, tournament_id, active_only)

    def get_series_with_conn(self, conn, tournament_id, active_only=False):
        condition = " AND ts.status='active'" if active_only else ""
        return conn.execute(text("""
            SELECT ts.id, ts.tournament_id, ts.round_index, ts.round_name, ts.position,
                   ts.challenger1_id, p1.name challenger1_name, ts.challenger2_id,
                   p2.name challenger2_name, ts.is_final, ts.status, ts.winner_id,
                   pw.name winner_name, ts.next_series_id, ts.next_slot,
                   COUNT(m.id) FILTER (WHERE
                     (m.goals_a > m.goals_b AND (m.a1_id=ts.challenger1_id OR m.a2_id=ts.challenger1_id)) OR
                     (m.goals_b > m.goals_a AND (m.b1_id=ts.challenger1_id OR m.b2_id=ts.challenger1_id))) wins1,
                   COUNT(m.id) FILTER (WHERE
                     (m.goals_a > m.goals_b AND (m.a1_id=ts.challenger2_id OR m.a2_id=ts.challenger2_id)) OR
                     (m.goals_b > m.goals_a AND (m.b1_id=ts.challenger2_id OR m.b2_id=ts.challenger2_id))) wins2
            FROM tournament_series ts
            LEFT JOIN players p1 ON p1.id=ts.challenger1_id
            LEFT JOIN players p2 ON p2.id=ts.challenger2_id
            LEFT JOIN players pw ON pw.id=ts.winner_id
            LEFT JOIN matches m ON m.tournament_series_id=ts.id
            WHERE ts.tournament_id=:tid""" + condition + """
            GROUP BY ts.id,p1.name,p2.name,pw.name
            ORDER BY ts.round_index,ts.position
        """), {"tid": tournament_id}).fetchall()

    def lock_series(self, conn, series_id):
        return conn.execute(text("""
            SELECT ts.*, t.leaderboard_id, t.season_id FROM tournament_series ts
            JOIN tournaments t ON t.id=ts.tournament_id WHERE ts.id=:id FOR UPDATE
        """), {"id": series_id}).fetchone()

    def used_companions(self, conn, series_id, challenger1_id, challenger2_id):
        rows = conn.execute(text("""
            SELECT a1_id,a2_id,b1_id,b2_id FROM matches WHERE tournament_series_id=:id
        """), {"id": series_id}).fetchall()
        used1, used2 = set(), set()
        for row in rows:
            a, b = {row[0], row[1]}, {row[2], row[3]}
            used1.add(next(iter((a if challenger1_id in a else b) - {challenger1_id})))
            used2.add(next(iter((a if challenger2_id in a else b) - {challenger2_id})))
        return used1, used2

    def get_used_companions(self, series_id, challenger1_id, challenger2_id):
        with self._get_connection() as conn:
            used1, used2 = self.used_companions(conn, series_id, challenger1_id, challenger2_id)
            ids = used1 | used2
            if not ids:
                return [], []
            names = dict(conn.execute(text("SELECT id,name FROM players WHERE id IN :ids"),
                                      {"ids": tuple(ids)}).fetchall())
            return sorted(names[player_id] for player_id in used1), sorted(names[player_id] for player_id in used2)

    def complete_and_advance(self, conn, series, winner_id):
        conn.execute(text("UPDATE tournament_series SET status='completed',winner_id=:w WHERE id=:id"),
                     {"w": winner_id, "id": series.id})
        if series.next_series_id:
            column = "challenger1_id" if series.next_slot == 1 else "challenger2_id"
            conn.execute(text(f"UPDATE tournament_series SET {column}=:w WHERE id=:id"),
                         {"w": winner_id, "id": series.next_series_id})
            conn.execute(text("""
                UPDATE tournament_series SET status='active'
                WHERE id=:id AND challenger1_id IS NOT NULL AND challenger2_id IS NOT NULL
            """), {"id": series.next_series_id})
        else:
            conn.execute(text("UPDATE tournaments SET status='completed',winner_id=:w WHERE id=:id"),
                         {"w": winner_id, "id": series.tournament_id})

    def match_winners(self, conn, series_id, challenger1_id, challenger2_id):
        rows = conn.execute(text("""
            SELECT a1_id,a2_id,b1_id,b2_id,goals_a,goals_b FROM matches
            WHERE tournament_series_id=:id ORDER BY id
        """), {"id": series_id}).fetchall()
        winners = []
        for row in rows:
            winning_team = {row[0], row[1]} if row[4] > row[5] else {row[2], row[3]}
            winners.append(challenger1_id if challenger1_id in winning_team else challenger2_id)
        return winners
