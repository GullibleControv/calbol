"""
Signals for Knowledge Base

Auto-trigger document processing after upload.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Document


@receiver(post_save, sender=Document)
def process_document_on_upload(sender, instance, created, **kwargs):
    """
    Trigger document processing when a new document is uploaded.
    """
    if created and not instance.processed:
        # Import here to avoid circular imports
        from .tasks import process_document

        # Queue for background processing
        try:
            process_document.delay(instance.id)
        except Exception:
            # If Celery isn't running, process synchronously
            # (for development without Redis)
            process_document(instance.id)
