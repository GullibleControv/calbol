from django.db import models
from django.conf import settings


class Document(models.Model):
    """
    Document Model

    Stores uploaded documents that form the business's knowledge base.
    These documents are processed and used by AI to answer customer questions.

    Example documents:
        - Price list PDF
        - Service menu
        - FAQ document
        - Business brochure

    How it works:
        1. User uploads a PDF/DOCX/TXT file
        2. System extracts text from the document
        3. Text is split into chunks (DocumentChunk)
        4. Each chunk gets an embedding (vector) for AI search
        5. When a customer asks a question, relevant chunks are found
        6. AI uses these chunks to generate an accurate response
    """

    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('docx', 'Word Document'),
        ('txt', 'Text File'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents'
    )

    # Original filename (for display)
    filename = models.CharField(
        max_length=255,
        help_text="Original name of the uploaded file"
    )

    # Actual file storage
    file = models.FileField(
        upload_to='documents/%Y/%m/',  # Organizes by year/month
        help_text="The uploaded document file"
    )

    # File type for processing logic
    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        help_text="Type of document (pdf, docx, txt)"
    )

    # Description (optional, helps user remember what's in the doc)
    description = models.TextField(
        blank=True,
        help_text="Optional description of what this document contains"
    )

    # Processing status
    processed = models.BooleanField(
        default=False,
        help_text="True when document has been chunked and embedded"
    )

    # Error message if processing failed
    processing_error = models.TextField(
        blank=True,
        help_text="Error message if document processing failed"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ['-created_at']

    def __str__(self):
        status = "✓" if self.processed else "⏳"
        return f"{status} {self.filename} ({self.user.email})"

    def get_chunk_count(self):
        """Return number of chunks this document has been split into."""
        return self.chunks.count()


class DocumentChunk(models.Model):
    """
    Document Chunk Model

    A document is split into smaller chunks for AI processing.
    Each chunk is typically 500-1000 tokens (roughly a paragraph).

    Why chunks?
        - AI models have token limits
        - Smaller chunks = more precise search results
        - Only relevant chunks are sent to AI (saves cost)

    How RAG (Retrieval Augmented Generation) works:
        1. Customer asks: "What's your price for beard styling?"
        2. System converts question to embedding (vector)
        3. System finds chunks with similar embeddings
        4. Top 3-5 relevant chunks are retrieved
        5. AI generates answer using these chunks as context
    """

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks'
    )

    # The actual text content of this chunk
    content = models.TextField(
        help_text="The text content of this chunk"
    )

    # Vector embedding for semantic search (stored as JSON array)
    # OpenAI's text-embedding-3-small produces 1536 dimensions
    embedding = models.JSONField(
        null=True,
        blank=True,
        help_text="Vector embedding for semantic search"
    )

    # Position in the original document
    chunk_index = models.IntegerField(
        default=0,
        help_text="Order of this chunk in the document"
    )

    # Metadata (page number, section title, etc.)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata like page number, section"
    )

    # Character count (useful for debugging/analytics)
    char_count = models.IntegerField(
        default=0,
        help_text="Number of characters in this chunk"
    )

    class Meta:
        verbose_name = "Document Chunk"
        verbose_name_plural = "Document Chunks"
        ordering = ['document', 'chunk_index']

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"Chunk {self.chunk_index}: {preview}"

    def save(self, *args, **kwargs):
        # Auto-calculate character count
        self.char_count = len(self.content)
        super().save(*args, **kwargs)

    def has_embedding(self):
        """Check if this chunk has been embedded."""
        return self.embedding is not None and len(self.embedding) > 0
