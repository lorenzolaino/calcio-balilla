#!/usr/bin/env python3
import sys
from datetime import datetime
import streamlit as st
from sqlalchemy import text
import pandas as pd
import altair as alt
from db import get_connection, init_db
import hashlib

K_FACTOR = 20.0

# ---------------- API ----------------

def api_classifica():
    with get_connection() as conn:
        res = conn.execute(text("""
            SELECT name, rating, games, wins, losses, goal_diff
            FROM players
            ORDER BY rating DESC
        """))
        return res.fetchall()

def api_add_player(name):
    with get_connection() as conn:
        conn.execute(text("""
            INSERT INTO players (name, rating, games, wins, losses, goal_diff)
            VALUES (:name, 1000, 0, 0, 0, 0)
            ON CONFLICT (name) DO NOTHING
        """), {"name": name})

def api_storico_partite(limit=50):
    with get_connection() as conn:
        res = conn.execute(text("""
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
        """), {"limit": limit})

        return res.fetchall()

def api_elo_history_all():
    with get_connection() as conn:
        return pd.read_sql("""
            SELECT
                h.created_at,
                p.name AS player,
                h.rating
            FROM player_ratings_history h
            JOIN players p ON h.player_id = p.id
            ORDER BY h.created_at
        """, conn)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(username, password):
    with get_connection() as conn:
        row = conn.execute(text("""
            SELECT u.id, u.username, r.name AS role
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.username=:username AND u.password=:password
        """), {
            "username": username,
            "password": hash_password(password)
        }).fetchone()
        return row 

# ---------------- DB HELPERS ----------------

def get_or_create_player(conn, name):
    row = conn.execute(text("""
        SELECT id, rating, games, wins, losses, goal_diff
        FROM players WHERE name = :name
    """), {"name": name}).fetchone()

    if row:
        return row

    conn.execute(text("""
        INSERT INTO players (name, rating, games, wins, losses, goal_diff)
        VALUES (:name, 1000, 0, 0, 0, 0)
    """), {"name": name})

    return conn.execute(text("""
        SELECT id, rating, games, wins, losses, goal_diff
        FROM players WHERE name = :name
    """), {"name": name}).fetchone()

def save_rating_history(conn, player_id, match_id, rating):
    conn.execute(text("""
        INSERT INTO player_ratings_history (player_id, match_id, rating)
        VALUES (:pid, :mid, :rating)
    """), {
        "pid": player_id,
        "mid": match_id,
        "rating": int(rating)
    })

# ---------------- ELO LOGIC ----------------

def expected_score(r_team, r_opp):
    return 1.0 / (1.0 + 10 ** ((r_opp - r_team) / 400.0))

def margin_multiplier(margin):
    if margin <= 2:
        return 1.0
    elif margin == 3:
        return 1.1
    elif margin == 4:
        return 1.2
    elif margin == 5:
        return 1.3
    elif margin == 6:
        return 1.4
    elif margin == 7:
        return 1.5
    elif margin == 8:
        return 1.6
    elif margin == 9:
        return 1.7
    else:
        return 1.8

def update_ratings_for_match(a1_name, a2_name, b1_name, b2_name, goals_a, goals_b):
    if goals_a == goals_b:
        raise ValueError("Non sono previsti pareggi.")
    margin = abs(goals_a - goals_b)
    if margin < 2:
        raise ValueError("Scarto minimo 2 gol.")

    with get_connection() as conn:
        a1 = get_or_create_player(conn, a1_name)
        a2 = get_or_create_player(conn, a2_name)
        b1 = get_or_create_player(conn, b1_name)
        b2 = get_or_create_player(conn, b2_name)

        a1_id, a1_rating, a1_games, a1_wins, a1_losses, a1_gd = a1
        a2_id, a2_rating, a2_games, a2_wins, a2_losses, a2_gd = a2
        b1_id, b1_rating, b1_games, b1_wins, b1_losses, b1_gd = b1
        b2_id, b2_rating, b2_games, b2_wins, b2_losses, b2_gd = b2

        r_a = (a1_rating + a2_rating) / 2.0
        r_b = (b1_rating + b2_rating) / 2.0

        e_a = expected_score(r_a, r_b)
        e_b = expected_score(r_b, r_a)

        s_a = 1.0 if goals_a > goals_b else 0.0
        s_b = 1.0 - s_a

        m = margin_multiplier(margin)

        delta_a = round(K_FACTOR * m * (s_a - e_a))
        delta_b = round(K_FACTOR * m * (s_b - e_b))

        new_a1_rating = a1_rating + delta_a
        new_a2_rating = a2_rating + delta_a
        new_b1_rating = b1_rating + delta_b
        new_b2_rating = b2_rating + delta_b

        a1_games += 1
        a2_games += 1
        b1_games += 1
        b2_games += 1

        if s_a == 1:
            a1_wins += 1
            a2_wins += 1
            b1_losses += 1
            b2_losses += 1
        else:
            b1_wins += 1
            b2_wins += 1
            a1_losses += 1
            a2_losses += 1

        gd_a = goals_a - goals_b
        gd_b = goals_b - goals_a

        a1_gd += gd_a
        a2_gd += gd_a
        b1_gd += gd_b
        b2_gd += gd_b

        for pid, rating, games, wins, losses, gd in [
            (a1_id, new_a1_rating, a1_games, a1_wins, a1_losses, a1_gd),
            (a2_id, new_a2_rating, a2_games, a2_wins, a2_losses, a2_gd),
            (b1_id, new_b1_rating, b1_games, b1_wins, b1_losses, b1_gd),
            (b2_id, new_b2_rating, b2_games, b2_wins, b2_losses, b2_gd),
        ]:
            conn.execute(text("""
                UPDATE players
                SET rating=:r, games=:g, wins=:w, losses=:l, goal_diff=:gd
                WHERE id=:id
            """), {"r": rating, "g": games, "w": wins, "l": losses, "gd": gd, "id": pid})

        conn.execute(text("""
            INSERT INTO matches
            (date, a1_id, a2_id, b1_id, b2_id, goals_a, goals_b, delta_a, delta_b)
            VALUES (:d, :a1, :a2, :b1, :b2, :ga, :gb, :da, :db)
        """), {
            "d": datetime.now(),
            "a1": a1_id, "a2": a2_id,
            "b1": b1_id, "b2": b2_id,
            "ga": goals_a, "gb": goals_b,
            "da": delta_a, "db": delta_b
        })

        match_id = conn.execute(text("SELECT currval('matches_id_seq')")).scalar()

        save_rating_history(conn, a1_id, match_id, new_a1_rating)
        save_rating_history(conn, a2_id, match_id, new_a2_rating)
        save_rating_history(conn, b1_id, match_id, new_b1_rating)
        save_rating_history(conn, b2_id, match_id, new_b2_rating)


