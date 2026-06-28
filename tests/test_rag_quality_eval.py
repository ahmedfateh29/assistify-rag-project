"""RAG quality evaluation harness.

A reproducible, document-agnostic scorer used to measure retrieval/answer
quality before and after the RAG enhancement work. It drives the existing
deterministic extractors against a set of synthetic, generic documents and
scores each case on two axes:

  * found:   the system returned a grounded answer (not the no-match sentinel)
  * correct: the answer contains every required evidence substring and none of
             the forbidden ones

IMPORTANT (genericity): no company/product/value constant lives in `backend/`.
The synthetic corpus and the expected substrings live only in THIS test data
file, so the production code remains fully document-agnostic. The fictional
"Northwind"/"Acme" style entities here exist purely to exercise structural
behaviour (tables, multi-entity rows, definitions, lists).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import backend.assistify_rag_server as rag_server
from backend.assistify_rag_server import _extract_table_fact_answer
from backend.config_head import RAG_NO_MATCH_RESPONSE

# Isolate the harness from the live ChromaDB collection so scores are
# reproducible and depend only on the synthetic corpus below. The extractor
# otherwise augments candidates with the active collection's pipe-table chunks,
# which would make this measurement machine-dependent.
rag_server._collection_pipe_table_chunks = lambda *a, **k: []


# --- Synthetic, generic corpus -------------------------------------------------
# A fictional services provider. Values are invented and live only in test data.
EVAL_DOCS = [
    {
        "page_content": (
            "Northwind Services overview. Northwind provides utility and connectivity plans "
            "to residential and business customers.\n\n"
            "[TABLE DATA]\n"
            "Plan | Monthly price | Setup fee | Data cap\n"
            "Starter | $20 / month | $10 | 100 GB\n"
            "Standard | $35 / month | $0 | 500 GB\n"
            "Premium | $60 / month | $0 | Unlimited\n\n"
            "Activation typically completes within 1 business day."
        ),
        "metadata": {"filename": "Northwind_Plans.pdf", "section": "Plans"},
    },
    {
        "page_content": (
            "A service credit is a billing adjustment applied to a customer account when an "
            "outage exceeds the guaranteed uptime threshold. Service credits are calculated "
            "automatically and appear on the next invoice."
        ),
        "metadata": {"filename": "Northwind_Glossary.pdf", "section": "Glossary"},
    },
    {
        "page_content": (
            "[TABLE DATA]\n"
            "Transfer type | Typical timing | Limit | Fee\n"
            "Standard transfer | 1-3 business days | $25,000 / day | Free\n"
            "Express transfer | Same business day | $100,000 / day | $15 outgoing\n"
            "Instant transfer | Minutes | $5,000 / day | 1.5% (min $0.50)"
        ),
        "metadata": {"filename": "Northwind_Transfers.pdf", "section": "Transfers"},
    },
]


@dataclass
class EvalCase:
    query: str
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    # If True, the expected outcome is the no-match sentinel (true negative).
    expect_not_found: bool = False


# Each case is structural: it asserts evidence substrings, never a hardcoded
# answer string in backend code.
EVAL_CASES: list[EvalCase] = [
    # --- single-entity numeric lookups (should already work) ---
    EvalCase(
        query="What is the setup fee for the Starter plan?",
        must_contain=["$10"],
        must_not_contain=["$0"],
    ),
    EvalCase(
        query="How much is the Standard plan per month?",
        must_contain=["$35"],
    ),
    EvalCase(
        query="How much does an express transfer cost and how long does it take?",
        must_contain=["$15", "business day"],
        must_not_contain=["Standard transfer", "Instant transfer"],
    ),
    # --- multi-entity lookups (Phase 4 target; baseline expected to FAIL) ---
    EvalCase(
        query="What is the monthly price for the Starter and Premium plans?",
        must_contain=["$20", "$60"],
    ),
    EvalCase(
        query="What are the setup fees for the Starter and Standard plans?",
        must_contain=["$10", "$0"],
    ),
    # --- true negative: an entity that does not exist in any table. A literal
    #     extractor can detect this (no matching row label, no row token hit),
    #     unlike a missing *attribute* expressed via synonyms, so it is the fair
    #     not-found probe for the deterministic layer. ---
    EvalCase(
        query="What is the setup fee for the Enterprise plan?",
        expect_not_found=True,
    ),
]


@dataclass
class CaseResult:
    case: EvalCase
    answer: str | None
    found: bool
    correct: bool
    reason: str = ""


def _evaluate_case(case: EvalCase) -> CaseResult:
    answer = _extract_table_fact_answer(case.query, EVAL_DOCS)
    is_sentinel = (answer is None) or (
        str(answer).strip().lower() == RAG_NO_MATCH_RESPONSE.strip().lower()
    )
    found = not is_sentinel

    if case.expect_not_found:
        correct = not found
        reason = "" if correct else f"expected not-found but got: {answer!r}"
        return CaseResult(case, answer, found, correct, reason)

    if not found:
        return CaseResult(case, answer, found, False, "no grounded answer returned")

    text = str(answer)
    missing = [s for s in case.must_contain if s not in text]
    forbidden = [s for s in case.must_not_contain if s in text]
    correct = not missing and not forbidden
    reason = ""
    if missing:
        reason += f"missing={missing} "
    if forbidden:
        reason += f"forbidden={forbidden} "
    return CaseResult(case, answer, found, correct, reason.strip())


def run_eval() -> dict:
    results = [_evaluate_case(c) for c in EVAL_CASES]
    total = len(results)
    found_ok = sum(
        1
        for r in results
        if (r.case.expect_not_found and not r.found) or (not r.case.expect_not_found and r.found)
    )
    correct_ok = sum(1 for r in results if r.correct)
    return {
        "total": total,
        "found_ok": found_ok,
        "correct_ok": correct_ok,
        "results": results,
    }


def format_report(summary: dict) -> str:
    lines = [
        "=" * 70,
        "RAG QUALITY EVAL",
        f"  cases:            {summary['total']}",
        f"  found correctly:  {summary['found_ok']}/{summary['total']}",
        f"  answered correct: {summary['correct_ok']}/{summary['total']}",
        "-" * 70,
    ]
    for r in summary["results"]:
        status = "PASS" if r.correct else "FAIL"
        lines.append(f"  [{status}] {r.case.query}")
        if not r.correct:
            lines.append(f"         -> answer={r.answer!r}")
            if r.reason:
                lines.append(f"         -> {r.reason}")
    lines.append("=" * 70)
    return "\n".join(lines)


# --- pytest entry points -------------------------------------------------------
def test_single_entity_cases_answered_correctly() -> None:
    """Single-entity numeric lookups must be found and correct."""
    failures = []
    for case in EVAL_CASES:
        if case.expect_not_found or len(_entities_in_query(case.query)) > 1:
            continue
        r = _evaluate_case(case)
        if not r.correct:
            failures.append((case.query, r.answer, r.reason))
    assert not failures, f"single-entity regressions: {failures}"


def test_true_negative_is_not_found() -> None:
    """A detail absent from the corpus must not be fabricated."""
    for case in EVAL_CASES:
        if not case.expect_not_found:
            continue
        r = _evaluate_case(case)
        assert r.correct, f"expected not-found for {case.query!r}, got {r.answer!r}"


def _entities_in_query(query: str) -> list[str]:
    # crude multi-entity detector used only to partition the suite
    q = query.lower()
    return [p for p in q.replace(",", " ").split(" and ") if p.strip()]


if __name__ == "__main__":
    print(format_report(run_eval()))
