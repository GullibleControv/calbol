"""
Unit tests for EmbeddingService.

All tests mock the AI client so no real OpenAI calls are made.

Covers:
- cosine_similarity edge cases (identical, orthogonal, zero vectors)
- find_similar_chunks top-k ordering
- find_similar_chunks min_similarity filtering
- find_similar_chunks with all-None embeddings
- numpy batch path produces same results as pure-Python path
"""
import os
import math
import pytest
from unittest.mock import MagicMock, patch

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from knowledge.services.embeddings import EmbeddingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 1536


def _unit_vec(dim: int, hot_index: int) -> list:
    """Return a 1536-dim unit vector with a 1 at hot_index."""
    vec = [0.0] * dim
    vec[hot_index] = 1.0
    return vec


def _make_service(query_embedding=None):
    """
    Return an EmbeddingService whose AI client is fully mocked.

    query_embedding: what create_embedding() will return for the query.
    """
    mock_client = MagicMock()
    mock_client.create_embedding.return_value = query_embedding
    with patch("knowledge.services.embeddings.get_ai_client", return_value=mock_client):
        service = EmbeddingService()
    # Directly replace client so further calls are intercepted
    service.ai_client = mock_client
    return service


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors_return_one(self):
        svc = _make_service()
        vec = [1.0, 0.0, 0.0]
        assert math.isclose(svc.cosine_similarity(vec, vec), 1.0, rel_tol=1e-6)

    def test_orthogonal_vectors_return_zero(self):
        svc = _make_service()
        assert math.isclose(svc.cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)

    def test_opposite_vectors_return_negative_one(self):
        svc = _make_service()
        result = svc.cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert math.isclose(result, -1.0, rel_tol=1e-6)

    def test_empty_vec1_returns_zero(self):
        svc = _make_service()
        assert svc.cosine_similarity([], [1.0, 0.0]) == 0.0

    def test_empty_vec2_returns_zero(self):
        svc = _make_service()
        assert svc.cosine_similarity([1.0, 0.0], []) == 0.0

    def test_both_empty_returns_zero(self):
        svc = _make_service()
        assert svc.cosine_similarity([], []) == 0.0

    def test_zero_magnitude_vector_returns_zero(self):
        svc = _make_service()
        assert svc.cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_non_normalised_vectors_still_correct(self):
        svc = _make_service()
        # [2, 0] and [5, 0] are parallel — cosine = 1
        result = svc.cosine_similarity([2.0, 0.0], [5.0, 0.0])
        assert math.isclose(result, 1.0, rel_tol=1e-6)

    def test_partial_similarity(self):
        svc = _make_service()
        # 45-degree angle → cos(45°) ≈ 0.707
        result = svc.cosine_similarity([1.0, 1.0], [1.0, 0.0])
        assert math.isclose(result, 1 / math.sqrt(2), rel_tol=1e-6)


# ---------------------------------------------------------------------------
# find_similar_chunks
# ---------------------------------------------------------------------------

def _make_chunk(idx: int, hot_index: int, content: str = None) -> dict:
    """Return a chunk dict with an embedding pointing in dimension hot_index."""
    return {
        "id": idx,
        "content": content or f"chunk content {idx}",
        "embedding": _unit_vec(EMBEDDING_DIM, hot_index),
        "chunk_index": idx,
        "document_filename": "test.txt",
        "document_id": 1,
    }


