# Gemini VLM — free tier, models, tuning

## Best “free” path for this project

1. **Google AI Studio** — [aistudio.google.com](https://aistudio.google.com) — create an API key (no card required for the free tier; limits apply).
2. Put the key in **`backend/.env`** as **`GEMINI_API_KEY`**.
3. **Throttle VLM** — defaults are conservative (`VLM_MAX_HZ=0.2` ≈ one vision call / 5s). Raise only if you need snappier overlays.
4. If Gemini errors (429, quota), the backend **falls back** to color-based heuristics so the HUD still runs with weaker “VLM” — check logs for `Gemini rate limit`.

Official model list and quotas change over time — always check **[Gemini API models](https://ai.google.dev/gemini-api/docs/models)**.

## Which `GEMINI_MODEL` to use

Use a **model ID string** that your key supports on the **Gemini API** (AI Studio), not necessarily Vertex-only names.

Typical choices (verify on the docs page above):

| Tier | Examples (names change — confirm in docs) |
|------|----------------------------------------|
| Default in SurgeAI | **`gemini-2.5-flash`** (override with `GEMINI_MODEL`) |
| Alternatives | See [Gemini API models](https://ai.google.dev/gemini-api/docs/models) — Flash-Lite variants often cheaper |

**Defaults in code:** `GEMINI_MODEL` defaults to **`gemini-2.5-flash`** if unset.

On Gemini errors (rate limit, etc.), the backend **backs off** vision calls (`GEMINI_RATE_LIMIT_BACKOFF_SECONDS`) and **skips Groq + Snowflake** for that tick to save quota.

Avoid relying on undocumented preview IDs unless you confirmed them in AI Studio’s model picker.

## If you still hit limits

- Enable **billing** in Google Cloud / AI Studio for higher quotas (not “free,” but the real fix for heavy use).
- Reduce **`VLM_MAX_HZ`** and JPEG size via **`VLM_JPEG_QUALITY`**.
- Run **VLM-only** with **`LOOP_B_ENABLED=false`** to remove other API noise while debugging.
