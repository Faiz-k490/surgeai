class GuidanceSpeaker:
    def __init__(self, _settings):
        self.settings = _settings

    def speak(self, text: str) -> None:
        # TODO: Use ElevenLabs first; fallback to pyttsx3 on failure.
        _ = text
