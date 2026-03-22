"""
intelligence_pipeline.py — RAG retrieval + LLM generation for SurgeAI.

Architecture changes vs. previous version:
  - Groq client is a singleton (one HTTP connection, reused forever).
  - Snowflake connection is persistent (reconnects only on stale detection).
  - `retrieve_context` is explicitly marked synchronous and MUST be called via
    asyncio.to_thread() / run_in_executor — never directly from async code.
  - `stream_answer_tokens` is an async generator that yields Groq text tokens
    the moment they arrive, via an asyncio.Queue bridge so the event loop is
    never blocked by the synchronous Groq SDK iterator.
  - max_tokens reduced to 120, GROQ_TIMEOUT to 8 s.
  - System prompt enforces ≤30-word action-first directives.
"""

import asyncio
import logging
import os
from functools import lru_cache
from typing import AsyncIterator, Optional

import snowflake.connector
from groq import Groq
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("surgeai.intelligence")

# ── Constants ────────────────────────────────────────────────────────────────

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT = 8  # fail fast — a surgical assistant cannot wait 30 s

# Enforces extreme brevity: one sentence, action-first, ≤30 words.
# Verbose preamble ("Great question!") wastes TTS bandwidth and locks the
# audio channel while the attending is waiting for the critical directive.
SYSTEM_PROMPT = (
    "You are a surgical safety officer in an active operating room. "
    "Rules: (1) Answer in ONE sentence, ≤30 words. (2) Lead with the action. "
    "(3) No preamble, no filler words, no hedging. "
    "(4) Base your answer strictly on the protocol context provided. "
    "(5) If context is absent, say: 'Protocol unclear — verify with attending.' "
    "Format: <action verb> <object> [<critical caveat>]."
)

# ── Pydantic models ──────────────────────────────────────────────────────────


class QuestionInput(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)

    @field_validator("question")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question must not be blank.")
        return v


class PipelineResult(BaseModel):
    question: str
    context_chunks: list[str] = Field(default_factory=list)
    answer: str
    model: str = GROQ_MODEL
    error: Optional[str] = None


# ── Singleton clients ────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_groq_client() -> Groq:
    """One Groq HTTP client per process — amortises TLS handshake cost."""
    return Groq(api_key=os.environ["GROQ_API_KEY"], timeout=GROQ_TIMEOUT)


_snowflake_conn: Optional[snowflake.connector.SnowflakeConnection] = None


def _get_snowflake_connection() -> snowflake.connector.SnowflakeConnection:
    """
    Persistent Snowflake connection — reconnects only if stale.

    Opening a new connection costs ~300–600 ms (TLS + auth). Reusing one
    reduces per-question Snowflake overhead to ~10–50 ms round-trip.
    """
    global _snowflake_conn
    if _snowflake_conn is None or _snowflake_conn.is_closed():
        logger.info("Opening new Snowflake connection …")
        params: dict = dict(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            database=os.environ["SNOWFLAKE_DATABASE"],
            schema=os.environ["SNOWFLAKE_SCHEMA"],
            warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        )
        role = os.environ.get("SNOWFLAKE_ROLE")
        if role:
            params["role"] = role
        _snowflake_conn = snowflake.connector.connect(**params)
    return _snowflake_conn


# ── Snowflake RAG retrieval ──────────────────────────────────────────────────


def retrieve_context(question: str, top_k: int = 2) -> list[str]:
    """
    Synchronous Snowflake Cortex Search query.

    !! MUST be called via asyncio.to_thread() or loop.run_in_executor() !!
    Calling this directly in an async function blocks the entire event loop
    for the duration of the network round-trip (~200–800 ms).
    """
    query = """
        SELECT results
        FROM TABLE(
            SNOWFLAKE.CORTEX.SEARCH(
                service_name   => 'surgical_protocols_search',
                query_text     => %(question)s,
                num_results    => %(top_k)s
            )
        )
    """
    chunks: list[str] = []
    try:
        conn = _get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query, {"question": question, "top_k": top_k})
        for row in cur.fetchall():
            if row and row[0]:
                chunks.append(str(row[0]))
        cur.close()
    except snowflake.connector.errors.Error as exc:
        logger.error("Snowflake retrieval failed: %s", exc)
    except Exception as exc:
        logger.error("Unexpected RAG error: %s", exc)
    logger.info("Retrieved %d context chunk(s) from Snowflake.", len(chunks))
    return chunks


