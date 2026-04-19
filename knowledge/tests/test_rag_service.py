"""
Unit tests for RAGService.

All external dependencies (AI client, DB queries) are mocked.

Covers:
- should_use_ai: False when no document chunks exist
- should_use_ai: True when high-similarity chunks are found
- generate_response: error dict when AI is not configured
- generate_response: sources list populated from matched chunks
- generate_response: confidence higher with good context vs no context
"""
import os
import math
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from knowledge.services.rag import RAGService


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_rag_service(
    ai_available: bool = True,
    ai_response: dict = None,
    similar_chunks=None,
):
    """
    Build a RAGService with fully mocked internals.

    ai_available: whether ai_client.is_available() returns True
    ai_response: what ai_client.generate_response() returns
    similar_chunks: what embedding_service.search_user_knowledge() returns
    """
    mock_ai = MagicMock()
    mock_ai.is_available.return_value = ai_available
    mock_ai.generate_response.return_value = ai_response or {
        "response": "Test response",
        "confidence": 0.5,
        "tokens_used": 42,
    }

    mock_embedding = MagicMock()
    mock_embedding.search_user_knowledge.return_value = similar_chunks or []

    with (
        patch("knowledge.services.rag.get_ai_client", return_value=mock_ai),
        patch("knowledge.services.embeddings.get_ai_client", return_value=mock_ai),
    ):
        svc = RAGService()

    # Directly replace services so behaviour is fully controlled in tests
    svc.ai_client = mock_ai
    svc.embedding_service = mock_embedding
    return svc


def _make_user():
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.company_name = "Test Corp"
    return mock_user


def _make_chunk(doc_filename="faq.txt", chunk_index=0, similarity=0.8):
    """Return a (chunk_dict, similarity) tuple as returned by search_user_knowledge."""
    chunk = {
        "id": 1,
        "content": "We offer a 30-day money-back guarantee.",
        "chunk_index": chunk_index,
        "document_filename": doc_filename,
        "document_id": 1,
    }
    return (chunk, similarity)


# ---------------------------------------------------------------------------
# should_use_ai
# ---------------------------------------------------------------------------

class TestShouldUseAi:
    def test_returns_false_when_no_document_chunks(self):
        svc = _make_rag_service()
        user = _make_user()

        with patch("knowledge.models.DocumentChunk") as mock_dc:
            mock_dc.objects.filter.return_value.count.return_value = 0
            result = svc.should_use_ai(user, "What are your hours?")

        assert result["should_respond"] is False
        assert result["confidence"] == 0
        assert "knowledge base" in result["reason"].lower()

    def test_returns_false_when_no_similar_chunks_found(self):
        svc = _make_rag_service(similar_chunks=[])
        user = _make_user()

        with patch("knowledge.models.DocumentChunk") as mock_dc:
            mock_dc.objects.filter.return_value.count.return_value = 5
            result = svc.should_use_ai(user, "unrelated question")

        assert result["should_respond"] is False
        assert result["confidence"] == 0.1

    def test_returns_true_when_high_similarity_chunks_found(self):
        high_sim_chunk = _make_chunk(similarity=0.75)
        svc = _make_rag_service(similar_chunks=[high_sim_chunk])
        user = _make_user()

        with patch("knowledge.models.DocumentChunk") as mock_dc:
            mock_dc.objects.filter.return_value.count.return_value = 5
            result = svc.should_use_ai(user, "money back guarantee?")

        assert result["should_respond"] is True
        assert result["confidence"] >= 0.7
        assert "high" in result["reason"].lower()

    def test_returns_true_for_moderate_similarity(self):
        moderate_chunk = _make_chunk(similarity=0.5)
        svc = _make_rag_service(similar_chunks=[moderate_chunk])
        user = _make_user()

        with patch("knowledge.models.DocumentChunk") as mock_dc:
            mock_dc.objects.filter.return_value.count.return_value = 3
            result = svc.should_use_ai(user, "do you have a guarantee?")

        assert result["should_respond"] is True
        assert result["confidence"] >= 0.5

    def test_returns_false_for_low_similarity_below_threshold(self):
        low_sim_chunk = _make_chunk(similarity=0.36)
        svc = _make_rag_service(similar_chunks=[low_sim_chunk])
        user = _make_user()

        with patch("knowledge.models.DocumentChunk") as mock_dc:
            mock_dc.objects.filter.return_value.count.return_value = 3
            # should_use_ai uses min_similarity=0.35, so this chunk passes retrieval
            # but best_similarity=0.36 < 0.4 → should_respond=False
            result = svc.should_use_ai(user, "some question")

        assert result["should_respond"] is False
        assert "low" in result["reason"].lower()


