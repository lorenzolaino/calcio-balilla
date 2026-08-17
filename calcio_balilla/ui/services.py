import streamlit as st

from calcio_balilla.app_facade import ApplicationFacade
from calcio_balilla.cache import StreamlitCacheManager
from db import engine, get_connection


def get_app() -> ApplicationFacade:
    return ApplicationFacade(
        engine=engine,
        get_connection=get_connection,
        cache_manager=StreamlitCacheManager(st.cache_data),
    )
