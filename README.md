# ⚡ SurgeAI

**AI-Powered Content Surge Analyzer** — built for [VandyHacks XII](https://vandyhacks.org)

SurgeAI analyzes any text (news articles, social media posts, press releases) and instantly detects:

- **Surge Score** (0–100): How "hot" or trending is the content?
- **Sentiment**: Positive, Negative, or Neutral tone
- **Urgency Signals**: Words that indicate time-sensitive events
- **Top Keywords**: The dominant themes driving the surge
- **AI Summary**: A concise, AI-generated explanation of what's surging and why

---

## Demo

Paste any text → click **Analyze Surge** → get instant insights.

Try the built-in samples: 🚀 Tech Breakthrough · ₿ Crypto Rally · ⚠️ Market Crisis

---

## Tech Stack

| Layer     | Technology                        |
|-----------|-----------------------------------|
| Backend   | Python 3.11 · Flask               |
| AI        | OpenAI GPT-4o-mini (optional)     |
| Frontend  | HTML5 · Bootstrap 5 · Vanilla JS  |

---

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/Faiz-k490/surgeai.git
cd surgeai
pip install -r requirements.txt

# 2. (Optional) Add your OpenAI key for AI-powered summaries
echo "OPENAI_API_KEY=sk-..." > .env

# 3. Run
python app.py
# Open http://localhost:5000
```

### Environment Variables

| Variable         | Description                              | Required |
|------------------|------------------------------------------|----------|
| `OPENAI_API_KEY` | OpenAI key for GPT-4o-mini summaries     | No       |
| `SECRET_KEY`     | Flask secret key                         | No       |
| `PORT`           | Port to listen on (default: 5000)        | No       |
| `FLASK_DEBUG`    | Set to `true` to enable debug mode       | No       |

---

## How It Works

1. **Text is tokenized** into individual words
2. **Stop words are filtered** out (common words like "the", "and", etc.)
3. **Three signal categories** are scored:
   - *Positive signals*: words like "breakthrough", "record", "soaring"
   - *Negative signals*: words like "crash", "crisis", "collapse"
   - *Urgency signals*: words like "breaking", "urgent", "spike"
4. Scores are combined into a **Surge Score** (0–100)
5. If an OpenAI key is configured, **GPT-4o-mini generates** a concise summary
6. Top non-stop keywords are surfaced as a **keyword cloud**

---

## Project Structure

```
surgeai/
├── app.py              # Flask app + surge analysis logic
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Single-page UI
└── static/
    ├── css/style.css   # Custom dark-mode styles
    └── js/main.js      # Frontend logic & API calls
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

Built with ❤️ for **VandyHacks XII**
