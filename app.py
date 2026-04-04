#!/usr/bin/env python3
import streamlit as st
import altair as alt
from db import init_db
from models import DatabaseManager

def run_web_app():
    # Initialize database tables
    init_db()

    # --- Session State / Auth ---
    if 'user' not in st.session_state:
        st.session_state['user'] = None

    st.sidebar.title("Account")

    if st.session_state['user'] is None:
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            user = DatabaseManager.check_login(username, password)
            if user:
                st.session_state['user'] = {
                    "id": user[0], 
                    "username": user[1], 
                    "role": user[2]
                }
                st.success(f"Benvenuto {user[1]}!")
                st.rerun()
            else:
                st.error("Login fallito")
    else:
        st.sidebar.write(
            f"Logged in as {st.session_state['user']['username']} "
            f"({st.session_state['user']['role']})"
        )
        if st.sidebar.button("Logout"):
            st.session_state['user'] = None
            st.rerun()

    st.title("⚽ Calcio Balilla - Classifica Elo")

    # --- Sidebar Navigation (Labels kept in Italian) ---
    st.sidebar.title("Azioni")
    action = st.sidebar.selectbox(
        "Scegli", 
        ["Classifica", "Storico Partite", "Andamento Elo", "Aggiungi Giocatore", "Nuova Partita"]
    )

    if action == "Classifica":
        st.subheader("🏆 Classifica")
        leaderboard_data = DatabaseManager.get_leaderboard()
        
        st.dataframe([
            {
                "Pos": index + 1,
                "Giocatore": player[0],
                "Rating": int(player[1]),
                "Partite": player[2],
                "V": player[3],
                "S": player[4],
                "DG": player[5],
                "% Win": (player[3] / player[2] * 100) if player[2] > 0 else 0.0
            }
            for index, player in enumerate(leaderboard_data)
        ], hide_index=True, column_config={
            "% Win": st.column_config.NumberColumn(format="%.1f%%")
        })

    elif action == "Storico Partite":
        st.subheader("📜 Storico Partite")
        limit = st.slider("Numero di partite da mostrare", 5, 100, 20)
        history_data = DatabaseManager.get_match_history(limit)

        if not history_data:
            st.info("Nessuna partita registrata.")
        else:
            st.table([
                {
                    "Data": record[0].strftime("%d/%m/%Y %H:%M"),
                    "Squadra A": f"{record[1]} + {record[2]}",
                    "Risultato": f"{record[5]} - {record[6]}",
                    "Squadra B": f"{record[3]} + {record[4]}",
                    "Δ Elo A": record[7],
                    "Δ Elo B": record[8],
                }
                for record in history_data
            ])
    
    elif action == "Andamento Elo":
        st.subheader("📈 Andamento Elo giocatori")
        df_history = DatabaseManager.get_elo_history()

        if df_history.empty:
            st.info("Nessun dato storico disponibile.")
        else:
            selection = alt.selection_point(
                fields=["player"],
                bind="legend",
                toggle=True
            )
            
            chart = alt.Chart(df_history).mark_line(point=True).encode(
                x=alt.X("created_at:T", title="Data"),
                y=alt.Y(
                    "rating:Q", 
                    scale=alt.Scale(zero=False), 
                    title="Rating Elo"
                ),
                color=alt.Color("player:N", title="Giocatore"),
                opacity=alt.condition(
                    selection,
                    alt.value(1.0),
                    alt.value(0.05)
                ),
                tooltip=["player", "rating", "created_at"]
            ).add_params(selection).properties(height=500)

            st.altair_chart(chart, use_container_width=True)

    elif action == "Aggiungi Giocatore":
        if st.session_state['user'] is None or st.session_state['user']['role'] != 'user':
            st.warning("Devi essere loggato per aggiungere giocatori")
        else:
            player_name = st.text_input("Nome giocatore")
            if st.button("Aggiungi"):
                DatabaseManager.add_player(player_name)
                st.success(f"Giocatore '{player_name}' aggiunto")
                st.rerun()

    elif action == "Nuova Partita":
        if st.session_state['user'] is None or st.session_state['user']['role'] != 'user':
            st.warning("Devi essere loggato per inserire partite")
        else:
            st.subheader("⚽ Inserisci Partita 2vs2")
            players_list = DatabaseManager.get_player_names()
            if len(players_list) < 4:
                st.warning("Servono almeno 4 giocatori per inserire una partita.")
                st.stop()
                
            col1, col2 = st.columns(2)
            with col1:
                a1 = st.selectbox("Giocatore 1 Squadra A", players_list, key="a1")
                a2 = st.selectbox("Giocatore 2 Squadra A", players_list, key="a2")
            with col2:
                b1 = st.selectbox("Giocatore 1 Squadra B", players_list, key="b1")
                b2 = st.selectbox("Giocatore 2 Squadra B", players_list, key="b2")

            col3, col4 = st.columns(2)
            with col3:
                score_a = st.number_input("Gol Squadra A", min_value=0, value=10)
            with col4:
                score_b = st.number_input("Gol Squadra B", min_value=0, value=8)

            selected_players = {a1, a2, b1, b2}
            if len(selected_players) < 4:
                st.error("Ogni giocatore può comparire una sola volta nella partita.")
                st.stop()

            if st.button("Salva Partita"):
                try:
                    DatabaseManager.record_match(a1, a2, b1, b2, score_a, score_b)
                    st.success("✅ Partita salvata! Classifica aggiornata.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

if __name__ == "__main__":
    run_web_app()
