"""
Embedding Service

Creates and manages vector embeddings for semantic search.
"""
import logging
import json
import numpy as np
from typing import List, Optional, Tuple
from .ai_client import get_ai_client

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Manages embeddings for knowledge base chunks.

    Handles:
    - Creating embeddings for document chunks
    - Semantic similarity search
    """

    def __init__(self):
        self.ai_client = get_ai_client()

    def create_chunk_embedding(self, content: str) -> Optional[List[float]]:
        """
        Create embedding for a single chunk.

        Args:
            content: Text content to embed

        Returns:
            Embedding vector or None on error
        """
        return self.ai_client.create_embedding(content)

    def create_chunk_embeddings(self, contents: List[str]) -> List[Optional[List[float]]]:
        """
        Create embeddings for multiple chunks efficiently.

        Args:
            contents: List of text contents

        Returns:
            List of embedding vectors
        """
        return self.ai_client.create_embeddings_batch(contents)

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score between -1 and 1
        """
        if not vec1 or not vec2:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def find_similar_chunks(
        self,
        query: str,
        chunks: List[dict],
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Tuple[dict, float]]:
        """
        Find chunks most similar to a query using numpy batch operations.

        Vectorised approach:
        1. Stack all valid chunk embeddings into a 2D matrix (n_chunks x 1536)
        2. Compute all dot products in a single matrix multiply
        3. Divide by norms to obtain cosine similarities
        4. Use np.argsort to select top_k and filter by min_similarity

        Args:
            query: Search query text
            chunks: List of chunk dicts with 'content' and 'embedding' keys
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold

        Returns:
            List of (chunk, similarity_score) tuples, sorted by similarity
        """
        # Get query embedding
        query_embedding = self.ai_client.create_embedding(query)
        if not query_embedding:
            logger.warning("Could not create query embedding")
            return []

        # Parse and validate each chunk embedding; track which chunks are usable
        valid_chunks = []
        valid_embeddings = []

        for chunk in chunks:
            embedding = chunk.get('embedding')
            if not embedding:
                continue

            # Handle JSON-stored embeddings
            if isinstance(embedding, str):
                try:
                    embedding = json.loads(embedding)
                except json.JSONDecodeError:
                    continue

            if not isinstance(embedding, list) or len(embedding) == 0:
                continue

            valid_chunks.append(chunk)
            valid_embeddings.append(embedding)

        if not valid_embeddings:
            return []

        # Build matrices for vectorised cosine similarity
        # Shape: (n_chunks, embedding_dim)
        embeddings_matrix = np.array(valid_embeddings, dtype=np.float64)
        # Shape: (embedding_dim,)
        query_vec = np.array(query_embedding, dtype=np.float64)

        # Dot products: shape (n_chunks,)
        dot_products = embeddings_matrix @ query_vec

        # Norms
        query_norm = np.linalg.norm(query_vec)
        chunk_norms = np.linalg.norm(embeddings_matrix, axis=1)

        # Avoid division by zero
        denom = chunk_norms * query_norm
        with np.errstate(invalid='ignore', divide='ignore'):
            scores = np.where(denom > 0, dot_products / denom, 0.0)

        # Filter by min_similarity threshold
        above_threshold = np.where(scores >= min_similarity)[0]

        if len(above_threshold) == 0:
            return []

        # Sort descending by score and take top_k
        sorted_indices = above_threshold[np.argsort(scores[above_threshold])[::-1]]
        top_indices = sorted_indices[:top_k]

        return [(valid_chunks[i], float(scores[i])) for i in top_indices]

    def search_user_knowledge(
        self,
        user,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> List[Tuple[dict, float]]:
        """
        Search all document chunks for a user.

        Args:
            user: User model instance
            query: Search query
            top_k: Number of results
            min_similarity: Minimum similarity threshold

        Returns:
            List of (chunk_info, similarity) tuples
        """
        from knowledge.models import DocumentChunk

        # Get all chunks for user's documents
        chunks = DocumentChunk.objects.filter(
            document__user=user,
            document__processed=True
        ).select_related('document').values(
            'id', 'content', 'embedding', 'chunk_index',
            'document__filename', 'document__id'
        )

        chunk_list = [
            {
                'id': c['id'],
                'content': c['content'],
                'embedding': c['embedding'],
                'chunk_index': c['chunk_index'],
                'document_filename': c['document__filename'],
                'document_id': c['document__id']
            }
            for c in chunks
        ]

        return self.find_similar_chunks(
            query, chunk_list, top_k, min_similarity
        )
