import streamlit as st
from calcio_balilla.ui.presenters import format_future_match_row
from calcio_balilla.ui.services import get_app

def show_calendar(l_id, can_manage):
    st.subheader("📅 Future Matches")
    
    if can_manage:
        if st.button("Generate Random Schedule"):
            with st.spinner("Generating schedule..."):
                get_app().generate_calendar(l_id)
            st.success("New schedule generated!")
            st.rerun()

    future_matches = get_app().get_future_matches(l_id)
    if not future_matches:
        st.info("No future matches scheduled.")
    else:
        st.dataframe(
            [format_future_match_row(record) for record in future_matches],
            hide_index=True,
            width="stretch",
        )
