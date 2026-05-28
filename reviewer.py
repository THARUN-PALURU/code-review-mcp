# reviewer.py
# Talks to Groq and returns review text.
# Keep AI/LLM logic here — server.py shouldn't know or care which model we use.

import os
import logging
from groq import Groq
from dotenv import load_dotenv
from prompts import CODE_REVIEW, DIFF_REVIEW

load_dotenv()

log = logging.getLogger(__name__)

_client = None  # lazy-init — only connect when first needed. Don't crash at import time if key is missing — crash only when actually called

#Single place to handle missing key with a clear error
def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set in .env")
        _client = Groq(api_key=api_key)
    return _client


# llama-3.3-70b-versatile: best free model on groq as of 2025
MODEL = "llama-3.3-70b-versatile"


def review_code(code: str) -> str:
    if not code or not code.strip():
        return "No code provided."

    # Rough sanity check — avoid burning tokens on garbage input
    if len(code.strip()) < 5:
        return "Code too short to review meaningfully."

    log.info(f"Reviewing code snippet ({len(code)} chars)")
    return _call_llm(CODE_REVIEW.format(code=code))


def review_diff(diff: str) -> str:
    if not diff or not diff.strip():
        return "No diff provided."

    if not diff.startswith("diff --git") and "@@" not in diff:
        return "Input doesn't look like a valid git diff. Paste the raw output of `git diff`."

    log.info(f"Reviewing diff ({len(diff)} chars)")
    return _call_llm(DIFF_REVIEW.format(diff=diff))


def _call_llm(prompt: str) -> str:
    try:
        resp = _get_client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, # Lower = more consistent, less creative
            max_tokens=1024,
        )
        return resp.choices[0].message.content

    except RuntimeError as e:
        # Config problem — surface it clearly
        return f"Config error: {e}"

    except Exception as e:
        log.error(f"Groq call failed: {e}")
        return f"Review failed — Groq API error: {e}"