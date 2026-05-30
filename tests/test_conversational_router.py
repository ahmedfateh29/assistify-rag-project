"""Router tests for conversational (non-document) user messages."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config_head import (
    CONVERSATIONAL_PRESENCE_EN,
    CONVERSATIONAL_REDIRECT_EN,
    RAG_NO_MATCH_RESPONSE,
)
from backend.assistify_rag_server import (
    _finalize_user_visible_answer,
    _is_support_procedural_query,
    _rescue_support_procedural_from_docs,
    classify_query_route,
)


def test_classify_query_route_conversational() -> None:
    cases = [
        ("tell me are you getting my messages", "conversational_ack"),
        ("are you getting me ??", "conversational_ack"),
        ("are you getting me", "conversational_ack"),
        ("do you get me", "conversational_ack"),
        ("Can you listen to me?", "conversational_ack"),
        ("can you hear me", "conversational_ack"),
        ("are you there", "conversational_ack"),
        ("why are you only having to find the document", "assistant_meta"),
        ("Why do you keep saying not found in the document", "assistant_meta"),
        ("So tell me how to reset the password", "document_question"),
        ("tell me how to reset my password", "document_question"),
        ("How do I reset my password?", "document_question"),
    ]
    for query, expected_route in cases:
        assert classify_query_route(query) == expected_route, f"{query!r} -> {classify_query_route(query)!r}"


def test_finalize_maps_sentinel_for_conversational() -> None:
    out = _finalize_user_visible_answer("can you hear me", RAG_NO_MATCH_RESPONSE)
    assert out != RAG_NO_MATCH_RESPONSE
    assert "here to help" in out.lower() or "support" in out.lower()


def test_finalize_maps_sentinel_for_getting_me() -> None:
    out = _finalize_user_visible_answer("are you getting me", RAG_NO_MATCH_RESPONSE)
    assert out != RAG_NO_MATCH_RESPONSE
    assert out == CONVERSATIONAL_PRESENCE_EN


def test_finalize_keeps_sentinel_for_document_miss() -> None:
    out = _finalize_user_visible_answer(
        "What is quantum physics?",
        RAG_NO_MATCH_RESPONSE,
    )
    assert out == RAG_NO_MATCH_RESPONSE


def test_finalize_maps_sentinel_for_behavior_complaint() -> None:
    out = _finalize_user_visible_answer(
        "why are you only having to find the document",
        RAG_NO_MATCH_RESPONSE,
    )
    assert out != RAG_NO_MATCH_RESPONSE
    assert "knowledge base" in out.lower() or "documents" in out.lower()


def test_conversational_redirect_constant() -> None:
    assert "help" in CONVERSATIONAL_REDIRECT_EN.lower()
    assert "password reset" in CONVERSATIONAL_REDIRECT_EN.lower()


def test_support_procedural_voice_phrasing() -> None:
    assert _is_support_procedural_query("So tell me how to reset the password")
    assert _is_support_procedural_query("tell me how to reset my password")


def test_support_procedural_rescue_from_docs() -> None:
    docs = [
        {
            "page_content": (
                "To reset your password, follow these steps: 1) Go to the login page "
                "and click 'Forgot Password' 2) Enter your registered email address."
            ),
            "metadata": {"id": "password_reset"},
        }
    ]
    out = _finalize_user_visible_answer(
        "So tell me how to reset the password",
        RAG_NO_MATCH_RESPONSE,
        retrieved_docs=docs,
    )
    assert out != RAG_NO_MATCH_RESPONSE
    assert "forgot password" in out.lower()
    assert _rescue_support_procedural_from_docs("So tell me how to reset the password", docs)


if __name__ == "__main__":
    test_classify_query_route_conversational()
    test_finalize_maps_sentinel_for_conversational()
    test_finalize_maps_sentinel_for_getting_me()
    test_finalize_keeps_sentinel_for_document_miss()
    test_finalize_maps_sentinel_for_behavior_complaint()
    test_conversational_redirect_constant()
    test_support_procedural_voice_phrasing()
    test_support_procedural_rescue_from_docs()
    print("All conversational router tests passed.")
