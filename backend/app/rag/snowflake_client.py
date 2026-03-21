from typing import Dict


class SnowflakeRAGClient:
    def __init__(self, _settings):
        self.settings = _settings

    def fetch_context(self, scene_summary: str, step_name: str) -> Dict[str, str]:
        # TODO: Implement Cortex.SEARCH query against procedure docs.
        return {
            "source": "stub",
            "context": f"Protocol context placeholder for step '{step_name}' and scene '{scene_summary}'.",
        }
