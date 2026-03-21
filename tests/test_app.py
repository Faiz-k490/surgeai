"""Tests for SurgeAI – VandyHacks XII"""

import pytest
from app import app, tokenize, extract_keywords, compute_surge_score, get_ai_summary


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---- Unit tests ----

class TestTokenize:
    def test_basic(self):
        assert tokenize("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self):
        assert tokenize("it's breaking!") == ["it", "s", "breaking"]

    def test_empty(self):
        assert tokenize("") == []

    def test_alpha_only(self):
        result = tokenize("price $100k")
        assert "100" not in result


class TestExtractKeywords:
    def test_returns_list(self):
        kw = extract_keywords("the quick brown fox jumps over the lazy dog")
        assert isinstance(kw, list)

    def test_stopwords_filtered(self):
        kw = extract_keywords("the the the fox fox fox")
        words = [k["word"] for k in kw]
        assert "the" not in words
        assert "fox" in words

    def test_top_n(self):
        text = "alpha beta gamma delta epsilon zeta eta theta"
        kw = extract_keywords(text, top_n=3)
        assert len(kw) <= 3

    def test_pct_sum(self):
        kw = extract_keywords("surge surge trend trend breaking breaking")
        total_pct = sum(k["pct"] for k in kw)
        assert abs(total_pct - 100.0) < 1.0


class TestComputeSurgeScore:
    def test_score_range(self):
        texts = [
            "hello world, nothing special here at all today",
            "BREAKING: Unprecedented surge! Markets soaring to record highs overnight!",
            "The company reported a minor decline in quarterly results.",
        ]
        for text in texts:
            result = compute_surge_score(text)
            assert 0 <= result["score"] <= 100

    def test_high_surge_text(self):
        text = (
            "Breaking urgent: Bitcoin surges to unprecedented record, skyrocketing "
            "overnight with extreme soaring growth. Viral breakthrough alert!"
        )
        result = compute_surge_score(text)
        assert result["score"] >= 50

    def test_low_surge_text(self):
        text = "The committee met on Tuesday to discuss the annual budget review."
        result = compute_surge_score(text)
        assert result["score"] < 50

    def test_level_field_present(self):
        result = compute_surge_score("hello world")
        assert "level" in result
        assert "color" in result
        assert "sentiment" in result

    def test_color_matches_level(self):
        high_text = (
            "Breaking: extreme urgent surge crash failure crisis record "
            "collapse soaring skyrocket viral unprecedented"
        )
        result = compute_surge_score(high_text)
        if result["score"] >= 70:
            assert result["color"] == "danger"
        elif result["score"] >= 40:
            assert result["color"] == "warning"
        else:
            assert result["color"] == "success"

    def test_positive_sentiment(self):
        text = "Breakthrough amazing success win outstanding record growth surge"
        result = compute_surge_score(text)
        assert result["sentiment"] == "Positive"

    def test_negative_sentiment(self):
        text = "crash collapse failure crisis disaster decline fall loss problem"
        result = compute_surge_score(text)
        assert result["sentiment"] == "Negative"


class TestGetAiSummary:
    def test_returns_string(self):
        surge = compute_surge_score("surge breaking record")
        kw = extract_keywords("surge breaking record")
        summary = get_ai_summary("surge breaking record", surge, kw)
        assert isinstance(summary, str)
        assert len(summary) > 0


# ---- API / route tests ----

class TestIndexRoute:
    def test_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_contains_surgeai(self, client):
        r = client.get("/")
        assert b"SurgeAI" in r.data


class TestHealthRoute:
    def test_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "ok"
        assert "ai_powered" in data


class TestAnalyzeRoute:
    def test_valid_text(self, client):
        r = client.post("/analyze", json={
            "text": "Breaking: markets are surging to unprecedented record highs overnight with extreme growth"
        })
        assert r.status_code == 200
        data = r.get_json()
        assert "surge" in data
        assert "keywords" in data
        assert "summary" in data
        assert "word_count" in data
        assert 0 <= data["surge"]["score"] <= 100

    def test_empty_text(self, client):
        r = client.post("/analyze", json={"text": ""})
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_short_text(self, client):
        r = client.post("/analyze", json={"text": "too short"})
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_no_body(self, client):
        r = client.post("/analyze")
        assert r.status_code == 400

    def test_word_count(self, client):
        text = "The stock market is surging rapidly with record breaking gains across all sectors"
        r = client.post("/analyze", json={"text": text})
        data = r.get_json()
        assert data["word_count"] > 0

    def test_keywords_structure(self, client):
        r = client.post("/analyze", json={
            "text": "Surge surge surge trend trend breaking breaking records records records"
        })
        data = r.get_json()
        for kw in data["keywords"]:
            assert "word" in kw
            assert "count" in kw
            assert "pct" in kw