# ---------------- STREAMLIT UI ----------------

def run_web_app():
    init_db()

    # --- Login / Logout ---
    if 'user' not in st.session_state:
        st.session_state['user'] = None

    st.sidebar.title("Account")

    if st.session_state['user'] is None:
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            user = check_login(username, password)
            if user:
                st.session_state['user'] = {"id": user[0], "username": user[1], "role": user[2]}
                st.success(f"Benvenuto {user[1]}!")
            else:
                st.error("Login fallito")
    else:
        st.sidebar.write(f"Logged in as {st.session_state['user']['username']} ({st.session_state['user']['role']})")
        if st.sidebar.button("Logout"):
            st.session_state['user'] = None
            st.experimental_rerun()

    st.title("⚽ Calcio Balilla - Classifica Elo")

    st.sidebar.title("Azioni")
    action = st.sidebar.selectbox(
        "Scegli", ["Classifica", "Storico Partite", "Andamento Elo", "Aggiungi Giocatore", "Nuova Partita"]
    )

    if action == "Classifica":
        rows = api_classifica()
        st.subheader("🏆 Classifica")
        st.table([
            {
                "Pos": i + 1,
                "Giocatore": r[0],
                "Rating": int(r[1]),
                "Partite": r[2],
                "V": r[3],
                "S": r[4],
                "DG": r[5]
            }
            for i, r in enumerate(rows)
        ])

    elif action == "Storico Partite":
        st.subheader("📜 Storico Partite")
        limit = st.slider("Numero di partite da mostrare", 5, 100, 20)
        rows = api_storico_partite(limit)

        if not rows:
            st.info("Nessuna partita registrata.")
        else:
            st.table([
                {
                    "Data": r[0].strftime("%d/%m/%Y %H:%M"),
                    "Squadra A": f"{r[1]} + {r[2]}",
                    "Risultato": f"{r[5]} - {r[6]}",
                    "Squadra B": f"{r[3]} + {r[4]}",
                    "Δ Elo A": r[7],
                    "Δ Elo B": r[8],
                }
                for r in rows
            ])
    
    elif action == "Andamento Elo":
        st.subheader("📈 Andamento Elo giocatori")
        df = api_elo_history_all()

        if df.empty:
            st.info("Nessun dato storico disponibile.")
        else:
            chart = alt.Chart(df).mark_line(point=True).encode(
                x=alt.X("created_at:T", title="Data"),
                y=alt.Y("rating:Q", title="Rating Elo"),
                color=alt.Color("player:N", title="Giocatore"),
                tooltip=["player", "rating", "created_at"]
            ).properties(height=500)

            st.altair_chart(chart, use_container_width=True)

    elif action == "Aggiungi Giocatore":
        if st.session_state['user'] is None or st.session_state['user']['role'] != 'user':
            st.warning("Devi essere loggato per aggiungere giocatori")
        else:
            name = st.text_input("Nome giocatore")
            if st.button("Aggiungi"):
                api_add_player(name)
                st.success(f"Giocatore '{name}' aggiunto")
                st.rerun()

    elif action == "Nuova Partita":
        if st.session_state['user'] is None or st.session_state['user']['role'] != 'user':
            st.warning("Devi essere loggato per inserire partite")
        else:
            st.subheader("⚽ Inserisci Partita 2vs2")
            col1, col2 = st.columns(2)
            with col1:
                a1 = st.text_input("Giocatore 1 Squadra A")
                a2 = st.text_input("Giocatore 2 Squadra A")
            with col2:
                b1 = st.text_input("Giocatore 1 Squadra B")
                b2 = st.text_input("Giocatore 2 Squadra B")

            col3, col4 = st.columns(2)
            with col3:
                goals_a = st.number_input("Gol Squadra A", min_value=0, value=10)
            with col4:
                goals_b = st.number_input("Gol Squadra B", min_value=0, value=8)

            if st.button("Salva Partita"):
                try:
                    update_ratings_for_match(a1, a2, b1, b2, goals_a, goals_b)
                    st.success("✅ Partita salvata! Classifica aggiornata.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

if __name__ == "__main__":
    run_web_app()
