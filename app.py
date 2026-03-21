"""
SurgeAI - AI-powered content surge analyzer
VandyHacks XII
"""

import html
import os
import re
from collections import Counter
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "surgeai-vandyhacks-xii")

# Optional OpenAI integration
try:
    from openai import OpenAI
    _openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    OPENAI_AVAILABLE = bool(os.environ.get("OPENAI_API_KEY"))
except ImportError:
    _openai_client = None
    OPENAI_AVAILABLE = False

# ----- Surge analysis helpers -----

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "not", "no", "nor",
    "so", "yet", "both", "either", "neither", "as", "if", "than", "that",
    "this", "these", "those", "it", "its", "he", "she", "they", "we",
    "you", "i", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "what", "which", "who", "whom", "when", "where", "why",
    "how", "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "up", "out", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "while", "although",
    "because", "since", "until", "unless", "also", "just", "very",
}

POSITIVE_WORDS = {
    "breakthrough", "amazing", "innovative", "revolutionary", "record",
    "success", "win", "winning", "growth", "surging", "soaring", "booming",
    "excellent", "outstanding", "remarkable", "impressive", "powerful",
    "strong", "leading", "advance", "progress", "rise", "rising",
    "increase", "skyrocket", "explode", "viral", "trending", "hot",
}

NEGATIVE_WORDS = {
    "crash", "fail", "failure", "crisis", "disaster", "collapse",
    "plunge", "drop", "decline", "fall", "falling", "threat", "danger",
    "risk", "problem", "issue", "concern", "worry", "fear", "loss",
    "losing", "shortage", "deficit", "ban", "block", "controversy",
}

URGENCY_WORDS = {
    "breaking", "urgent", "alert", "warning", "emergency", "immediate",
    "critical", "severe", "extreme", "rapid", "sudden", "unprecedented",
    "overnight", "skyrocket", "explosion", "surge", "spike", "jump",
    "soar", "flash", "now", "today", "just", "latest",
}


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    return re.findall(r"[a-z]+", text.lower())


def extract_keywords(text: str, top_n: int = 10) -> list[dict]:
    """Return the top N non-stopword words with their frequencies."""
    words = [w for w in tokenize(text) if w not in STOPWORDS and len(w) > 2]
    counts = Counter(words)
    total = sum(counts.values()) or 1
    return [
        {"word": word, "count": count, "pct": round(count / total * 100, 1)}
        for word, count in counts.most_common(top_n)
    ]


def compute_surge_score(text: str) -> dict:
    """Compute a surge score (0-100) with a breakdown."""
    words = tokenize(text)
    total = len(words) or 1

    pos_hits = [w for w in words if w in POSITIVE_WORDS]
    neg_hits = [w for w in words if w in NEGATIVE_WORDS]
    urgency_hits = [w for w in words if w in URGENCY_WORDS]

    pos_score = min(len(pos_hits) / total * 400, 35)
    neg_score = min(len(neg_hits) / total * 400, 30)
    urgency_score = min(len(urgency_hits) / total * 500, 35)

    raw = pos_score + neg_score + urgency_score
    score = round(min(raw, 100))

    if score >= 70:
        level = "🔴 High Surge"
        color = "danger"
    elif score >= 40:
        level = "🟡 Moderate Surge"
        color = "warning"
    else:
        level = "🟢 Low Surge"
        color = "success"

    sentiment = "Positive" if pos_score > neg_score else ("Negative" if neg_score > pos_score else "Neutral")

    return {
        "score": score,
        "level": level,
        "color": color,
        "sentiment": sentiment,
        "positive_hits": sorted(set(pos_hits)),
        "negative_hits": sorted(set(neg_hits)),
        "urgency_hits": sorted(set(urgency_hits)),
        "pos_score": round(pos_score),
        "neg_score": round(neg_score),
        "urgency_score": round(urgency_score),
    }


def get_ai_summary(text: str, surge: dict, keywords: list[dict]) -> str:
    """Call OpenAI for a 2-3 sentence summary; fall back to a template."""
    if OPENAI_AVAILABLE and _openai_client:
        try:
            kw_list = ", ".join(k["word"] for k in keywords[:5])
            prompt = (
                f"Analyze the following content for trending/surge signals.\n\n"
                f"Surge score: {surge['score']}/100 ({surge['level']})\n"
                f"Sentiment: {surge['sentiment']}\n"
                f"Top keywords: {kw_list}\n\n"
                f"Content snippet (first 600 chars):\n{text[:600]}\n\n"
                f"Write 2-3 concise sentences explaining what is surging, why, "
                f"and what it signals. Be direct and insightful."
            )
            response = _openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            pass

    # Template fallback — escape user-derived content to prevent XSS
    kw = html.escape(keywords[0]["word"].capitalize()) if keywords else "content"
    level = surge['level'].lower().replace('🔴 ', '').replace('🟡 ', '').replace('🟢 ', '')
    return (
        f"The analyzed content shows a surge score of {surge['score']}/100, "
        f"indicating {level} activity. "
        f"The dominant theme is centered around \"{kw}\" with a "
        f"{surge['sentiment'].lower()} overall sentiment. "
        f"{'Urgency signals detected suggest time-sensitive developments.' if surge['urgency_hits'] else 'No strong urgency signals were detected.'}"
    )


# ----- Routes -----

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "No text provided."}), 400
    if len(text) < 20:
        return jsonify({"error": "Please provide at least 20 characters of text."}), 400

    surge = compute_surge_score(text)
    keywords = extract_keywords(text)
    summary = get_ai_summary(text, surge, keywords)
    word_count = len(tokenize(text))

    return jsonify({
        "surge": surge,
        "keywords": keywords,
        "summary": summary,
        "word_count": word_count,
        "ai_powered": OPENAI_AVAILABLE,
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok", "ai_powered": OPENAI_AVAILABLE})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true", port=port)
