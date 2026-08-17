class StreamlitCacheManager:
    def __init__(self, cache_data_api):
        self.cache_data_api = cache_data_api

    def invalidate_all(self):
        self.cache_data_api.clear()
