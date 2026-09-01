import streamlit as st

from calcio_balilla.ui.services import get_app


def show_manage_tournaments(leaderboard_id, leaderboard_name):
    st.subheader("🏆 Manage tournament")
    st.caption(f"Leaderboard: {leaderboard_name} (usa il selettore in alto per cambiarla)")
    players = get_app().get_player_names(leaderboard_id)
    name_to_id = {player.name: player.id for player in players}
    with st.form(f"create_tournament_{leaderboard_id}"):
        name = st.text_input("Nome torneo")
        selected = st.multiselect("Giocatori iscritti", list(name_to_id))
        submitted = st.form_submit_button("Crea torneo e genera bracket", type="primary")
    if submitted:
        try:
            get_app().create_tournament(leaderboard_id, name, [name_to_id[n] for n in selected])
            st.success("Torneo creato; il bracket è stato salvato.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    st.subheader("Tornei creati")
    tournaments = get_app().get_tournaments(leaderboard_id)
    if not tournaments:
        st.info("Nessun torneo disponibile.")
    else:
        st.dataframe([{"Nome": t.name, "Stato": t.status, "Season": t.season_id}
                      for t in tournaments], hide_index=True, use_container_width=True)


def _series_label(series):
    left = series.challenger1_name or "Da definire"
    right = series.challenger2_name or "Da definire"
    return f"{series.round_name} #{series.position + 1}: {left} {series.wins1}-{series.wins2} {right}"


def show_tournament(leaderboard_id):
    st.subheader("🏆 Tournament")
    season = get_app().get_active_season(leaderboard_id)
    tournaments = get_app().get_tournaments(leaderboard_id, season.id if season else None)
    if not tournaments:
        st.info("Nessun torneo associato alla season corrente.")
        return
    options = {f"{t.name} ({t.status})": t for t in tournaments}
    selected_label = st.selectbox("Torneo", list(options), key=f"tournament_{leaderboard_id}")
    tournament = options[selected_label]
    series_rows = get_app().get_tournament_series(tournament.id)

    rounds = {}
    for series in series_rows:
        rounds.setdefault((series.round_index, series.round_name), []).append(series)
    columns = st.columns(len(rounds))
    for column, ((_, round_name), rows) in zip(columns, sorted(rounds.items())):
        with column:
            st.markdown(f"#### {round_name}")
            for series in rows:
                winner = f"\n\n🏅 {series.winner_name}" if series.winner_name else ""
                st.markdown(
                    f"**{series.challenger1_name or '—'}** {series.wins1} – {series.wins2} "
                    f"**{series.challenger2_name or '—'}**  \n`{series.status}`{winner}"
                )
    if tournament.status == "completed":
        winner = next((s.winner_name for s in series_rows if s.is_final), None)
        st.success(f"Campione: {winner}")
        return

    active = [series for series in series_rows if series.status == "active"]
    if not active:
        st.info("Nessuna serie attiva.")
        return
    active_map = {_series_label(series): series for series in active}
    selected_series = active_map[st.selectbox("Serie attiva", list(active_map))]
    st.write(f"**{selected_series.challenger1_name}** vs **{selected_series.challenger2_name}** — "
             f"{selected_series.wins1}-{selected_series.wins2}")
    used_first, used_second = get_app().get_used_tournament_companions(
        selected_series.id, selected_series.challenger1_id, selected_series.challenger2_id
    )
    st.caption(f"Compagni già usati da {selected_series.challenger1_name}: "
               f"{', '.join(used_first) if used_first else 'nessuno'}")
    st.caption(f"Compagni già usati da {selected_series.challenger2_name}: "
               f"{', '.join(used_second) if used_second else 'nessuno'}")
    players = get_app().get_player_names(leaderboard_id)
    name_to_id = {player.name: player.id for player in players}
    present = st.multiselect("Giocatori presenti", list(name_to_id), key=f"present_{selected_series.id}")
    if st.button("Sorteggia compagni", type="primary"):
        try:
            first, second = get_app().draw_tournament_companions(
                selected_series.id, [name_to_id[name] for name in present]
            )
            id_to_name = {value: key for key, value in name_to_id.items()}
            st.success(f"{selected_series.challenger1_name} + {id_to_name[first]} vs "
                       f"{selected_series.challenger2_name} + {id_to_name[second]}")
        except ValueError as exc:
            st.error(str(exc))
