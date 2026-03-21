class GroqGuidanceClient:
    def __init__(self, _settings):
        self.settings = _settings

    def generate_guidance(self, scene_summary: str, context: str, step_name: str) -> str:
        # TODO: Implement Groq completion call with grounded context.
        return f"[Stub] {step_name}: {scene_summary}. Context: {context[:120]}"
