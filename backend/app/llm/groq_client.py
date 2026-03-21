from groq import Groq


class GroqGuidanceClient:
    def __init__(self, settings):
        self.settings = settings
        self.client = Groq(api_key=settings.groq_api_key)

    def ping(self) -> bool:
        try:
            _ = self.client
            return True
        except Exception:
            return False

    def generate_guidance(self, scene_summary: str, context: str, step_name: str) -> str:
        prompt = (
            "You are a concise surgical training co-pilot. "
            "Use the grounded protocol context and provide a short safe instruction.\n\n"
            f"Step: {step_name}\n"
            f"Scene: {scene_summary}\n"
            f"Protocol context: {context}\n"
        )
        try:
            completion = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=120,
            )
            return completion.choices[0].message.content.strip()
        except Exception:
            return f"{step_name}: proceed carefully. {context[:140]}"
