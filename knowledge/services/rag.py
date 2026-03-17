"""
RAG (Retrieval Augmented Generation) Service

Combines knowledge base search with AI response generation.
"""
import logging
from typing import List, Optional
from .ai_client import get_ai_client
from .embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class RAGService:
    """
    Retrieval Augmented Generation for CalBol.

    Flow:
    1. User sends a question
    2. Search knowledge base for relevant chunks
    3. Use chunks as context for AI response
    4. Return response with confidence score
    """

    def __init__(self):
        self.ai_client = get_ai_client()
        self.embedding_service = EmbeddingService()

    def generate_response(
        self,
        user,
        message: str,
        max_context_chunks: int = 3,
        min_similarity: float = 0.35
    ) -> dict:
        """
        Generate an AI response using RAG.

        Args:
            user: User model instance (owner of knowledge base)
            message: Customer's message/question
            max_context_chunks: Maximum chunks to include as context
            min_similarity: Minimum similarity for including a chunk

        Returns:
            dict with:
            - response: Generated response text
            - confidence: Confidence score (0-1)
            - sources: List of source documents used
            - error: Error message if failed
        """
        if not self.ai_client.is_available():
            return {
                'response': None,
                'confidence': 0,
                'sources': [],
                'error': 'AI not configured'
            }

        # Step 1: Search knowledge base
        similar_chunks = self.embedding_service.search_user_knowledge(
            user=user,
            query=message,
            top_k=max_context_chunks,
            min_similarity=min_similarity
        )

        # Step 2: Build context from chunks
        context = ""
        sources = []
        avg_similarity = 0

        if similar_chunks:
            context_parts = []
            similarities = []

            for chunk, similarity in similar_chunks:
                context_parts.append(chunk['content'])
                similarities.append(similarity)

                # Track sources
                source = {
                    'document': chunk['document_filename'],
                    'chunk_index': chunk['chunk_index'],
                    'similarity': round(similarity, 3)
                }
                if source not in sources:
                    sources.append(source)

            context = "\n\n---\n\n".join(context_parts)
            avg_similarity = sum(similarities) / len(similarities)

        # Step 3: Generate response
        result = self.ai_client.generate_response(
            message=message,
            context=context,
            max_tokens=300,
            temperature=0.5  # Lower temperature for factual responses
        )

        # Adjust confidence based on context quality
        if result.get('response'):
            # Base confidence from AI response
            confidence = result.get('confidence', 0.5)

            # Boost if we had good context matches
            if similar_chunks:
                confidence = min(0.95, confidence + (avg_similarity * 0.2))
            else:
                # No context = lower confidence
                confidence = max(0.2, confidence - 0.2)

            result['confidence'] = round(confidence, 2)

        result['sources'] = sources
        result['context_chunks'] = len(similar_chunks)

        return result

    def should_use_ai(
        self,
        user,
        message: str
    ) -> dict:
        """
        Determine if AI should respond or escalate to human.

        Checks:
        - Does user have knowledge base content?
        - Is there relevant context for this question?

        Args:
            user: User model instance
            message: Customer's message

        Returns:
            dict with 'should_respond', 'reason', 'confidence'
        """
        from knowledge.models import DocumentChunk

        # Check if user has any processed documents
        chunk_count = DocumentChunk.objects.filter(
            document__user=user,
            document__processed=True
        ).count()

        if chunk_count == 0:
            return {
                'should_respond': False,
                'reason': 'No knowledge base documents',
                'confidence': 0
            }

        # Check if we have relevant context
        similar_chunks = self.embedding_service.search_user_knowledge(
            user=user,
            query=message,
            top_k=3,
            min_similarity=0.35
        )

        if not similar_chunks:
            return {
                'should_respond': False,
                'reason': 'No relevant knowledge found',
                'confidence': 0.1
            }

        # Calculate confidence based on best match
        best_similarity = similar_chunks[0][1] if similar_chunks else 0

        if best_similarity >= 0.6:
            return {
                'should_respond': True,
                'reason': 'High confidence match',
                'confidence': 0.8
            }
        elif best_similarity >= 0.4:
            return {
                'should_respond': True,
                'reason': 'Moderate confidence match',
                'confidence': 0.6
            }
        else:
            return {
                'should_respond': False,
                'reason': 'Low confidence - recommend human review',
                'confidence': 0.3
            }

    def get_fallback_response(self, user) -> str:
        """
        Get a fallback response when AI cannot confidently answer.

        Returns a polite message indicating human follow-up.
        """
        company_name = user.company_name or "our team"

        return (
            f"Thank you for your message! I want to make sure you get the most "
            f"accurate information, so {company_name} will follow up with you "
            f"shortly. Is there anything else I can help you with in the meantime?"
        )
