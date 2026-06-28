"""Regression tests for KB/RAG final RCA fixes (status, validation, greetings)."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.assistify_rag_server import (
    _classify_smalltalk_intent,
    _definition_quality_rejected_reason,
    _detect_fact_query_type,
    _extract_table_fact_answer,
    _is_numeric_fact_lookup_query,
    _normalize_query_for_router,
    _resolve_grounded_answer_route,
    _set_kb_pipeline_stage,
    classify_query_route,
)
from backend.config_head import RAG_NO_MATCH_RESPONSE
from backend.rag_query_prep import is_pure_conversational_only, prepare_query_for_rag, strip_conversational_prefix


MERIDIAN_DOCS = [
    {
        "page_content": (
            "Meridian Financial Services is a regional bank offering personal and business banking.\n\n"
            "[TABLE DATA]\n"
            "Everyday Checking | $500 minimum balance | No monthly fee\n"
            "Premium Checking | $2,500 minimum balance | Waived fees with direct deposit\n\n"
            "FDIC insurance covers deposits up to $250,000 per depositor, per insured bank."
        ),
        "metadata": {"filename": "Meridian_Financial_Handbook.pdf"},
    }
]


def test_greeting_variants_normalize_and_classify() -> None:
    variants = {
        "hi": "greeting",
        "hii": "greeting",
        "hiii": "greeting",
        "hello": "greeting",
        "helloo": "greeting",
        "hey": "greeting",
        "heyy": "greeting",
        "thanks": "thanks",
        "thankss": "thanks",
        "ok": "ack",
        "okk": "ack",
    }
    for raw, expected in variants.items():
        norm = _normalize_query_for_router(raw)
        assert _classify_smalltalk_intent(raw) == expected, f"{raw!r} norm={norm!r}"
        assert classify_query_route(raw) == "smalltalk", raw


def test_greeting_variants_strip_prefix() -> None:
    for variant in ("hii", "heyy", "helloo", "thankss", "okk"):
        assert strip_conversational_prefix(variant) == ""


def test_prepare_greeting_variants_smalltalk() -> None:
    for variant in ("hi", "hii", "hiii", "helloo", "heyy", "thankss", "okk"):
        prepared = asyncio.run(prepare_query_for_rag(variant))
        assert prepared.direct_response is not None, variant
        assert prepared.rag_query == "", variant


def test_numeric_fact_query_detection() -> None:
    assert _is_numeric_fact_lookup_query("What is the FDIC coverage limit?")
    assert _is_numeric_fact_lookup_query(
        "What is the minimum balance requirement for Everyday Checking?"
    )
    assert _detect_fact_query_type("What is the FDIC coverage limit?") == "numeric"
    assert _resolve_grounded_answer_route("What is the FDIC coverage limit?") == "fact"


def test_table_fact_fdic_extraction() -> None:
    answer = _extract_table_fact_answer("What is the FDIC coverage limit?", MERIDIAN_DOCS)
    assert answer is not None
    assert "250" in answer
    assert answer != RAG_NO_MATCH_RESPONSE


def test_table_fact_minimum_balance_extraction() -> None:
    answer = _extract_table_fact_answer(
        "What is the minimum balance requirement for Everyday Checking?",
        MERIDIAN_DOCS,
    )
    assert answer is not None
    assert "500" in answer
    assert "minimum balance" in answer.lower()
    assert "everyday checking" in answer.lower()
    assert "premium" not in answer.lower()


def test_definition_quality_accepts_insured_sentence() -> None:
    sentence = "FDIC insurance covers deposits up to $250,000 per depositor."
    reason = _definition_quality_rejected_reason(
        sentence,
        entity_l="fdic coverage limit",
        query_text="What is the FDIC coverage limit?",
    )
    assert reason is None, reason


def test_kb_pipeline_stage_clamps_indexed_to_total() -> None:
    from backend import assistify_rag_server as srv

    srv._kb_pipeline_state["state"] = "processing"
    srv._kb_pipeline_state["stage"] = "writing"
    _set_kb_pipeline_stage("writing", indexed=120, total=100, percent=100)
    assert srv._kb_pipeline_state["indexed_chunks"] == 100
    assert srv._kb_pipeline_state["total_chunks"] == 100


def test_active_source_filter_bypassed_for_tenant_isolated_retrieval() -> None:
    from backend import assistify_rag_server as srv

    sample = [{"metadata": {"normalized_filename": "handbook.pdf"}, "text": "fee schedule"}]
    token = srv._request_tenant_id.set(6)
    try:
        assert srv._uses_tenant_isolated_retrieval() is True
        assert len(srv._filter_results_to_active_sources(sample)) == 1
        assert len(srv._filter_doc_dicts_to_active_sources(sample)) == 1
    finally:
        srv._request_tenant_id.reset(token)

    default_token = srv._request_tenant_id.set(srv.DEFAULT_TENANT_ID)
    try:
        srv._active_doc_registry["active_sources"] = set()
        assert srv._filter_results_to_active_sources(sample) == []
    finally:
        srv._request_tenant_id.reset(default_token)


def test_numeric_fee_query_skips_definition_rewrite() -> None:
    from backend import assistify_rag_server as srv

    query = "What is the standard fee for an expedited card replacement?"
    grounded = (
        "To replace a lost or damaged card, choose 'Replace card' - "
        "standard replacement is free; expedited is $25."
    )
    assert srv._is_ws_definition_query_mode(query) is False
    fixed = srv._ws_fix_explanation_answer(query, grounded, [])
    assert "refers to" not in fixed.lower()
    assert "expedited is $25" in fixed or "expedited is $25." in fixed


def test_pipe_delimited_tables_convert_to_markdown() -> None:
    from backend import assistify_rag_server as srv

    raw = (
        "Transfer type | Typical timing | Limit (standard) | Fee ACH (bank-to-bank) | "
        "1-3 business days | $25,000 / day | Free Instant debit-card transfer | Minutes | "
        "$5,000 / day | 1.5% (min $0.50) Domestic wire | Same business day | $100,000 / day | $15 outgoing Mobile check deposit | "
        "Held 1-5 business days | $10,000 / day | Free Peer-to-peer (Meridian Pay) | Minutes | "
        "$2,500 / day | Free Limits may be higher for established accounts and can be reviewed on request."
    )
    md = srv._format_pipe_delimited_tables(raw)
    assert md.startswith("| Transfer type | Typical timing | Limit (standard) | Fee |")
    assert re.search(r"\|\s*---\s*\|\s*---\s*\|\s*---\s*\|\s*---\s*\|", md)
    assert "ACH (bank-to-bank) | 1-3 business days | $25,000 / day | Free |" in md
    assert "Domestic wire | Same business day | $100,000 / day | $15 outgoing |" in md
    assert "Peer-to-peer (Meridian Pay) | Minutes | $2,500 / day | Free |" in md
    assert "Limits may be higher" in md
    assert "Free Limits may be higher" not in md


def test_wire_transfer_query_returns_matching_row_not_full_table() -> None:
    raw = (
        "Transfer type | Typical timing | Limit (standard) | Fee ACH (bank-to-bank) | "
        "1-3 business days | $25,000 / day | Free Instant debit-card transfer | Minutes | "
        "$5,000 / day | 1.5% (min $0.50) Domestic wire | Same business day | $100,000 / day | $15 outgoing Mobile check deposit | "
        "Held 1-5 business days | $10,000 / day | Free Peer-to-peer (Meridian Pay) | Minutes | "
        "$2,500 / day | Free Limits may be higher for established accounts and can be reviewed on request."
    )
    docs = [{"page_content": raw, "metadata": {"filename": "handbook.pdf"}}]
    q = "How much does an outgoing domestic wire transfer cost, and how long does it take?"
    answer = _extract_table_fact_answer(q, docs)
    assert answer is not None
    assert "$15" in answer
    assert "business day" in answer.lower()
    assert "ACH" not in answer
    assert "Instant debit-card transfer" not in answer

    from backend import assistify_rag_server as srv

    full_md = srv._format_pipe_delimited_tables(raw)
    focused = srv._format_pipe_delimited_tables(raw, query_text=q)
    assert "ACH (bank-to-bank)" in full_md
    assert "ACH" not in focused
    assert "$15" in focused


def test_cleanup_preserves_markdown_table_separator() -> None:
    from backend import assistify_rag_server as srv

    raw = (
        "Transfer type | Typical timing | Limit (standard) | Fee ACH (bank-to-bank) | "
        "1-3 business days | $25,000 / day | Free Instant debit-card transfer | Minutes | "
        "$5,000 / day | 1.5% (min $0.50) Domestic wire | Same business day | $100,000 / day | $15 outgoing"
    )
    md = srv._format_pipe_delimited_tables(raw)
    cleaned = srv._cleanup_final_answer_text(md)
    assert re.search(r"\|\s*---\s*\|", cleaned)
    assert "ACH (bank-to-bank)" in cleaned


if __name__ == "__main__":
    test_greeting_variants_normalize_and_classify()
    test_greeting_variants_strip_prefix()
    test_prepare_greeting_variants_smalltalk()
    test_numeric_fact_query_detection()
    test_table_fact_fdic_extraction()
    test_table_fact_minimum_balance_extraction()
    test_definition_quality_accepts_insured_sentence()
    test_kb_pipeline_stage_clamps_indexed_to_total()
    print("All KB/RAG final fix tests passed.")