# ---------------------------------------------------------------------------
# generate_response
# ---------------------------------------------------------------------------

class TestGenerateResponse:
    def test_returns_error_dict_when_ai_not_configured(self):
        svc = _make_rag_service(ai_available=False)
        user = _make_user()

        result = svc.generate_response(user, "What are your prices?")

        assert result["response"] is None
        assert result["confidence"] == 0
        assert result["error"] == "AI not configured"
        assert result["sources"] == []

    def test_sources_list_populated_from_matched_chunks(self):
        chunk1 = _make_chunk("prices.txt", chunk_index=0, similarity=0.85)
        chunk2 = _make_chunk("faq.txt", chunk_index=2, similarity=0.70)
        svc = _make_rag_service(
            ai_available=True,
            similar_chunks=[chunk1, chunk2],
            ai_response={
                "response": "We offer competitive prices.",
                "confidence": 0.6,
                "tokens_used": 50,
            },
        )
        user = _make_user()

        result = svc.generate_response(user, "prices?")

        assert "sources" in result
        assert len(result["sources"]) == 2
        source_docs = {s["document"] for s in result["sources"]}
        assert "prices.txt" in source_docs
        assert "faq.txt" in source_docs

    def test_confidence_higher_with_good_context_than_no_context(self):
        """
        Confidence when similar chunks are found should exceed confidence
        when no chunks are found (all else being equal).
        """
        base_ai_response = {
            "response": "Here is our policy.",
            "confidence": 0.5,
            "tokens_used": 30,
        }

        # Case 1: good context available
        good_chunk = _make_chunk(similarity=0.80)
        svc_with_context = _make_rag_service(
            ai_available=True,
            similar_chunks=[good_chunk],
            ai_response=dict(base_ai_response),
        )
        result_with_context = svc_with_context.generate_response(
            _make_user(), "question"
        )

        # Case 2: no context available
        svc_no_context = _make_rag_service(
            ai_available=True,
            similar_chunks=[],
            ai_response=dict(base_ai_response),
        )
        result_no_context = svc_no_context.generate_response(
            _make_user(), "question"
        )

        assert result_with_context["confidence"] > result_no_context["confidence"]

    def test_generate_response_includes_context_chunks_count(self):
        chunks = [_make_chunk(similarity=0.7), _make_chunk("other.txt", similarity=0.65)]
        svc = _make_rag_service(
            ai_available=True,
            similar_chunks=chunks,
            ai_response={"response": "answer", "confidence": 0.5},
        )

        result = svc.generate_response(_make_user(), "question")

        assert result.get("context_chunks") == 2

    def test_generate_response_with_no_chunks_has_zero_context_chunks(self):
        svc = _make_rag_service(
            ai_available=True,
            similar_chunks=[],
            ai_response={"response": "generic answer", "confidence": 0.5},
        )

        result = svc.generate_response(_make_user(), "question")

        assert result.get("context_chunks") == 0

    def test_generate_response_confidence_clamped_to_max_0_95(self):
        """Even if base AI confidence + similarity boost would exceed 0.95, it should be clamped."""
        high_sim_chunk = _make_chunk(similarity=0.95)
        svc = _make_rag_service(
            ai_available=True,
            similar_chunks=[high_sim_chunk],
            ai_response={"response": "perfect answer", "confidence": 0.9},
        )

        result = svc.generate_response(_make_user(), "question")

        assert result["confidence"] <= 0.95

    def test_sources_deduplication(self):
        """Two chunks from the same doc with the same chunk_index → only one source entry."""
        duplicate_chunk = _make_chunk("faq.txt", chunk_index=0, similarity=0.8)
        svc = _make_rag_service(
            ai_available=True,
            similar_chunks=[duplicate_chunk, duplicate_chunk],
            ai_response={"response": "answer", "confidence": 0.5},
        )

        result = svc.generate_response(_make_user(), "question")

        assert len(result["sources"]) == 1

    def test_generate_response_passes_message_to_ai_client(self):
        svc = _make_rag_service(
            ai_available=True,
            similar_chunks=[],
            ai_response={"response": "answer", "confidence": 0.5},
        )
        user = _make_user()

        svc.generate_response(user, "What is your refund policy?")

        svc.ai_client.generate_response.assert_called_once()
        call_kwargs = svc.ai_client.generate_response.call_args
        # message should be passed, either positionally or as kwarg
        all_args = list(call_kwargs.args) + list(call_kwargs.kwargs.values())
        assert "What is your refund policy?" in all_args
