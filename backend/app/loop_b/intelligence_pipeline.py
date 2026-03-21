"""
intelligence_pipeline.py — RAG retrieval + LLM generation for SurgeAI.

1. Retrieves relevant surgical-protocol context from Snowflake Cortex Search.
2. Sends the context + question to Snowflake Cortex COMPLETE() for a grounded answer.
"""

import logging
import os
from typing import Optional

import snowflake.connector
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("surgeai.intelligence")

CORTEX_MODEL = os.getenv("CORTEX_MODEL", "mistral-large")

SYSTEM_PROMPT = (
    "You are a senior surgical attending providing rapid, precise guidance to "
    "a resident in the operating room. Speak in clear, natural clinical "
    "language. Base your answer strictly on the provided protocol context. "
    "If the context does not contain enough information, say so honestly. "
    "Keep your response concise—ideally under 100 words—so it can be read "
    "aloud quickly during a procedure."
)


class QuestionInput(BaseModel):
    """Validates the incoming transcribed question."""

    question: str = Field(..., min_length=3, max_length=2000)

    @field_validator("question")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question must not be blank.")
        return v


class PipelineResult(BaseModel):
    """Structured output from the intelligence pipeline."""

    question: str
    context_chunks: list[str] = Field(default_factory=list)
    answer: str
    model: str = CORTEX_MODEL
    error: Optional[str] = None


def _get_snowflake_connection() -> snowflake.connector.SnowflakeConnection:
    """Create a Snowflake connection from environment variables."""
    params = dict(
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
    return snowflake.connector.connect(**params)


def retrieve_context(question: str, top_k: int = 3) -> list[str]:
    """
    Query Snowflake Cortex Search for the most relevant surgical-protocol
    paragraphs.  Returns up to `top_k` text chunks.
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
        try:
            cur = conn.cursor()
            cur.execute(query, {"question": question, "top_k": top_k})
            for row in cur.fetchall():
                if row and row[0]:
                    chunks.append(str(row[0]))
        finally:
            conn.close()
    except snowflake.connector.errors.Error as exc:
        logger.error("Snowflake retrieval failed: %s", exc)
    except Exception as exc:
        logger.error("Unexpected error during RAG retrieval: %s", exc)

    logger.info("Retrieved %d context chunk(s) from Snowflake.", len(chunks))
    return chunks


def _build_user_prompt(question: str, context_chunks: list[str]) -> str:
    """Construct the user-facing prompt with injected context."""
    if context_chunks:
        context_block = "\n\n---\n\n".join(context_chunks)
        return (
            f"**Relevant Protocol Context:**\n{context_block}\n\n"
            f"**Resident's Question:**\n{question}"
        )
    return (
        "No protocol context was found for this question. "
        "Answer from general surgical knowledge if possible.\n\n"
        f"**Resident's Question:**\n{question}"
    )


def generate_answer(question: str, context_chunks: list[str]) -> str:
    """
    Send the context-augmented prompt to Snowflake Cortex COMPLETE() and
    return the generated clinical answer.
    """
    user_prompt = _build_user_prompt(question, context_chunks)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    try:
        conn = _get_snowflake_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
                (CORTEX_MODEL, full_prompt),
            )
            row = cur.fetchone()
            cur.close()
            if row and row[0]:
                answer = str(row[0]).strip()
                logger.info("Cortex generation complete (%s).", CORTEX_MODEL)
                return answer
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Cortex COMPLETE() failed in Loop B: %s", exc)

    return "I'm unable to generate an answer right now. Please try again."


async def run_pipeline(raw_question: str) -> PipelineResult:
    """
    Full RAG + generation pipeline.

    1. Validate the incoming question via Pydantic.
    2. Retrieve context from Snowflake Cortex Search.
    3. Generate an answer with Snowflake Cortex COMPLETE().
    4. Return a structured PipelineResult.
    """
    try:
        validated = QuestionInput(question=raw_question)
    except Exception as exc:
        logger.warning("Validation failed: %s", exc)
        return PipelineResult(
            question=raw_question,
            answer="",
            error=f"Validation error: {exc}",
        )

    question = validated.question

    try:
        context_chunks = retrieve_context(question)
    except Exception as exc:
        logger.error("Context retrieval error: %s", exc)
        context_chunks = []

    try:
        answer = generate_answer(question, context_chunks)
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
        answer=answer,
    )
