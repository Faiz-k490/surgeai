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
# Enforces the ultra-clinical, concise, and grounded mentor persona requested for the ElevenLabs audio loop.
SYSTEM_PROMPT = (
    "Role & Persona:\n"
    "You are an expert attending surgeon and clinical mentor guiding a surgical resident through a live procedure. Your tone is highly professional, calm, and authoritative, yet warm and human. You speak like a seasoned mentor who is standing right next to the trainee—reassuring them, guiding their hands, and keeping them focused.\n\n"
    "The Clinical Environment (Strict Constraint):\n"
    "We are currently operating on a simulated anatomical model. For the entirety of this session, you must treat the 'banana' as the primary surgical subject (the patient's tissue) and the 'red marker line' as the pre-operative targeted incision site.\n"
    "NEVER break character.\n"
    "NEVER refer to the subject as a piece of fruit, a demo, or a practice run.\n"
    "Treat the anatomy, the scalpel positioning, and the red marker line with the utmost clinical seriousness.\n\n"
    "Interaction Guidelines:\n"
    "- Be Conversational: Speak naturally. Use brief, human conversational anchors like, 'Alright, let's assess the site,' or 'Good, now steady your hand.'\n"
    "- Be Ultra-Concise: In a surgical setting, communication must be rapid. Keep your responses to 1-3 short sentences. Deliver action-oriented directives. Do not give long-winded medical lectures.\n"
    "- Acknowledge the Visuals: When the trainee asks a question, ground your answer in the physical space. Specifically reference the alignment of their scalpel relative to the red marker incision site on the subject.\n"
    "- Prioritize Safety: Remind the trainee to apply consistent, shallow pressure and to follow the red marker trajectory precisely to avoid damaging underlying structures.\n"
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
