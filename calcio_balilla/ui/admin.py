import streamlit as st
import pandas as pd
from calcio_balilla.ui.services import get_app
from calcio_balilla.ui.state import set_notes_dismissed

@st.dialog("🚀 What's New")
def show_release_notes(current_version: str):
    st.markdown(f"""
    ### Version {current_version} - Strategy & UI Overhaul
    This major update introduces advanced planning tools and a completely redesigned responsive interface.
    
    **New Features & Improvements**:
    1.  **Matchmaking**: Suggests balanced 2vs2 matches while rotating teammates and opponents.
    """)
    if st.button("Got it!"):
        set_notes_dismissed(True)
        st.rerun()

def show_manage_players(l_id, l_name):
    st.subheader("👥 Manage Players")
    with st.expander("➕ Add New Player"):
        name = st.text_input("Player Name")
        if st.button("Add Player"):
            if name:
                get_app().add_player(name, l_id)
                st.success(f"Added {name} to {l_name}!")
                st.rerun()
            else:
                st.error("Enter a name.")
    
    st.divider()
    st.write("Toggle Active Status")
    all_players = get_app().get_all_players(l_id)
    if all_players:
        df_p = pd.DataFrame([
            {"ID": p.id, "Name": p.name, "Active": p.is_active}
            for p in all_players
        ])
        edited = st.data_editor(
            df_p, 
            column_config={
                "ID": None, 
                "Name": st.column_config.TextColumn(disabled=True)
            }, 
            hide_index=True, 
            use_container_width=True
        )
        if not edited.equals(df_p):
            changed = edited[edited["Active"] != df_p["Active"]]
            for _, row in changed.iterrows():
                get_app().toggle_player_status(int(row["ID"]), bool(row["Active"]))
            st.success("Updated player status!")
            st.rerun()
