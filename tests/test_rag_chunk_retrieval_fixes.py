"""Regression tests for RAG chunking and table/heading heuristics."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from backend.rag_chunk_heuristics import looks_table_or_heading_like_chunk as _looks_table_or_heading_like_chunk
from backend.knowledge_base import chunk_and_add_document


def _chunk_texts_from_doc(text: str, *, doc_id: str = "test_doc", metadata: dict | None = None) -> list[str]:
    mock_collection = MagicMock()
    mock_collection.name = "test_rag_chunk_fixes"
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = np.array([[0.1] * 8])

    with patch("backend.knowledge_base.client") as mock_client, patch(
        "backend.knowledge_base.get_or_create_collection",
        return_value=mock_collection,
    ), patch("backend.knowledge_base.embedder", mock_embedder):
        mock_client.get_or_create_collection.return_value = mock_collection
        details = chunk_and_add_document(
            doc_id,
            text,
            metadata=metadata or {"file_ext": "pdf"},
            return_details=True,
            target_collection_name="test_rag_chunk_fixes",
        )
    return list(details.get("chunk_texts") or [])


# --- Bug 1: colon-led definition bullets must not be penalized ---

COLON_DEFINITION_NOT_TABLE = [
    "Brake Fluid: Hygroscopic (absorbs moisture over time), replacement every 2-3 years.",
    "Coolant (Antifreeze): A mixture of water and ethylene glycol that prevents freezing in cold climates.",
    "Engine Oil: 5W-30 viscosity is recommended for most passenger vehicles in moderate climates.",
    "ATF: Automatic transmission fluid lubricates gears and must meet manufacturer specifications.",
    "Power Steering Fluid: Hydraulic fluid that assists steering and should be checked monthly.",
    (
        "Battery Electrolyte: Sulfuric acid solution that stores chemical energy and requires "
        "periodic inspection of fluid levels in non-sealed batteries."
    ),
]

COLON_DEFINITION_SHOULD_BE_TABLE_LIKE = [
    "Chapter 3: Engine Systems",
    "Section 2.1: Overview",
    "INTRODUCTION TO VEHICLES",
    "Table 4: Fluid Specifications",
    "[TABLE DATA]\nOil Type | Viscosity | API Rating\n5W-30 | Standard | SN\nSynthetic | High | SP",
    "Name          Role          Year\nTaylor        Management    1911\nFayol         Admin         1916",
    "a | b | c",
    "1. Scientific Management Taylor\n2. Administrative Theory Fayol\n3. Bureaucracy Weber",
    "Figure 2: Engine cross-section diagram",
    "Classification\nType A\nType B\nType C\nType D\nType E\nType F\nType G\nType H",
]


@pytest.mark.parametrize("text", COLON_DEFINITION_NOT_TABLE)
def test_colon_definition_bullets_not_table_like(text: str):
    assert _looks_table_or_heading_like_chunk(text) is False


@pytest.mark.parametrize("text", COLON_DEFINITION_SHOULD_BE_TABLE_LIKE)
def test_true_headings_and_tables_still_table_like(text: str):
    assert _looks_table_or_heading_like_chunk(text) is True


def test_colon_definition_multi_bullet_chunk_not_table_like():
    chunk = "\n".join(COLON_DEFINITION_NOT_TABLE[:4])
    assert _looks_table_or_heading_like_chunk(chunk) is False


# --- Bug 2: prose and [TABLE DATA] must never share a chunk ---

def test_table_data_forces_chunk_boundary():
    prose_token = "VISCOSITYPROSE"
    prose = " ".join([prose_token] * 250)
    table = "[TABLE DATA]\nOil Type | Viscosity | Notes\n5W-30 | Standard | API SN"
    text = f"[PAGE_START: 1]\n{prose}\n\n{table}\n[PAGE_END: 1]"

    chunks = _chunk_texts_from_doc(text)
    assert chunks, "expected at least one chunk"

    mixed = [
        c for c in chunks
        if prose_token in c and "[TABLE DATA]" in c
    ]
    assert mixed == [], f"prose/table mixed in chunks: {mixed[:2]}"


def test_colon_bullet_before_table_stays_retrievable():
    bullet = (
        "Brake Fluid: Hygroscopic (absorbs moisture over time), replacement every 2-3 years."
    )
    table = "[TABLE DATA]\nFluid | Interval\nBrake Fluid | 2-3 years"
    text = f"[PAGE_START: 1]\n{bullet}\n\n{table}\n[PAGE_END: 1]"

    chunks = _chunk_texts_from_doc(text)
    bullet_chunks = [c for c in chunks if "Brake Fluid: Hygroscopic" in c]
    assert bullet_chunks, "colon-led bullet chunk missing"
    assert _looks_table_or_heading_like_chunk(bullet_chunks[0]) is False
    assert all("[TABLE DATA]" not in c for c in bullet_chunks)


# --- Bug 3: section headings must NOT be injected/repeated inside chunk text ---

def test_heading_not_repeated_inside_chunk():
    # A numbered section heading followed by a multi-line body must never have the
    # heading text spliced between sentences or repeated once per line. This is
    # the corruption signature that produced
    # "1. About Meridian Financial Services" between every sentence.
    heading = "1. About Meridian Financial Services"
    body_lines = [
        "Meridian Financial Services is a digital-first bank operating across the United States.",
        "Deposit accounts are held with our partner bank and are FDIC-insured up to $250,000.",
        "We serve individuals and small businesses through our mobile app and web banking.",
    ]
    text = "[PAGE_START: 1]\n" + heading + "\n" + "\n".join(body_lines) + "\n[PAGE_END: 1]"

    chunks = _chunk_texts_from_doc(text)
    joined = "\n".join(chunks)
    assert "Meridian Financial Services is a digital-first bank" in joined
    for c in chunks:
        assert heading not in c, f"section heading injected into chunk text: {c!r}"
        assert "United States. 1. About" not in c, f"heading spliced mid-text: {c!r}"


def test_table_header_kept_once_with_rows():
    # A pipe table header must appear exactly once and stay attached to its rows
    # (not dropped, not repeated before every row).
    text = (
        "[PAGE_START: 1]\n"
        "2. Deposit Accounts\n"
        "Account | Monthly fee | Min. balance | Highlights\n"
        "Everyday Checking | $0 | $0 | No overdraft fees, early direct deposit\n"
        "High-Yield Savings | $0 | $0 | Competitive APY\n"
        "Money Market | $0 | $1,000 | Tiered APY, check-writing\n"
        "[PAGE_END: 1]"
    )
    chunks = _chunk_texts_from_doc(text)
    table_chunks = [c for c in chunks if "Money Market" in c]
    assert table_chunks, "table chunk missing"
    c = table_chunks[0]
    assert c.count("Account | Monthly fee | Min. balance | Highlights") == 1
    assert "Money Market | $0 | $1,000" in c
    assert "Everyday Checking | $0 | $0" in c


def test_bullet_list_under_heading_keeps_full_sentences():
    heading = "Maintenance Fluids"
    bullets = "\n".join(COLON_DEFINITION_NOT_TABLE[:4])
    text = f"[PAGE_START: 1]\n{heading}\n\n{bullets}\n[PAGE_END: 1]"

    chunks = _chunk_texts_from_doc(text)
    joined = "\n".join(chunks)
    assert "Brake Fluid: Hygroscopic" in joined
    assert "Coolant (Antifreeze): A mixture" in joined
    assert not any(
        c.strip() == heading and len(c.split()) <= 4
        for c in chunks
    ), "heading-only fragment chunk detected"
