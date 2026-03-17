"""
Celery Tasks for Knowledge Base

Background tasks for document processing.
"""
import logging
from celery import shared_task
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_document(self, document_id: int):
    """
    Process an uploaded document: extract text, chunk, create embeddings.

    Args:
        document_id: ID of the Document to process
    """
    from knowledge.models import Document, DocumentChunk
    from knowledge.services import DocumentProcessor, EmbeddingService

    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return

    if document.processed:
        logger.info(f"Document {document_id} already processed")
        return

    logger.info(f"Processing document: {document.filename}")

    try:
        # Initialize services
        processor = DocumentProcessor(chunk_size=1000, chunk_overlap=200)
        embedding_service = EmbeddingService()

        # Get file path
        file_path = document.file.path

        # Extract and chunk text
        full_text, chunks = processor.process_document(
            file_path=file_path,
            file_type=document.file_type
        )

        if not chunks:
            document.processing_error = "No text content extracted"
            document.save()
            logger.warning(f"No content extracted from {document.filename}")
            return

        # Create embeddings for all chunks
        embeddings = embedding_service.create_chunk_embeddings(
            [chunk for chunk in chunks]
        )

        # Save chunks with embeddings
        with transaction.atomic():
            # Delete existing chunks (in case of reprocessing)
            DocumentChunk.objects.filter(document=document).delete()

            # Create new chunks
            for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                DocumentChunk.objects.create(
                    document=document,
                    content=chunk_text,
                    embedding=embedding,
                    chunk_index=i
                )

            # Mark document as processed
            document.processed = True
            document.processing_error = ""
            document.save()

        logger.info(
            f"Document {document.filename} processed: "
            f"{len(chunks)} chunks created"
        )

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        document.processing_error = str(e)
        document.save()

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def reprocess_all_documents(user_id: int):
    """
    Reprocess all documents for a user.

    Useful after knowledge base updates or model changes.
    """
    from knowledge.models import Document

    documents = Document.objects.filter(user_id=user_id)

    for doc in documents:
        doc.processed = False
        doc.save()
        process_document.delay(doc.id)

    logger.info(f"Queued {documents.count()} documents for reprocessing")
