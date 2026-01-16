#!/usr/bin/env python3
import sys
from datetime import datetime
import streamlit as st
from sqlalchemy import text

from db import get_connection, init_db

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

# ---------------- STREAMLIT UI ----------------

def run_web_app():
    init_db()

    st.title("⚽ Calcio Balilla - Classifica Elo")

    st.sidebar.title("Azioni")
    action = st.sidebar.selectbox(
        "Scegli", ["Classifica", "Aggiungi Giocatore", "Nuova Partita"]
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

    elif action == "Aggiungi Giocatore":
        name = st.text_input("Nome giocatore")
        if st.button("Aggiungi"):
            api_add_player(name)
            st.success(f"Giocatore '{name}' aggiunto")
            st.rerun()

    elif action == "Nuova Partita":
        st.subheader("⚽ Nuova Partita 2vs2")

        col1, col2 = st.columns(2)
        with col1:
            a1 = st.text_input("Giocatore A1")
            a2 = st.text_input("Giocatore A2")
        with col2:
            b1 = st.text_input("Giocatore B1")
            b2 = st.text_input("Giocatore B2")

        goals_a = st.number_input("Gol Squadra A", min_value=0, value=10)
        goals_b = st.number_input("Gol Squadra B", min_value=0, value=8)

        if st.button("Salva Partita"):
            try:
                update_ratings_for_match(a1, a2, b1, b2, goals_a, goals_b)
                st.success("Partita salvata")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

if __name__ == "__main__":
    run_web_app()
