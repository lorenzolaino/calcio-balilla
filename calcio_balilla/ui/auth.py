import streamlit as st
from calcio_balilla.ui.services import get_app
from calcio_balilla.ui.state import set_guest_user, set_user

def show_login_page():
    # Center the login box
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.title("⚽ Calcio Balilla")
        st.markdown("Please log in or continue as a guest to view the dashboard.")
        
        with st.container(border=True):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Login", use_container_width=True, type="primary"):
                    user = get_app().check_login(username, password)
                    if user:
                        set_user({
                            "id": user.id,
                            "username": user.username,
                            "role": user.role,
                            "leaderboard_id": user.leaderboard_id
                        })
                        st.rerun()
                    else:
                        st.error("Login failed")
            with col2:
                if st.button("Continue as Guest", use_container_width=True):
                    set_guest_user()
                    st.rerun()
