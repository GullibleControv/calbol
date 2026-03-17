"""
AI Client Service

Wraps OpenAI API for text generation and embeddings.
"""
import logging
from typing import List, Optional
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


class AIClient:
    """
    OpenAI API client for CalBol.

    Handles:
    - Text generation (chat completions)
    - Embeddings for semantic search
    """

    def __init__(self):
        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            logger.warning("OPENAI_API_KEY not set. AI features will be disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)

        # Default models
        self.chat_model = "gpt-4o-mini"  # Fast and cheap for auto-replies
        self.embedding_model = "text-embedding-3-small"

    def is_available(self) -> bool:
        """Check if AI client is configured and available."""
        return self.client is not None

    def generate_response(
        self,
        message: str,
        context: str = "",
        system_prompt: str = None,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> dict:
        """
        Generate an AI response to a customer message.

        Args:
            message: The customer's message
            context: Relevant context from knowledge base
            system_prompt: Custom system prompt (optional)
            max_tokens: Maximum response length
            temperature: Creativity (0=deterministic, 1=creative)

        Returns:
            dict with 'response', 'confidence', 'tokens_used'
        """
        if not self.is_available():
            return {
                'response': None,
                'confidence': 0,
                'error': 'AI client not configured'
            }

        # Default system prompt for business auto-replies
        if system_prompt is None:
            system_prompt = """You are a helpful customer service assistant for a business.
Your job is to answer customer questions based on the provided context.

Guidelines:
- Be friendly, professional, and concise
- Only answer based on the provided context
- If you don't have enough information, say so politely
- Keep responses under 2-3 sentences when possible
- Don't make up information not in the context"""

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        if context:
            messages.append({
                "role": "system",
                "content": f"Relevant information from knowledge base:\n{context}"
            })

        messages.append({"role": "user", "content": message})

        try:
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0

            # Estimate confidence based on response characteristics
            confidence = self._estimate_confidence(content, context)

            return {
                'response': content,
                'confidence': confidence,
                'tokens_used': tokens,
                'model': self.chat_model
            }

        except Exception as e:
            logger.error(f"AI generation error: {e}")
            return {
                'response': None,
                'confidence': 0,
                'error': str(e)
            }

    def create_embedding(self, text: str) -> Optional[List[float]]:
        """
        Create an embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector) or None on error
        """
        if not self.is_available():
            return None

        try:
            # Truncate text if too long (8191 tokens max)
            text = text[:30000]  # Rough character limit

            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    def create_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Create embeddings for multiple texts in one API call.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not self.is_available():
            return [None] * len(texts)

        try:
            # Truncate each text
            texts = [t[:30000] for t in texts]

            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )

            # Sort by index to maintain order
            embeddings = [None] * len(texts)
            for item in response.data:
                embeddings[item.index] = item.embedding

            return embeddings

        except Exception as e:
            logger.error(f"Batch embedding error: {e}")
            return [None] * len(texts)

    def _estimate_confidence(self, response: str, context: str) -> float:
        """
        Estimate confidence in the AI response.

        Simple heuristic based on:
        - Whether context was provided
        - Response length and characteristics
        """
        if not response:
            return 0.0

        confidence = 0.5  # Base confidence

        # Higher confidence if we had context
        if context:
            confidence += 0.2

        # Lower confidence for uncertain language
        uncertain_phrases = [
            "i'm not sure",
            "i don't know",
            "i cannot",
            "unfortunately",
            "i don't have"
        ]
        response_lower = response.lower()
        for phrase in uncertain_phrases:
            if phrase in response_lower:
                confidence -= 0.15
                break

        # Ensure bounds
        return max(0.1, min(0.95, confidence))


# Singleton instance
_ai_client = None

def get_ai_client() -> AIClient:
    """Get or create the AI client singleton."""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client
