#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hybrid query preparation before RAG: strip greetings, optional LLM normalize, typo pass."""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Literal, Optional

logger = logging.getLogger(__name__)

RAG_QUERY_LLM_PREP = os.getenv("RAG_QUERY_LLM_PREP", "true").lower() == "true"

PrepSource = Literal["none", "rules", "llm"]

_CONV_PREFIX_EN = re.compile(
    r"^\s*(?:"
    r"hello+|hi+|hey+|howdy|greetings|"
    r"good\s+(?:morning|afternoon|evening)|"
    r"thanks+(?:\s+you)?|thank\s+you+|thx|"
    r"ok+(?:ay+)?(?:\s+so)?|so|well|now|actually|alright|right|hmm|"
    r"i\s+mean|i\s+wanted\s+to\s+ask|"
    r"can\s+you\s+(?:please\s+)?tell\s+me|please\s+tell\s+me|tell\s+me|"
    r"could\s+you\s+(?:please\s+)?tell\s+me|"
    r"please|just|also|by\s+the\s+way"
    r")\b[\s,!.?]*",
    re.IGNORECASE,
)

_CONV_PREFIX_AR = re.compile(
    r"^\s*(?:"
    r"اهلا|أهلا|مرحبا|مرحباً|السلام\s+عليكم|"
    r"صباح\s+الخير|مساء\s+الخير|هلا|"
    r"شكرا|شكراً|تسلم|تسلمي|متشكر|متشكره|"
    r"طيب|تمام|ماشي|حاضر|اوكي|اوك|"
    r"يعني|بس|لو\s+سمحت|من\s+فضلك"
    r")[\s,!.?]*",
    re.IGNORECASE,
)

_MID_CONVERSATIONAL = re.compile(
    r"\b(?:hello|hi|hey|thanks|thank\s+you|also|by\s+the\s+way|ok(?:ay)?)\b",
    re.IGNORECASE,
)

# Leading question / request framing to remove before KB search. Document-agnostic:
# strips interrogative wrappers while preserving entity names and attributes.
_QUESTION_OPENER_EN = re.compile(
    r"^\s*(?:"
    r"(?:what|which|who|when|where)(?:'s|\s+is|\s+are)(?:\s+the|\s+a|\s+an)?\s+|"
    r"(?:how)(?:'s|\s+is|\s+are|\s+much|\s+many|\s+long|\s+often|\s+does|\s+do|\s+did|\s+can)?(?:\s+the|\s+a|\s+an)?\s+|"
    r"why(?:'s|\s+is|\s+are|\s+did|\s+does|\s+do|\s+might(?:\s+there\s+be|\s+it\s+be)?|\s+would|\s+could)?\s+|"
    r"(?:can|could)\s+you(?:\s+please)?\s+(?:tell\s+me\s+)?(?:what|how|why|when|where|which|who|about)?\s*|"
    r"(?:please\s+)?(?:tell\s+me|explain)(?:\s+what|\s+how|\s+why|\s+when|\s+where|\s+which|\s+who|\s+about)?\s*|"
    r"i(?:'d|\s+would)\s+like\s+to\s+know(?:\s+what|\s+how|\s+why|\s+when|\s+where|\s+which|\s+who|\s+about)?\s*|"
    r"i\s+want\s+to\s+know(?:\s+what|\s+how|\s+why|\s+when|\s+where|\s+which|\s+who|\s+about)?\s*"
    r")",
    re.IGNORECASE,
)

_LEADING_ARTICLE_EN = re.compile(r"^\s*(?:the|a|an)\s+", re.IGNORECASE)