class TestFindSimilarChunks:
    def test_returns_top_k_sorted_by_score(self):
        # Query vec points along dim 0 → chunk 0 should rank highest
        query_vec = _unit_vec(EMBEDDING_DIM, 0)
        svc = _make_service(query_embedding=query_vec)

        chunks = [
            _make_chunk(0, hot_index=0),   # similarity = 1.0
            _make_chunk(1, hot_index=1),   # similarity = 0.0
            _make_chunk(2, hot_index=2),   # similarity = 0.0
        ]

        results = svc.find_similar_chunks("query", chunks, top_k=3, min_similarity=0.0)

        assert len(results) == 3
        # First result must be chunk 0 (highest similarity)
        assert results[0][0]["id"] == 0
        assert math.isclose(results[0][1], 1.0, rel_tol=1e-6)

    def test_filters_below_min_similarity(self):
        query_vec = _unit_vec(EMBEDDING_DIM, 0)
        svc = _make_service(query_embedding=query_vec)

        chunks = [
            _make_chunk(0, hot_index=0),   # similarity = 1.0
            _make_chunk(1, hot_index=1),   # similarity = 0.0
        ]

        results = svc.find_similar_chunks("query", chunks, top_k=5, min_similarity=0.5)

        # Only chunk 0 should pass the threshold
        assert len(results) == 1
        assert results[0][0]["id"] == 0

    def test_top_k_limits_returned_results(self):
        query_vec = _unit_vec(EMBEDDING_DIM, 0)
        svc = _make_service(query_embedding=query_vec)

        # All chunks have similarity = 1.0 (they all point to dim 0)
        chunks = [_make_chunk(i, hot_index=0) for i in range(10)]

        results = svc.find_similar_chunks("query", chunks, top_k=3, min_similarity=0.0)

        assert len(results) == 3

    def test_all_none_embeddings_returns_empty_list(self):
        query_vec = _unit_vec(EMBEDDING_DIM, 0)
        svc = _make_service(query_embedding=query_vec)

        chunks = [
            {"id": i, "content": "text", "embedding": None, "chunk_index": i,
             "document_filename": "f.txt", "document_id": 1}
            for i in range(5)
        ]

        results = svc.find_similar_chunks("query", chunks, top_k=5, min_similarity=0.0)

        assert results == []

    def test_missing_embedding_key_skipped(self):
        query_vec = _unit_vec(EMBEDDING_DIM, 0)
        svc = _make_service(query_embedding=query_vec)

        chunks = [
            {"id": 0, "content": "no embedding key", "chunk_index": 0,
             "document_filename": "f.txt", "document_id": 1},
        ]

        results = svc.find_similar_chunks("query", chunks, top_k=5, min_similarity=0.0)
        assert results == []

    def test_json_string_embedding_is_parsed(self):
        import json
        query_vec = _unit_vec(EMBEDDING_DIM, 0)
        svc = _make_service(query_embedding=query_vec)

        embedding = _unit_vec(EMBEDDING_DIM, 0)
        chunks = [
            {
                "id": 0,
                "content": "stored as JSON string",
                "embedding": json.dumps(embedding),
                "chunk_index": 0,
                "document_filename": "f.txt",
                "document_id": 1,
            }
        ]

        results = svc.find_similar_chunks("query", chunks, top_k=5, min_similarity=0.0)
        assert len(results) == 1
        assert math.isclose(results[0][1], 1.0, rel_tol=1e-6)

    def test_query_embedding_failure_returns_empty_list(self):
        svc = _make_service(query_embedding=None)

        chunks = [_make_chunk(0, hot_index=0)]
        results = svc.find_similar_chunks("query", chunks, top_k=5, min_similarity=0.0)

        assert results == []

    def test_empty_chunk_list_returns_empty_list(self):
        query_vec = _unit_vec(EMBEDDING_DIM, 0)
        svc = _make_service(query_embedding=query_vec)

        results = svc.find_similar_chunks("query", [], top_k=5, min_similarity=0.0)
        assert results == []

    def test_results_sorted_highest_first(self):
        """Multiple chunks with known relative similarity; verify descending order."""
        import numpy as np
        # Create query vector tilted towards dim 0 more than dim 1
        query_vec = [0.0] * EMBEDDING_DIM
        query_vec[0] = 0.9
        query_vec[1] = 0.1
        # Normalise
        norm = sum(v ** 2 for v in query_vec) ** 0.5
        query_vec = [v / norm for v in query_vec]

        svc = _make_service(query_embedding=query_vec)

        chunk_high = _make_chunk(0, hot_index=0)   # should score ~0.9
        chunk_low = _make_chunk(1, hot_index=1)    # should score ~0.1

        results = svc.find_similar_chunks(
            "query", [chunk_high, chunk_low], top_k=5, min_similarity=0.0
        )

        assert len(results) == 2
        assert results[0][1] >= results[1][1]
        assert results[0][0]["id"] == 0

    # CROSS-CHECK: numpy batch path gives same results as pure-Python path
    def test_numpy_batch_matches_pure_python(self):
        """
        Ensure the vectorised find_similar_chunks produces the same scores
        as the pure-Python cosine_similarity on each chunk individually.
        """
        import math
        import random
        rng = random.Random(42)

        dim = EMBEDDING_DIM
        # Build 5 random embeddings
        raw_chunks = []
        for i in range(5):
            vec = [rng.gauss(0, 1) for _ in range(dim)]
            # Normalise
            norm = sum(v ** 2 for v in vec) ** 0.5
            vec = [v / norm for v in vec]
            raw_chunks.append({
                "id": i,
                "content": f"chunk {i}",
                "embedding": vec,
                "chunk_index": i,
                "document_filename": "f.txt",
                "document_id": 1,
            })

        query_vec = [rng.gauss(0, 1) for _ in range(dim)]
        norm = sum(v ** 2 for v in query_vec) ** 0.5
        query_vec = [v / norm for v in query_vec]

        svc = _make_service(query_embedding=query_vec)

        # Numpy batch results
        batch_results = svc.find_similar_chunks(
            "q", raw_chunks, top_k=10, min_similarity=-1.0
        )
        batch_scores = {r[0]["id"]: r[1] for r in batch_results}

        # Pure-Python reference scores
        for chunk in raw_chunks:
            expected = svc.cosine_similarity(query_vec, chunk["embedding"])
            actual = batch_scores[chunk["id"]]
            assert math.isclose(expected, actual, rel_tol=1e-5), (
                f"Chunk {chunk['id']}: expected={expected}, actual={actual}"
            )
