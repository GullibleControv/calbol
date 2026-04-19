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

        # Validate each embedding: must be a list of 1536 floats
        valid_pairs = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            if (
                embedding is None
                or not isinstance(embedding, list)
                or len(embedding) != 1536
            ):
                logger.warning(
                    f"Document {document_id}: chunk {i} has invalid embedding "
                    f"(type={type(embedding).__name__}, "
                    f"len={len(embedding) if isinstance(embedding, list) else 'N/A'})"
                )
            else:
                valid_pairs.append((i, chunk_text, embedding))

        # If more than 50% of chunks failed, mark error and trigger retry
        total = len(chunks)
        success_count = len(valid_pairs)
        failure_count = total - success_count

        if total > 0 and failure_count / total > 0.5:
            error_msg = (
                f"Embedding failure rate too high: "
                f"{failure_count}/{total} chunks failed"
            )
            logger.error(f"Document {document_id}: {error_msg}")
            document.processing_error = error_msg
            document.save()
            raise ValueError(error_msg)

        # Save only chunks with valid embeddings
        with transaction.atomic():
            # Delete existing chunks (in case of reprocessing)
            DocumentChunk.objects.filter(document=document).delete()

            # Create new chunks (original index preserved as chunk_index)
            for original_index, chunk_text, embedding in valid_pairs:
                DocumentChunk.objects.create(
                    document=document,
                    content=chunk_text,
                    embedding=embedding,
                    chunk_index=original_index
                )

            # Mark document as processed
            document.processed = True
            document.processing_error = ""
            document.save()

        logger.info(
            f"Document {document.filename} processed: "
            f"{success_count}/{total} chunks embedded successfully"
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