# ── Groq LLM streaming ───────────────────────────────────────────────────────


def _build_user_prompt(question: str, context_chunks: list[str]) -> str:
    if context_chunks:
        context_block = "\n---\n".join(context_chunks)
        return f"Protocol context:\n{context_block}\n\nQuestion: {question}"
    return f"No protocol context found.\n\nQuestion: {question}"


async def stream_answer_tokens(
    question: str,
    context_chunks: list[str],
    abort_event: asyncio.Event,
) -> AsyncIterator[str]:
    """
    Async generator that yields Groq text tokens the moment they arrive.

    The synchronous Groq SDK streaming iterator runs in a ThreadPoolExecutor
    thread. Each token is forwarded to the event loop via an asyncio.Queue so
    downstream consumers (ElevenLabs TTS, WebSocket broadcast) receive tokens
    without ever blocking the event loop.

    This is the key fix for the LLM-to-TTS handoff bottleneck: instead of
    waiting for the full response (~200-800 ms), ElevenLabs receives tokens
    starting at Groq's TTFT (~150-300 ms) and begins audio synthesis
    immediately.
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _stream_in_thread() -> None:
        try:
            stream = _get_groq_client().chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(question, context_chunks)},
                ],
                temperature=0.2,
                max_tokens=120,  # ≤30 words ≈ 40–80 tokens; 120 is a hard cap
                stream=True,
            )
            for chunk in stream:
                if abort_event.is_set():
                    logger.info("Abort: stopping Groq stream")
                    break
                delta = chunk.choices[0].delta.content
                if delta:
                    loop.call_soon_threadsafe(queue.put_nowait, delta)
        except Exception as exc:
            logger.error("Groq streaming error: %s", exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    thread_future = loop.run_in_executor(None, _stream_in_thread)

    try:
        while True:
            token = await queue.get()
            if token is None:
                break
            yield token
    finally:
        await thread_future


# ── Public entry point ───────────────────────────────────────────────────────


async def run_pipeline(raw_question: str) -> PipelineResult:
    """
    Non-streaming pipeline — backward-compatible wrapper.
    Internally uses stream_answer_tokens so all optimisations apply.
    """
    try:
        validated = QuestionInput(question=raw_question)
    except Exception as exc:
        logger.warning("Validation failed: %s", exc)
        return PipelineResult(question=raw_question, answer="", error=str(exc))

    question = validated.question

    # Snowflake is blocking — offload to thread pool so the event loop stays free
    try:
        context_chunks = await asyncio.to_thread(retrieve_context, question)
    except Exception as exc:
        logger.error("Context retrieval error: %s", exc)
        context_chunks = []

    abort = asyncio.Event()  # never set — consume the full stream
    tokens: list[str] = []
    try:
        async for token in stream_answer_tokens(question, context_chunks, abort):
            tokens.append(token)
    except Exception as exc:
        logger.error("LLM generation error: %s", exc)
        return PipelineResult(
            question=question,
            context_chunks=context_chunks,
            answer="",
            error=f"Generation error: {exc}",
        )

    return PipelineResult(
        question=question,
        context_chunks=context_chunks,
        answer="".join(tokens),
    )


# ── Synchronous compatibility shim ───────────────────────────────────────────


def generate_answer(question: str, context_chunks: Optional[list] = None) -> str:
    """Synchronous wrapper for loop_a_service and other non-async callers.

    Runs the full RAG + LLM pipeline in a blocking call.  Do NOT call this
    from inside an async function — use run_pipeline() instead.
    """
    chunks = context_chunks if context_chunks is not None else retrieve_context(question)
    prompt = _build_user_prompt(question, chunks)
    try:
        response = _get_groq_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=120,
            stream=False,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("generate_answer error: %s", exc)
        return ""