_LLM_PREP_SYSTEM = (
    "You extract a compact knowledge-base SEARCH PHRASE from user messages.\n"
    "Return ONLY valid JSON with keys action and query.\n"
    "action must be rag or smalltalk.\n"
    "Use smalltalk only when the message is ONLY a greeting/thanks/ack with no real "
    "information need; then query=\"\".\n"
    "Otherwise use rag and put a SHORT search phrase in query — keywords the KB can "
    "match, NOT a full question.\n"
    "Rules for query:\n"
    "- NO greetings, thanks, filler, or sidetalk.\n"
    "- NO question words (what/how/why/when/where/who/which) and NO question mark.\n"
    "- KEEP every entity name, product name, and technical term EXACTLY as written.\n"
    "- KEEP ALL items when the user lists multiple (and/or); do not drop any.\n"
    "- KEEP the attribute or topic asked about (fees, limits, balance, term, hold, etc.).\n"
    'Example: user "What are the minimum balance requirements for Everyday Checking '
    'and Money Market?" -> {"action":"rag","query":"minimum balance requirements '
    'Everyday Checking Money Market accounts"}\n'
    'Example: user "hello" -> {"action":"smalltalk","query":""}'
)


@dataclass
class PreparedQuery:
    original: str
    rag_query: str
    direct_response: Optional[str] = None
    prep_source: PrepSource = "none"


def strip_conversational_prefix(text: str) -> str:
    """Remove leading greetings/thanks/fillers; loop until stable."""
    if not text:
        return ""
    t = text.strip()
    prev = None
    while prev != t:
        prev = t
        t = _CONV_PREFIX_EN.sub("", t).strip()
        t = _CONV_PREFIX_AR.sub("", t).strip()
    return t


def strip_question_framing(text: str) -> str:
    """Remove interrogative wrappers; keep entities, attributes, and conjunctions."""
    if not text:
        return ""
    t = str(text).strip()
    prev = None
    while prev != t:
        prev = t
        t = _QUESTION_OPENER_EN.sub("", t).strip()
    t = _LEADING_ARTICLE_EN.sub("", t, count=1).strip()
    return t.rstrip("?.!").strip()


def extract_search_intent(text: str) -> str:
    """Rule-based KB search phrase: strip greetings then question framing."""
    t = strip_question_framing(strip_conversational_prefix(text))
    return t if _is_substantive(t) else str(text or "").strip()


def _finalize_search_phrase(text: str) -> str:
    """Last-pass cleanup so RAG always receives a phrase, never a question."""
    t = strip_question_framing(str(text or "").strip())
    return t if _is_substantive(t) else str(text or "").strip()


def _is_substantive(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    if re.search(r"[\u0600-\u06FF]", t):
        return len(re.sub(r"\s+", "", t)) >= 2
    tokens = [w for w in re.findall(r"[a-z0-9]{2,}", t.lower()) if w not in {"ok", "so", "the", "a", "an"}]
    return len(tokens) >= 1


def is_pure_conversational_only(original: str, stripped: str) -> bool:
    if not _is_substantive(stripped):
        return True
    try:
        from backend.assistify_rag_server import _is_pure_smalltalk_query

        if _is_pure_smalltalk_query(stripped) or _is_pure_smalltalk_query(original):
            return True
    except Exception:
        pass
    return False


def needs_llm_query_prep(original: str, stripped: str) -> bool:
    if not RAG_QUERY_LLM_PREP:
        return False
    orig = str(original or "").strip()
    work = str(stripped or "").strip()
    if not work:
        return False
    # Always polish real KB/document questions through the LLM layer so RAG receives
    # a compact search phrase instead of conversational interrogatives.
    if _looks_like_document_question(orig) or _looks_like_document_question(work):
        return True
    if orig.lower() == work.lower():
        if _MID_CONVERSATIONAL.search(work) and _looks_like_document_question(work):
            return True
        return False
    if "," in orig and _looks_like_document_question(work):
        return True
    if len(orig.split()) > 12 and _MID_CONVERSATIONAL.search(orig):
        return True
    if _MID_CONVERSATIONAL.search(work) and _looks_like_document_question(work):
        return True
    return work.lower() != orig.lower()


def _looks_like_document_question(text: str) -> bool:
    q = str(text or "").strip().lower()
    if not q:
        return False
    if re.search(r"[\u0600-\u06FF]", q):
        return bool(re.search(r"\b(?:ما|ماذا|كيف|لماذا|متى|أين|من|هل)\b", q))
    return bool(
        re.search(
            r"\b(?:what|who|when|where|why|how|which|explain|define|tell|list|describe|compare)\b",
            q,
        )
    )


def _parse_llm_prep_json(raw: str) -> Optional[dict]:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


async def llm_normalize_rag_query(text: str) -> Optional[PreparedQuery]:
    """Small Ollama call to extract one KB question or detect pure smalltalk."""
    import aiohttp

    model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    base = os.getenv("LLM_SERVER_URL", os.getenv("OLLAMA_HOST", "http://127.0.0.1:8010")).rstrip("/")
    if base.endswith("/api/chat"):
        url = base
    else:
        url = f"{base}/api/chat"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _LLM_PREP_SYSTEM},
            {"role": "user", "content": str(text or "").strip()},
        ],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 80},
    }
    try:
        timeout = aiohttp.ClientTimeout(total=3, connect=2, sock_read=3)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=timeout) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception as exc:
        logger.info("[QUERY PREP] LLM normalize skipped: %s", exc)
        return None

    content = ""
    try:
        content = str((data.get("message") or {}).get("content") or "").strip()
    except Exception:
        return None
    parsed = _parse_llm_prep_json(content)
    if not parsed:
        return None

    action = str(parsed.get("action") or "rag").strip().lower()
    query = str(parsed.get("query") or "").strip()
    if action == "smalltalk":
        try:
            from backend.assistify_rag_server import _smalltalk_response

            return PreparedQuery(
                original=text,
                rag_query="",
                direct_response=_smalltalk_response(text),
                prep_source="llm",
            )
        except Exception:
            return PreparedQuery(original=text, rag_query="", direct_response=None, prep_source="llm")
    if query:
        return PreparedQuery(
            original=text,
            rag_query=_finalize_search_phrase(query),
            prep_source="llm",
        )
    return None


async def prepare_query_for_rag(text: str) -> PreparedQuery:
    """Hybrid prep: rules strip, optional LLM, KB typo correction."""
    original = str(text or "").strip()
    if not original:
        return PreparedQuery(original="", rag_query="", prep_source="none")

    stripped = strip_conversational_prefix(original)
    if is_pure_conversational_only(original, stripped):
        return PreparedQuery(
            original=original,
            rag_query="",
            direct_response=_smalltalk_direct_response(original),
            prep_source="rules",
        )

    # Rule-based search intent is always applied first so RAG never sees raw
    # interrogatives like "What are the ...?" even when the LLM is unavailable.
    working = extract_search_intent(original)
    prep_source: PrepSource = "rules"

    if needs_llm_query_prep(original, working):
        llm_result = await llm_normalize_rag_query(original)
        if llm_result:
            if llm_result.direct_response:
                return llm_result
            if llm_result.rag_query:
                working = llm_result.rag_query
                prep_source = "llm"

    rag_query = _apply_spelling_correction(_finalize_search_phrase(working))
    logger.info(
        "[QUERY PREP] original='%s' rag_query='%s' source=%s",
        original[:160],
        rag_query[:160],
        prep_source,
    )
    return PreparedQuery(original=original, rag_query=rag_query, prep_source=prep_source)


def _apply_spelling_correction(text: str) -> str:
    try:
        from backend.assistify_rag_server import _spelling_correction_preserving_exact_terms

        corrected = _spelling_correction_preserving_exact_terms(text)
        return corrected if corrected else text
    except Exception:
        return text


def _smalltalk_direct_response(text: str) -> str:
    from backend.assistify_rag_server import _smalltalk_response

    return _smalltalk_response(text)
